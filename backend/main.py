from fastapi import FastAPI
from contextlib import asynccontextmanager
from database import db
from routes import auth

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializa conexão ao iniciar o app
    await db.connect()
    yield
    # Fecha conexão ao desligar
    await db.close()

app = FastAPI(title="UERJHUB API", lifespan=lifespan)

# Registrar rotas
app.include_router(auth.router, prefix="/auth", tags=["Autenticação"])

@app.get("/")
def read_root():
    return {"message": "UERJHUB API is running!"}