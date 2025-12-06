# main.py

from fastapi import FastAPI
from contextlib import asynccontextmanager
from database import db
import os
# Importe as novas rotas
from routes import auth, disciplines, professors, materials, warnings 
from fastapi.staticfiles import StaticFiles

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    
    # --- CRIAÇÃO DE ÍNDICES ---
    try:
        # 1. Usuários: Email único
        await db.db.users.create_index("email", unique=True)
        
        # 2. Disciplinas (Turmas): Código+Turma+Semestre único
        await db.db.disciplines.create_index(
            [("codigo", 1), ("turma", 1), ("semestre", 1)], 
            unique=True
        )
        
        # 3. Professores: Nome+Email+Departamento único (Índice Composto)
        await db.db.professors.create_index(
            [("nome", 1), ("email", 1), ("departamento", 1)],
            unique=True
        )
        
        # 4. Materiais: Código da disciplina único (pois é um repositório por matéria)
        await db.db.materials.create_index("codigo_disciplina", unique=True)
        
        print("🔒 Todos os índices configurados!")
    except Exception as e:
        print(f"⚠️ Erro ao criar índices: {e}")
        
    yield
    await db.close()

UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

app = FastAPI(title="UERJHUB API", lifespan=lifespan)

app.include_router(auth.router, prefix="/auth", tags=["Autenticação"])
app.include_router(disciplines.router, prefix="/disciplines", tags=["Turmas/Disciplinas"])
app.include_router(professors.router, prefix="/professors", tags=["Professores"])
app.include_router(materials.router, prefix="/materials", tags=["Materiais"])
app.include_router(warnings.router, prefix="/warnings", tags=["Avisos"])

app.mount("/arquivos", StaticFiles(directory=UPLOAD_DIR), name="arquivos")

@app.get("/")
def read_root():
    return {"message": "UERJHUB API is running!"}