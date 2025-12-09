from fastapi import APIRouter, HTTPException, Body, Depends
from typing import List
from database import db
from models import Professor, Feedback, FeedbackInput, User
from security import get_current_user
from pymongo.errors import DuplicateKeyError
from bson import ObjectId

router = APIRouter()

# ==========================================
# 1. LISTAR PROFESSORES
# ==========================================
@router.get("/", response_model=List[Professor])
async def list_professors(
    search: str = None, 
    departamento: str = None,
    current_user: User = Depends(get_current_user)
):
    query = {}
    
    # Filtro por nome (case insensitive)
    if search:
        query["nome"] = {"$regex": search, "$options": "i"}
    
    if departamento:
        query["departamento"] = departamento
        
    # Retorna lista limitada a 100 para não pesar
    return await db.get_collection("professors").find(query).to_list(100)

# ==========================================
# 2. CADASTRAR PROFESSOR
# ==========================================
@router.post("/", response_model=Professor, status_code=201)
async def create_professor(
    professor: Professor,
    current_user: User = Depends(get_current_user)
):
    """
    Cadastra um novo professor.
    Aceita qualquer e-mail válido (Gmail, Hotmail, UERJ...),
    pois não há restrição de domínio aqui.
    """
    prof_col = db.get_collection("professors")

    # 1. Verifica duplicidade de E-mail manualmente para dar erro legível
    if await prof_col.find_one({"email": professor.email}):
        raise HTTPException(status_code=400, detail="Este e-mail já está cadastrado para outro professor.")

    try:
        # 2. Insere no banco
        # O model_dump já valida o formato do email se você usou EmailStr no models.py
        new_prof = await prof_col.insert_one(
            professor.model_dump(by_alias=True, exclude=["id"])
        )
        
        return await prof_col.find_one({"_id": new_prof.inserted_id})
        
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Professor duplicado no banco de dados.")
    except Exception as e:
        print(f"Erro ao criar professor: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao cadastrar professor.")

# ==========================================
# 3. ADICIONAR FEEDBACK
# ==========================================
@router.post("/{professor_id}/feedback")
async def add_feedback(
    professor_id: str, 
    feedback_in: FeedbackInput,
    current_user: User = Depends(get_current_user)
):
    """
    Adiciona nota e comentário à lista de feedbacks do professor.
    """
    prof_col = db.get_collection("professors")
    
    # Cria objeto de feedback vinculado ao usuário logado
    novo_feedback = Feedback(
        user_id=str(current_user.id), # Converte ID do usuário para string
        nota=feedback_in.nota,
        comentario=feedback_in.comentario
    )
    
    # Atualiza o documento do professor ($push adiciona ao array)
    result = await prof_col.update_one(
        {"_id": ObjectId(professor_id)},
        {"$push": {"feedbacks": novo_feedback.model_dump()}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(404, "Professor não encontrado.")
        
    return {"message": "Avaliação enviada com sucesso!"}