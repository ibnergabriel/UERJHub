from pydantic import BaseModel

class Aluno(BaseModel):
    nome: str
    email: str
