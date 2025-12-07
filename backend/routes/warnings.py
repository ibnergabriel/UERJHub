from fastapi import APIRouter, HTTPException, Depends, Body
from typing import List, Optional
from database import db
from models import WarningModel, User
from security import get_current_user
from bson import ObjectId
from datetime import datetime

router = APIRouter()

# --- ROTA POST: CRIAR AVISO ---
@router.post("/", response_model=WarningModel, status_code=201)
async def create_warning(
    warning: WarningModel, 
    current_user: User = Depends(get_current_user) # <--- Pega o usuário do Token
):
    try:
        # 1. Transforma o modelo em dicionário
        warning_dict = warning.model_dump(by_alias=True, exclude={"id"})
        
        # 2. O PULO DO GATO: Sobrescreve o "temp" pelo ID real do usuário logado
        warning_dict["autor_id"] = str(current_user.id)
        
        # 3. Adiciona data de criação se não tiver
        if "created_at" not in warning_dict or not warning_dict["created_at"]:
            warning_dict["created_at"] = datetime.now()

        # 4. Salva no Banco
        new_warning = await db.get_collection("warnings").insert_one(warning_dict)
        
        # 5. Retorna o objeto criado
        created_warning = await db.get_collection("warnings").find_one({"_id": new_warning.inserted_id})
        return created_warning

    except Exception as e:
        print(f"Erro ao criar aviso: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao salvar aviso")


# --- ROTA GET: LISTAR AVISOS COM NOME ---
@router.get("/", response_model=List[dict]) 
async def list_warnings(
    tipo: Optional[str] = None, 
    disciplina_id: Optional[str] = None
):
    query = {}
    
    # Filtros
    if disciplina_id:
        query["disciplina_id"] = disciplina_id
        query["tipo"] = "disciplina"
    elif tipo:
        query["tipo"] = tipo
    else:
        query["tipo"] = {"$in": ["geral", "urgencia", "oportunidade"]}

    # Busca no banco (Mais recentes primeiro)
    avisos = await db.get_collection("warnings").find(query).sort("created_at", -1).to_list(100)
    
    users_col = db.get_collection("users")
    resultado_final = []

    for aviso in avisos:
        # Converte para dict python
        aviso_dict = dict(aviso)
        
        # Arruma o ID do aviso
        if "_id" in aviso_dict:
            aviso_dict["id"] = str(aviso_dict.pop("_id"))
        
        # --- BUSCA O NOME DO AUTOR ---
        autor_nome = "Anônimo"
        autor_id = aviso_dict.get("autor_id")

        if autor_id and autor_id != "temp":
            try:
                # Verifica se é um ObjectId válido antes de buscar
                if ObjectId.is_valid(autor_id):
                    user = await users_col.find_one({"_id": ObjectId(autor_id)})
                    if user:
                        autor_nome = user.get("nome", "Usuário")
            except Exception as e:
                print(f"Erro ao buscar autor {autor_id}: {e}")
        
        # Adiciona o nome ao objeto de resposta
        aviso_dict["autor_nome"] = autor_nome
        
        resultado_final.append(aviso_dict)

    return resultado_final