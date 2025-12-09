import traceback
from typing import List
from services.utils import get_system_semester
import bcrypt
from bson import ObjectId
from database import db
from fastapi import (APIRouter, Body, Depends, File, Form, HTTPException,
                     UploadFile)
from models import DisciplinaAluno, Discipline, User
from pydantic import BaseModel, EmailStr
from security import get_current_user
# Imports da NOVA lógica de autenticação
from services.auth_utils import (generate_six_digit_token, save_token_to_db,
                                 send_reset_password_email,
                                 send_validation_email,
                                 validar_dominio_graduacao,
                                 verify_and_delete_token)
# Imports do sistema existente
from services.extractor import UERJExtractor

router = APIRouter()

# --- Modelos Auxiliares ---
class TokenRequest(BaseModel):
    email: EmailStr

# --- HELPER ---
async def get_or_create_global_id(codigo: str, nome: str, turma: str, semestre: str, horario: List[str]) -> str:
    try:
        coll = db.get_collection("disciplines")
        turma_limpa = str(turma).strip().upper() if turma else "1"
        if turma_limpa.isdigit(): turma_limpa = str(int(turma_limpa))
        
        filtro = {
            "codigo": codigo.strip().upper(), 
            "turma": turma_limpa,
            "semestre": semestre.strip()
        }
        
        found = await coll.find_one(filtro)
        if found: return str(found["_id"])
        
        new_d = Discipline(
            nome=nome.strip(), 
            codigo=codigo.strip().upper(), 
            turma=turma_limpa, 
            semestre=semestre.strip(),
            horario=horario,   
            membros=[]         
        )
        res = await coll.insert_one(new_d.model_dump(by_alias=True, exclude=["id"]))
        return str(res.inserted_id)
    except Exception as e:
        print(f"Erro disciplina global: {e}")
        return None


# ==========================================
# ROTA 1: SOLICITAR TOKEN
# ==========================================
@router.post("/request-token")
async def request_token(payload: TokenRequest):
    email = payload.email

    # 1. Validação de Domínio
    if not validar_dominio_graduacao(email):
        raise HTTPException(400, "Domínio inválido. Use @aluno.uerj.br ou @uerj.br")
    
    # 2. Verifica se usuário já existe
    if await db.get_collection("users").find_one({"email": email}):
        raise HTTPException(400, "E-mail já cadastrado.")

    # 3. Fluxo de Token
    token = generate_six_digit_token()
    await save_token_to_db(email, token)
    
    # 4. Envio de Email
    try:
        await send_validation_email(email, token)
    except Exception as e:
        print(f"Erro envio email: {e}")
        raise HTTPException(500, "Erro ao enviar e-mail. Verifique o servidor.")

    return {"message": f"Token enviado para {email}"}


# ==========================================
# ROTA 2: CADASTRO FINAL 
# ==========================================
@router.post("/register", response_model=User, status_code=201)
async def register(
    nome: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
    token: str = Form(...),
    
):
    # 1. VALIDAÇÃO DO TOKEN
    is_valid = await verify_and_delete_token(email, token)
    if not is_valid:
        raise HTTPException(401, "Token inválido ou expirado.")

    try:
        users_col = db.get_collection("users")
        
        if await users_col.find_one({"email": email}):
            raise HTTPException(400, "Email já cadastrado.")

        # 3. Hash da senha
        hashed = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()

        # 3. Busca o semestre ativo no sistema (ex: "2025.1")
        semestre_inicial = await get_system_semester()

        # 4. Cria Objeto Usuário
        new_user = User(
            nome=nome,
            email=email,
            senha_hash=hashed,
            disciplinas_atuais={}, # Começa vazio, importa depois
            historico={},          
            periodo_atual=semestre_inicial # Já nasce no semestre certo
        )

        # 5. Salva no Banco
        res = await users_col.insert_one(new_user.model_dump(by_alias=True, exclude=["id"]))
        user_id = res.inserted_id
        
        return await users_col.find_one({"_id": user_id})

    except HTTPException as he:
        raise he
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Erro interno: {str(e)}")


# ==========================================
# ROTA MEU PERFIL
# ==========================================
@router.get("/me", response_model=User, response_model_exclude={"senha_hash"})
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user


