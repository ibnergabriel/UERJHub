from fastapi import APIRouter, HTTPException, Depends, Body
from typing import List
from bson import ObjectId
from database import db
from models import Discipline, User
from security import get_current_user

router = APIRouter()

# 1. LISTAR MINHAS TURMAS (Para a tela de seleção)
@router.get("/mine", response_model=List[Discipline])
async def get_my_disciplines(current_user: User = Depends(get_current_user)):
    try:
        coll = db.get_collection("disciplines")
        disciplinas = await coll.find({
            "membros": ObjectId(current_user.id),
            "semestre": current_user.periodo_atual
        }).to_list(100)
        return disciplinas
    except Exception as e:
        print(f"Erro: {e}")
        raise HTTPException(500, "Erro ao buscar turmas.")

# 2. PEGAR DETALHES DE UMA TURMA (Para o Painel da Turma) - NOVA ROTA
@router.get("/{discipline_id}", response_model=Discipline)
async def get_discipline_details(discipline_id: str, current_user: User = Depends(get_current_user)):
    try:
        coll = db.get_collection("disciplines")
        # Busca pelo ID e garante que o aluno é membro
        turma = await coll.find_one({
            "_id": ObjectId(discipline_id),
            "membros": ObjectId(current_user.id)
        })
        
        if not turma:
            raise HTTPException(404, "Turma não encontrada ou acesso negado.")
            
        return turma
    except Exception:
        raise HTTPException(400, "ID Inválido.")

# 3. ATUALIZAR WHATSAPP
@router.patch("/{discipline_id}")
async def update_discipline_info(
    discipline_id: str,
    whatsapp_link: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user)
):
    coll = db.get_collection("disciplines")
    turma = await coll.find_one({
        "_id": ObjectId(discipline_id),
        "membros": ObjectId(current_user.id)
    })
    
    if not turma:
        raise HTTPException(404, "Erro ao atualizar.")
    
    await coll.update_one(
        {"_id": ObjectId(discipline_id)},
        {"$set": {"whatsapp_link": whatsapp_link}}
    )
    return {"message": "Link atualizado!"}