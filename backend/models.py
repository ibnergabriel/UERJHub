from pydantic import BaseModel, Field, ConfigDict, EmailStr, BeforeValidator
from typing import Optional, List, Dict, Annotated, Any
from datetime import datetime
from enum import Enum

# 1. Helper para lidar com ObjectId do MongoDB no Pydantic v2
# Isso transforma o ObjectId em string quando enviamos o JSON para o frontend
PyObjectId = Annotated[str, BeforeValidator(str)]

class MongoBaseModel(BaseModel):
    """Classe base para configurar o mapeamento de _id para id"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={datetime: lambda dt: dt.isoformat()}
    )

# --- Sub-modelos (usados dentro de outros documentos) ---

class Feedback(BaseModel):
    user_id: PyObjectId
    nota: int = Field(ge=0, le=5) # Nota entre 0 e 5
    comentario: Optional[str] = None
    data: datetime = Field(default_factory=datetime.now)

# --- Modelos das Coleções Principais ---

# 1. Usuários (Alunos)
class DisciplinaAluno(BaseModel):
    codigo: str              # Ex: FEN06-05080
    nome: str                # Ex: Controle de Processos (Sem o lixo "4 75...")
    horario: List[str] = []  # Preenchido apenas nas atuais
    nota: Optional[float] = None # Preenchido apenas no histórico
    status: str = "Cursando" # Cursando, Aprovado, Reprovado
    disciplina_id: Optional[PyObjectId] = None # Link para o banco geral

# Modelo do Usuário
class User(MongoBaseModel):
    nome: str
    email: EmailStr
    senha_hash: str
    
    # FORMATO: { "2025.1": [ { ...disciplina... }, { ... } ] }
    disciplinas_atuais: Dict[str, List[DisciplinaAluno]] = {} 
    
    # FORMATO: { "2020.2": [...], "2021.1": [...] }
    historico: Dict[str, List[DisciplinaAluno]] = {}          
    
    periodo_atual: str = "2025.1" # Controle interno
    created_at: datetime = Field(default_factory=datetime.now)
    
# 2. Professores
class Professor(MongoBaseModel):
    nome: str
    departamento: str
    tags: List[str] = [] # Ex: ["calculo", "didatico"]
    feedbacks: List[Feedback] = [] # Lista de sub-documentos

# 3. Disciplinas
class Discipline(MongoBaseModel):
    nome: str
    codigo: str # Ex: MAT101
    professor_id: Optional[PyObjectId] = Field(default=None, alias="professor")
    whatsapp_link: Optional[str] = None
    classroom_link: Optional[str] = None
    quadro_aviso: List[str] = [] # Pode ser lista de strings ou IDs de avisos
    created_at: datetime = Field(default_factory=datetime.now)

# 4. Materiais
class MaterialTipo(str, Enum):
    PDF = "PDF"
    VIDEO = "VIDEO"
    SLIDE = "SLIDE"
    OUTRO = "OUTRO"

class Material(MongoBaseModel):
    disciplina_id: PyObjectId
    titulo: str
    url: str
    tipo: MaterialTipo = MaterialTipo.PDF
    tags_professor: List[str] = [] # Ex: ["importante", "p1"]
    data: datetime = Field(default_factory=datetime.now)

# 5. Avisos
class WarningType(str, Enum):
    GERAL = "geral"
    DISCIPLINA = "disciplina"
    URGENCIA = "urgencia"
    OPORTUNIDADE = "oportunidade"

class WarningModel(MongoBaseModel):
    tipo: WarningType
    disciplina_id: Optional[PyObjectId] = None # Null se for aviso geral da UERJ
    autor_id: PyObjectId # Quem criou o aviso
    titulo: str
    mensagem: str
    created_at: datetime = Field(default_factory=datetime.now)