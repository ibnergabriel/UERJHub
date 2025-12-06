from fastapi import APIRouter, HTTPException
from typing import List, Optional
from database import db
from models import WarningModel, WarningType
from bson import ObjectId

router = APIRouter()

@router.post("/", response_model=WarningModel)
async def create_warning(aviso: WarningModel):
    new_aviso = await db.get_collection("warnings").insert_one(
        aviso.model_dump(by_alias=True, exclude=["id"])
    )
    return await db.get_collection("warnings").find_one({"_id": new_aviso.inserted_id})

@router.get("/", response_model=List[WarningModel])
async def list_warnings(tipo: Optional[WarningType] = None, disciplina_id: Optional[str] = None):
    query = {}
    if tipo:
        query["tipo"] = tipo
    if disciplina_id:
        query["disciplina_id"] = disciplina_id # Busca avisos específicos
    
    # Ordena por data (mais recentes primeiro)
    return await db.get_collection("warnings").find(query).sort("created_at", -1).to_list(50)