# ROTA 4: IMPORTAR DISCPLINAS EM CURSO
@router.post("/me/importar-rid")
async def upload_rid_grade(
    arquivo: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    try:
        # 1. Pega a configuração GLOBAL do Admin
        semestre_sistema = await get_system_semester()

        # 2. Processa o PDF
        rid_bytes = await arquivo.read()
        dict_extracted = UERJExtractor.parse_rid(rid_bytes) 
        # O extractor retorna algo como: { "2024.2": [list...] } ou { "Atual": [...] }

        if not dict_extracted:
            raise HTTPException(400, "Não foi possível ler as disciplinas.")

        # 3. UNIFICAÇÃO: Ignora a chave de semestre do PDF e usa a do SISTEMA.
        # Pegamos a primeira lista de disciplinas que encontrarmos no arquivo
        lista_disciplinas_pdf = []
        for sem_key, lista in dict_extracted.items():
            if lista:
                lista_disciplinas_pdf = lista
                break
        
        # Se o PDF estiver vazio
        if not lista_disciplinas_pdf:
             raise HTTPException(400, "Nenhuma disciplina encontrada no PDF.")

        # --- LÓGICA DE ATUALIZAÇÃO ---
        disc_col = db.get_collection("disciplines")
        user_col = db.get_collection("users")
        user_id = ObjectId(current_user.id)
        
        objs_semestre_user = []
        ids_novos = set()

        # Mapeia IDs antigos DESTE semestre específico (para saber se o aluno saiu de alguma)
        ids_antigos = set()
        if current_user.disciplinas_atuais and semestre_sistema in current_user.disciplinas_atuais:
            for d_antiga in current_user.disciplinas_atuais[semestre_sistema]:
                gid = d_antiga.get("disciplina_id") if isinstance(d_antiga, dict) else d_antiga.disciplina_id
                if gid: ids_antigos.add(str(gid))

        # Processa as novas
        for item in lista_disciplinas_pdf:
            codigo = item["codigo"].strip().upper()
            turma = str(item.get("turma", "1")).strip()
            
            # CRIA/BUSCA TURMA GLOBAL USANDO O SEMESTRE DO SISTEMA
            gid_str = await get_or_create_global_id(
                codigo=codigo, 
                nome=item["nome"],
                turma=turma, 
                semestre=semestre_sistema, # <--- FORÇA O SEMESTRE GLOBAL
                horario=item.get("horario", []) 
            )
            
            if gid_str:
                ids_novos.add(gid_str)
                # Adiciona aluno na turma global
                await disc_col.update_one(
                    {"_id": ObjectId(gid_str)},
                    {"$addToSet": {"membros": user_id}}
                )

            # Objeto Local do Usuário
            d_obj = DisciplinaAluno(
                codigo=codigo,
                nome=item["nome"].strip(),
                turma=turma,
                horario=item.get("horario", []),
                nota=None,
                status="Cursando",
                disciplina_id=gid_str
            )
            objs_semestre_user.append(d_obj.model_dump())

        # Remove aluno das turmas que ele saiu (que estavam no banco mas não estão no PDF)
        ids_para_sair = ids_antigos - ids_novos
        if ids_para_sair:
            await disc_col.update_many(
                {"_id": {"$in": [ObjectId(i) for i in ids_para_sair]}},
                {"$pull": {"membros": user_id}}
            )

        # SALVA NO USUÁRIO
        # Preserva histórico de outros semestres se houver, mas atualiza o ATUAL
        disciplinas_atuais_atualizadas = current_user.disciplinas_atuais or {}
        disciplinas_atuais_atualizadas[semestre_sistema] = objs_semestre_user

        await user_col.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "disciplinas_atuais": disciplinas_atuais_atualizadas,
                    "periodo_atual": semestre_sistema # Garante que o usuário está no semestre certo
                }
            }
        )

        return {
            "message": f"Grade importada para o semestre {semestre_sistema}!",
            "turmas_qtd": len(objs_semestre_user)
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Erro ao importar RID: {str(e)}")

# ROTA 5: ENVIAR HISTÓRICO
@router.post("/me/historico")
async def upload_historico(
    arquivo: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    try:
        hist_bytes = await arquivo.read()
        dict_hist = UERJExtractor.parse_historico(hist_bytes)
        
        if not dict_hist:
            raise HTTPException(400, "Não foi possível ler o histórico.")

        historico_final = {}
        for semestre, lista in dict_hist.items():
            objs_semestre = []
            for item in lista:
                d_obj = DisciplinaAluno(
                    codigo=item["codigo"].strip().upper(),
                    nome=item["nome"].strip(),
                    turma=None,
                    horario=[],
                    nota=item.get("nota"),
                    status=item.get("status", "Cursado"),
                    disciplina_id=None
                )
                objs_semestre.append(d_obj.model_dump())
            historico_final[semestre] = objs_semestre

        await db.get_collection("users").update_one(
            {"_id": ObjectId(current_user.id)},
            {"$set": {"historico": historico_final}}
        )

        return {"message": "Histórico importado!", "semestres": list(historico_final.keys())}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Erro: {str(e)}")
    
@router.delete("/me/disciplinas-atuais")
async def limpar_minhas_disciplinas(current_user: User = Depends(get_current_user)):
    """
    Remove o aluno de todas as turmas atuais e limpa sua grade.
    """
    try:
        user_col = db.get_collection("users")
        disc_col = db.get_collection("disciplines")
        user_id = ObjectId(current_user.id)

        # 1. Encontrar IDs das turmas atuais para remover o aluno da lista de membros
        ids_para_sair = []
        if current_user.disciplinas_atuais:
            for sem, lista in current_user.disciplinas_atuais.items():
                for disc in lista:
                    # Verifica se é dict ou objeto
                    gid = disc.get("disciplina_id") if isinstance(disc, dict) else disc.disciplina_id
                    if gid:
                        ids_para_sair.append(ObjectId(gid))
        
        # 2. Remover aluno da coleção 'disciplines' (Global)
        if ids_para_sair:
            await disc_col.update_many(
                {"_id": {"$in": ids_para_sair}},
                {"$pull": {"membros": user_id}}
            )

        # 3. Limpar o perfil do usuário
        await user_col.update_one(
            {"_id": user_id},
            {"$set": {"disciplinas_atuais": {}}}
        )

        return {"message": "Todas as disciplinas foram removidas com sucesso."}

    except Exception as e:
        print(f"Erro ao limpar disciplinas: {e}")
        raise HTTPException(500, "Erro ao remover disciplinas.")
