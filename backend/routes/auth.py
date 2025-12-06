# backend/routes/auth.py

import bcrypt
import traceback
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from typing import List, Dict
from bson import ObjectId
from services.extractor import UERJExtractor
from database import db
from models import User, Discipline, DisciplinaAluno

router = APIRouter()

# --- CORREÇÃO 1: Função agora recebe horário e salva tudo ---
async def get_or_create_global_id(codigo: str, nome: str, turma: str, semestre: str, horario: List[str]) -> str:
    """
    Busca uma turma existente ou cria uma nova.
    A chave única é: CODIGO + TURMA + SEMESTRE.
    """
    try:
        coll = db.get_collection("disciplines")
        
        # Garante que a turma seja string e sem espaços (Normalização)
        turma_limpa = str(turma).strip() if turma else "1"
        
        # 1. Busca Exata
        filtro = {
            "codigo": codigo, 
            "turma": turma_limpa,
            "semestre": semestre
        }
        
        found = await coll.find_one(filtro)
        
        if found: 
            # Se já existe, retorna o ID dela (não duplica!)
            return str(found["_id"])
        
        # 2. Se não existe, CRIA com os dados completos
        print(f"🆕 Criando nova turma global: {nome} (Turma {turma_limpa})")
        
        new_d = Discipline(
            nome=nome, 
            codigo=codigo, 
            turma=turma_limpa, # Salva o número da turma
            semestre=semestre,
            horario=horario,   # Salva o horário
            membros=[]         # Começa vazia
        )
        
        res = await coll.insert_one(new_d.model_dump(by_alias=True, exclude=["id"]))
        return str(res.inserted_id)
    except Exception as e:
        print(f"Erro ao buscar/criar disciplina: {e}")
        return None

@router.get("/users/debug", response_model=List[User])
async def list_all_users():
    return await db.get_collection("users").find().to_list(100)

@router.post("/register", response_model=User, status_code=201)
async def register(
    nome: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
    rid: UploadFile = File(...),
    historico: UploadFile = File(...)
):
    try:
        users_col = db.get_collection("users")
        if await users_col.find_one({"email": email}):
            raise HTTPException(400, "Email já cadastrado.")

        # Extração
        rid_bytes = await rid.read()
        hist_bytes = await historico.read()

        dict_atuais = UERJExtractor.parse_rid(rid_bytes)
        dict_hist = UERJExtractor.parse_historico(hist_bytes)

        # Processamento
        async def processar_disciplinas(dados_raw: Dict, vincular_global: bool):
            resultado = {}
            for semestre, lista in dados_raw.items():
                objs_semestre = []
                for item in lista:
                    gid = None
                    # Se for disciplina atual, buscamos/criamos a sala global
                    if vincular_global:
                        gid = await get_or_create_global_id(
                            codigo=item["codigo"], 
                            nome=item["nome"],
                            turma=item.get("turma", "1"), # Passa a turma
                            semestre=semestre,
                            horario=item.get("horario", []) # Passa o horário!
                        )
                    
                    d_obj = DisciplinaAluno(
                        codigo=item["codigo"],
                        nome=item["nome"],
                        turma=item.get("turma"),
                        horario=item.get("horario", []),
                        nota=item.get("nota"),
                        status=item.get("status", "Cursando"),
                        disciplina_id=gid
                    )
                    objs_semestre.append(d_obj)
                resultado[semestre] = objs_semestre
            return resultado

        atuais_final = await processar_disciplinas(dict_atuais, vincular_global=True)
        historico_final = await processar_disciplinas(dict_hist, vincular_global=False)

        # Criação do Usuário
        hashed = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()
        periodo_ref = list(atuais_final.keys())[0] if atuais_final else "2025.1"

        new_user = User(
            nome=nome,
            email=email,
            senha_hash=hashed,
            disciplinas_atuais=atuais_final,
            historico=historico_final,
            periodo_atual=periodo_ref
        )

        res = await users_col.insert_one(new_user.model_dump(by_alias=True, exclude=["id"]))
        user_id = res.inserted_id
        
        # --- MATRÍCULA AUTOMÁTICA (Adiciona o aluno nas turmas encontradas) ---
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