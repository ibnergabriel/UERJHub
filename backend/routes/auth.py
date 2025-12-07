import bcrypt
import traceback
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import List, Dict
from bson import ObjectId
from services.extractor import UERJExtractor
from database import db
from models import User, Discipline, DisciplinaAluno
from security import get_current_user # <--- Importante: Guarda de Segurança

router = APIRouter()

# --- HELPER: Busca ou Cria Turma Global ---
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

# --- ROTA 1: CADASTRO (Pública - Só pede RID) ---
@router.post("/register", response_model=User, status_code=201)
async def register(
    nome: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
    rid: UploadFile = File(...)
):
    try:
        users_col = db.get_collection("users")
        if await users_col.find_one({"email": email}):
            raise HTTPException(400, "Email já cadastrado.")

        # Processa RID
        rid_bytes = await rid.read()
        dict_atuais = UERJExtractor.parse_rid(rid_bytes)

        # Processa Disciplinas e cria Turmas
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
            historico={}, # Histórico começa vazio
            periodo_atual=periodo_ref
        )

        res = await users_col.insert_one(new_user.model_dump(by_alias=True, exclude=["id"]))
        user_id = res.inserted_id
        
        # Matrícula Automática
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

# --- ROTA 2: MEU PERFIL (Protegida) ---
@router.get("/me", response_model=User, response_model_exclude={"senha_hash"})
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Retorna os dados do usuário logado baseado no Token"""
    return current_user

# --- ROTA 3: ENVIAR HISTÓRICO (Protegida) ---
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

        # Salva no banco
        await db.get_collection("users").update_one(
            {"_id": ObjectId(current_user.id)},
            {"$set": {"historico": historico_final}}
        )

        return {"message": "Histórico importado!", "semestres": list(historico_final.keys())}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Erro: {str(e)}")