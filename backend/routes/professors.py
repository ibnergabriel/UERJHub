from fastapi import APIRouter, HTTPException, Body, Depends
from typing import List
from database import db
from models import Professor, Feedback, FeedbackInput, User
from security import get_current_user
from pymongo.errors import DuplicateKeyError
from bson import ObjectId

router = APIRouter()

# 1. LISTAR PROFESSORES (Com filtro opcional)
@router.get("/", response_model=List[Professor])
async def list_professors(
    search: str = None, 
    departamento: str = None,
    current_user: User = Depends(get_current_user)
):
    query = {}
    
    # Filtro simples por nome (case insensitive)
    if search:
        query["nome"] = {"$regex": search, "$options": "i"}
    
    if departamento:
        query["departamento"] = departamento
        
    return await db.get_collection("professors").find(query).to_list(100)

# 2. CADASTRAR PROFESSOR (Manualmente)
@router.post("/", response_model=Professor, status_code=201)
async def create_professor(
    professor: Professor,
    current_user: User = Depends(get_current_user)
):
    """
    Cadastra um novo professor.
    O índice único no banco (Nome+Email+Dept) impede duplicatas.
    """
    try:
        prof_col = db.get_collection("professors")
        
        # Insere (feedbacks começa vazio por padrão no model)
        new_prof = await prof_col.insert_one(
            professor.model_dump(by_alias=True, exclude=["id"])
        )
        
        return await prof_col.find_one({"_id": new_prof.inserted_id})
        
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Professor já cadastrado com estes dados.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 3. ADICIONAR FEEDBACK (Avaliação)
@router.post("/{professor_id}/feedback")
async def add_feedback(
    professor_id: str, 
    feedback_in: FeedbackInput,
    current_user: User = Depends(get_current_user)
):
    """
    Adiciona nota e comentário.
    O user_id vem do Token (seguro).
    """
    prof_col = db.get_collection("professors")
    
    # Monta o objeto Feedback interno
    novo_feedback = Feedback(
        user_id=current_user.id,
        nota=feedback_in.nota,
        comentario=feedback_in.comentario
    )
    
    # Adiciona na lista 'feedbacks' do professor
    result = await prof_col.update_one(
        {"_id": ObjectId(professor_id)},
        {"$push": {"feedbacks": novo_feedback.model_dump()}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(404, "Professor não encontrado.")
        
    return {"message": "Avaliação enviada com sucesso!"}