from fastapi import APIRouter, HTTPException
from database import alunos_collection
from models import Aluno
from schemas import AlunoResponse
from auth_jwt import criar_jwt

router = APIRouter(prefix="/alunos", tags=["Alunos"])

# CREATE
@router.post("/", response_model=AlunoResponse)
async def criar_aluno(aluno: Aluno):
    existente = await alunos_collection.find_one({"email": aluno.email})
    if existente:
        raise HTTPException(400, "Email já cadastrado")

    result = await alunos_collection.insert_one(aluno.dict())

    return {
        "id": str(result.inserted_id),
        "nome": aluno.nome,
        "email": aluno.email
    }

# LISTAR
@router.get("/")
async def listar_alunos():
    alunos = await alunos_collection.find({}).to_list(100)
    return alunos

# LOGIN
@router.post("/login")
async def login(email: str):
    aluno = await alunos_collection.find_one({"email": email})
    if not aluno:
        raise HTTPException(401, "Email não encontrado")

    token = criar_jwt(aluno["_id"], email)

    return {"token": token}
