# backend/routes/auth.py
import traceback
from typing import List

import bcrypt
from bson import ObjectId
from database import db
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Body, Depends
from models import DisciplinaAluno, Discipline, User
from pydantic import BaseModel, EmailStr
from security import get_current_user
# Imports da NOVA lógica de autenticação
from services.auth_utils import (generate_six_digit_token, save_token_to_db,
                                 send_validation_email,
                                 validar_dominio_graduacao,
                                 verify_and_delete_token)
# Imports do sistema existente
from services.extractor import UERJExtractor

router = APIRouter()

# --- Modelos Auxiliares ---
class TokenRequest(BaseModel):
    email: EmailStr

# --- HELPER (Mantido do original) ---
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
# 🚀 NOVA ROTA 1: SOLICITAR TOKEN
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
# 🚀 ROTA 2: CADASTRO FINAL (MODIFICADA)
# ==========================================
@router.post("/register", response_model=User, status_code=201)
async def register(
    nome: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
    token: str = Form(...), # <--- NOVO CAMPO OBRIGATÓRIO
    rid: UploadFile = File(...)
):
    # 1. VALIDAÇÃO DO TOKEN ANTES DE TUDO
    is_valid = await verify_and_delete_token(email, token)
    if not is_valid:
        raise HTTPException(401, "Token inválido ou expirado.")

    # Daqui pra baixo, segue a lógica original de processar RID
    try:
        users_col = db.get_collection("users")
        
        # Redundância de segurança: checa duplicidade de novo
        if await users_col.find_one({"email": email}):
            raise HTTPException(400, "Email já cadastrado.")

        # Processa RID
        rid_bytes = await rid.read()
        dict_atuais = UERJExtractor.parse_rid(rid_bytes)

        # Processa Disciplinas
        atuais_final = {}
        for semestre, lista in dict_atuais.items():
            objs_semestre = []
            for item in lista:
                codigo_user = item["codigo"].strip().upper()
                turma_user = str(item.get("turma", "1")).strip().upper()
                if turma_user.isdigit(): turma_user = str(int(turma_user))

                gid = await get_or_create_global_id(
                    codigo=codigo_user, 
                    nome=item["nome"],
                    turma=turma_user, 
                    semestre=semestre,
                    horario=item.get("horario", []) 
                )
                
                d_obj = DisciplinaAluno(
                    codigo=codigo_user,
                    nome=item["nome"].strip(),
                    turma=turma_user,
                    horario=item.get("horario", []),
                    nota=None,
                    status="Cursando",
                    disciplina_id=gid
                )
                objs_semestre.append(d_obj)
            atuais_final[semestre] = objs_semestre

        # Cria Usuário
        hashed = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()
        periodo_ref = list(atuais_final.keys())[0] if atuais_final else "2025.1"

        new_user = User(
            nome=nome,
            email=email,
            senha_hash=hashed,
            disciplinas_atuais=atuais_final,
            historico={},
            periodo_atual=periodo_ref
        )

        res = await users_col.insert_one(new_user.model_dump(by_alias=True, exclude=["id"]))
        user_id = res.inserted_id
        
        # Matrícula
        if atuais_final:
            disc_col = db.get_collection("disciplines")
            for semestre, lista_disciplinas in atuais_final.items():
                for materia in lista_disciplinas:
                    if materia.disciplina_id:
                        await disc_col.update_one(
                            {"_id": ObjectId(materia.disciplina_id)},
                            {"$addToSet": {"membros": user_id}}
                        )

        return await users_col.find_one({"_id": user_id})

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Erro interno: {str(e)}")

# As outras rotas (/me, /historico) continuam iguais...
# ... (Cole o restante do seu arquivo auth.py original aqui para manter /me e /historico)
@router.get("/me", response_model=User, response_model_exclude={"senha_hash"})
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/me/historico")
async def upload_historico(arquivo: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    # ... (mesma lógica do original)
    pass