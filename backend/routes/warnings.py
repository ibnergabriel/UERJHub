from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from database import db
from models import WarningModel, WarningType, User
from security import get_current_user

router = APIRouter()

# CRIAR AVISO (Serve tanto para Geral quanto para Turma)
@router.post("/", response_model=WarningModel)
async def create_warning(
    aviso: WarningModel,
    current_user: User = Depends(get_current_user)
):
    # O backend garante que o autor é quem está logado
    aviso.autor_id = current_user.id 
    
    new_aviso = await db.get_collection("warnings").insert_one(
        aviso.model_dump(by_alias=True, exclude=["id"])
    )
    return await db.get_collection("warnings").find_one({"_id": new_aviso.inserted_id})

# LISTAR AVISOS (Com Filtros)
@router.get("/", response_model=List[WarningModel])
async def list_warnings(
    tipo: Optional[str] = None, # geral, oportunidade, disciplina...
    disciplina_id: Optional[str] = None
):
    query = {}
    
    if disciplina_id:
        # Se passou ID da disciplina, traz só avisos daquela turma
        query["disciplina_id"] = disciplina_id
        query["tipo"] = "disciplina"
    elif tipo:
        # Se passou tipo (ex: geral), traz aquele tipo E garante que NÃO é de disciplina
        query["tipo"] = tipo
        # query["disciplina_id"] = None # Opcional: garantir que não é de turma
    else:
        # Se não passou nada, traz apenas os GERAIS e OPORTUNIDADES (Padrão do mural)
        query["tipo"] = {"$in": ["geral", "urgencia", "oportunidade"]}

    # Retorna ordenado por data (mais recente primeiro)
    return await db.get_collection("warnings").find(query).sort("created_at", -1).to_list(100)