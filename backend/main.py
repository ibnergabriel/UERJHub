import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Carrega variáveis antes de tudo
load_dotenv()

from database import db
# Importa todas as rotas que criamos
from routes import auth, disciplines, login, materials, professors, warnings, admin

# Cria pasta de uploads se não existir
UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)


# Configuração do Banco ao iniciar/desligar
@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    # Criação de índices para garantir unicidade
    try:
        await db.db.users.create_index("email", unique=True)
        await db.db.disciplines.create_index([("codigo", 1), ("turma", 1), ("semestre", 1)], unique=True)
        await db.db.professors.create_index([("nome", 1), ("email", 1), ("departamento", 1)], unique=True)
        print("🔒 Índices configurados!")
    except Exception as e:
        print(f"⚠️ Aviso índices: {e}")
        
    yield
    await db.close()

app = FastAPI(title="UERJHUB API", lifespan=lifespan)


# Configuração de CORS (Permitir que o HTML acesse a API)
origins = ["*"] # Em produção, coloque o domínio exato

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- REGISTRO DE ROTAS ---

# 1. Login (Gera Token) - Fica na raiz /token
app.include_router(login.router, tags=["Login"])

# 2. Auth (Cadastro, Perfil, Histórico) - Prefixo /auth
app.include_router(auth.router, prefix="/auth", tags=["Autenticação"])

# 3. Outras funcionalidades
app.include_router(disciplines.router, prefix="/disciplines", tags=["Turmas"])
app.include_router(professors.router, prefix="/professors", tags=["Professores"])
app.include_router(materials.router, prefix="/materials", tags=["Materiais"])
app.include_router(warnings.router, prefix="/warnings", tags=["Avisos"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])


# 4. Arquivos Estáticos (Para baixar os PDFs upados)
app.mount("/arquivos", StaticFiles(directory=UPLOAD_DIR), name="arquivos")

@app.get("/")
def read_root():
    return {"message": "UERJHUB API is running!"}