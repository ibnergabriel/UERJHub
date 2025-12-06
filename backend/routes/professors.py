from fastapi import APIRouter, HTTPException, Body
from typing import List
from database import db
from models import Professor, Feedback, FeedbackInput
from pymongo.errors import DuplicateKeyError

router = APIRouter()

@router.post("/", response_model=Professor, status_code=201)
async def create_professor(professor: Professor):
    """
    Cadastra um professor manualmente.
    O índice único (Nome + Email + Dept) impedirá duplicatas.
    """
    try:
        prof_col = db.get_collection("professors")
        
        # Tenta inserir
        new_prof = await prof_col.insert_one(professor.model_dump(by_alias=True, exclude=["id"]))
        
        return await prof_col.find_one({"_id": new_prof.inserted_id})
        
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Professor já cadastrado com este Nome/Email/Departamento.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[Professor])
async def list_professors(departamento: str = None, disciplina: str = None):
    """Filtra professores por departamento ou código de disciplina ofertada"""
    query = {}
    if departamento:
        query["departamento"] = departamento
    if disciplina:
        query["disciplinas_ofertadas"] = disciplina # Busca no array
        
    return await db.get_collection("professors").find(query).to_list(100)

@router.put("/{prof_id}/disciplines")
async def add_discipline_to_professor(prof_id: str, disciplina_codigo: str = Body(..., embed=True)):
    """Adiciona uma nova disciplina à lista do professor"""
    from bson import ObjectId
    
    result = await db.get_collection("professors").update_one(
        {"_id": ObjectId(prof_id)},
        {"$addToSet": {"disciplinas_ofertadas": disciplina_codigo}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(404, "Professor não encontrado ou disciplina já existe.")
        
    return {"message": "Disciplina adicionada com sucesso."}

@router.post("/{professor_id}/feedback")
async def add_feedback(
    professor_id: str, 
    feedback: FeedbackInput,
    user_id: str = Body(..., embed=True) # Em produção, pegaria do Token JWT
):
    """
    Adiciona uma avaliação ao professor.
    """
    prof_col = db.get_collection("professors")
    
    # 1. Monta o objeto completo
    novo_feedback = Feedback(
        user_id=user_id,
        nota=feedback.nota,
        comentario=feedback.comentario
    )
    
    # 2. Insere na lista 'feedbacks' do professor
    result = await prof_col.update_one(
        {"_id": ObjectId(professor_id)},
        {"$push": {"feedbacks": novo_feedback.model_dump()}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(404, "Professor não encontrado.")
        
    return {"message": "Avaliação enviada com sucesso!"}