# models.py

from pydantic import BaseModel, Field, ConfigDict, EmailStr, BeforeValidator
from typing import Optional, List, Dict, Annotated
from datetime import datetime
from enum import Enum

PyObjectId = Annotated[str, BeforeValidator(str)]

class MongoBaseModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True, json_encoders={datetime: lambda dt: dt.isoformat()})

# --- Auxiliares ---
class Feedback(BaseModel):
    user_id: PyObjectId
    nota: int = Field(ge=0, le=5)
    comentario: Optional[str] = None
    data: datetime = Field(default_factory=datetime.now)

class FeedbackInput(BaseModel):
    """O que o aluno envia"""
    nota: int = Field(..., ge=0, le=5, description="Nota de 0 a 5")
    comentario: Optional[str] = Field(None, max_length=500)
    # user_id e data serão inseridos pelo sistema

# --- 1. Usuários e Disciplinas (Mantidos do anterior) ---
class DisciplinaAluno(BaseModel):
    codigo: str
    nome: str
    turma: Optional[str] = None 
    horario: List[str] = []
    nota: Optional[float] = None
    status: str = "Cursando"
    disciplina_id: Optional[PyObjectId] = None

class Discipline(MongoBaseModel):
    codigo: str
    nome: str
    turma: str
    semestre: str
    horario: List[str] = []
    membros: List[PyObjectId] = [] 
    professor_id: Optional[PyObjectId] = None
    whatsapp_link: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

class User(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    nome: str
    email: EmailStr
    senha_hash: str
    role: str = "student" # <--- NOVO CAMPO (student ou admin)
    # periodo_atual: str = "2025.1"
    disciplinas_atuais: Dict[str, List[dict]] = {}
    historico: Dict[str, List[dict]] = {}
    periodo_atual: Optional[str] = None

# --- 2. Professores  ---
class Professor(MongoBaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    nome: str
    email: EmailStr
    departamento: str
    # Lista de CÓDIGOS de disciplinas que ele pode dar (ex: ["FEN06-05080", "MAT01..."])
    disciplinas_ofertadas: List[str] = [] 
    feedbacks: List[Feedback] = []
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        
# --- 3. Materiais (Estrutura de Repositório) ---
class MaterialTipo(str, Enum):
    PDF = "PDF"
    VIDEO = "VIDEO"
    SLIDE = "SLIDE"
    OUTRO = "OUTRO"
    LINK = "LINK"

class ArquivoMaterial(BaseModel):
    """Representa um arquivo individual dentro da pasta"""
    titulo: str
    url: str
    tipo: MaterialTipo = MaterialTipo.PDF
    aluno_autor_id: PyObjectId # Quem upou
    likes: int = 0
    data: datetime = Field(default_factory=datetime.now)

class MaterialRepository(MongoBaseModel):
    """
    Um documento único por CÓDIGO DE DISCIPLINA.
    Estrutura:
    {
       "codigo_disciplina": "FEN06-05080",
       "acervo": {
           "2025_1": {
               "ID_DO_PROFESSOR_A": [Arquivo1, Arquivo2],
               "ID_DO_PROFESSOR_B": [Arquivo3]
           },
           "2024_2": { ... }
       }
    }
    """
    codigo_disciplina: str
    # Dict[Semestre, Dict[ProfessorID, List[Arquivos]]]
    acervo: Dict[str, Dict[str, List[ArquivoMaterial]]] = {}

# --- 4. Avisos ---
class WarningType(str, Enum):
    GERAL = "geral"           # Para todo o site
    DISCIPLINA = "disciplina" # Para uma matéria específica
    URGENCIA = "urgencia"
    OPORTUNIDADE = "oportunidade" # Estágios, IC, etc.

class WarningModel(MongoBaseModel):
    tipo: WarningType
    disciplina_id: Optional[PyObjectId] = None
    autor_id: PyObjectId
    titulo: str
    mensagem: str
    validade: Optional[datetime] = None # Data para o aviso sumir (opcional)
    created_at: datetime = Field(default_factory=datetime.now)