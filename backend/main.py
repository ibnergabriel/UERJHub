from fastapi import FastAPI
from routes.alunos import router as alunos_router
from routes.rid import router as rid_router

app = FastAPI(title="Sistema RID - Faculdade")

app.include_router(alunos_router)
app.include_router(rid_router)

@app.get("/")
def root():
    return {"msg": "API da Faculdade funcionando!"}
