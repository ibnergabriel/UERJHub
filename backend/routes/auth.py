import bcrypt
import traceback
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from typing import List, Dict
from services.extractor import UERJExtractor
from database import db
from models import User, Discipline, DisciplinaAluno

router = APIRouter()

async def get_global_id(codigo: str, nome: str) -> str:
    """Busca ou cria disciplina no banco global para pegar o _id"""
    try:
        coll = db.get_collection("disciplines")
        found = await coll.find_one({"codigo": codigo})
        if found: return str(found["_id"])
        
        new_d = Discipline(nome=nome, codigo=codigo)
        res = await coll.insert_one(new_d.model_dump(by_alias=True, exclude=["id"]))
        return str(res.inserted_id)
    except:
        return None

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

        # 1. EXTRAÇÃO DOS PDFs
        rid_bytes = await rid.read()
        hist_bytes = await historico.read()

        # dict_atuais = { "2025.2": [...] }
        dict_atuais = UERJExtractor.parse_rid(rid_bytes)
        
        # dict_hist = { "2020.1": [...], "2020.2": [...] }
        dict_hist = UERJExtractor.parse_historico(hist_bytes)

        # 2. PROCESSAMENTO (Adicionar IDs globais e validar Modelos)
        async def processar_dict(dados_raw: Dict):
            resultado = {}
            for semestre, lista in dados_raw.items():
                objs_semestre = []
                for item in lista:
                    gid = await get_global_id(item["codigo"], item["nome"])
                    
                    d_obj = DisciplinaAluno(
                        codigo=item["codigo"],
                        nome=item["nome"],
                        horario=item["horario"],
                        nota=item["nota"],
                        status=item["status"],
                        disciplina_id=gid
                    )
                    objs_semestre.append(d_obj)
                resultado[semestre] = objs_semestre
            return resultado

        # Processa as duas listas separadamente
        atuais_final = await processar_dict(dict_atuais)
        historico_final = await processar_dict(dict_hist)

        # 3. CRIAÇÃO DO USUÁRIO
        hashed = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()
        
        new_user = User(
            nome=nome,
            email=email,
            senha_hash=hashed,
            disciplinas_atuais=atuais_final,  # <--- Vai para o campo específico
            historico=historico_final         # <--- Vai para o campo específico
        )

        res = await users_col.insert_one(new_user.model_dump(by_alias=True, exclude=["id"]))
        return await users_col.find_one({"_id": res.inserted_id})

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Erro interno: {str(e)}")