from pydantic import BaseModel

class AlunoResponse(BaseModel):
    id: str
    nome: str
    email: str
