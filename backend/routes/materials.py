import shutil
import os
import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
from database import db
from models import MaterialRepository, ArquivoMaterial, MaterialTipo

router = APIRouter()

# Configuração local (deve ser igual ao main.py)
UPLOAD_DIR = "uploads"

@router.post("/{codigo_disciplina}/upload")
async def upload_material(
    codigo_disciplina: str,
    semestre: str = Form(...),      # Form(...) é usado quando enviamos arquivos junto
    professor_id: str = Form(...),
    titulo: str = Form(...),
    tipo: MaterialTipo = Form(...), # PDF, SLIDE, etc.
    aluno_id: str = Form(...),
    file: UploadFile = File(...)    # <--- O ARQUIVO BINÁRIO VEM AQUI
):
    """
    Recebe um arquivo (PDF, PPT, etc), salva na pasta /uploads
    e registra o caminho no banco de dados.
    """
    # 1. Validação simples de extensão (Opcional)
    # Garante que o usuário não suba um .exe ou script malicioso
    allowed_extensions = {".pdf", ".pptx", ".ppt", ".docx", ".doc", ".zip", ".png", ".jpg"}
    filename_lower = file.filename.lower()
    
    # Pega a extensão (ex: .pdf)
    ext = os.path.splitext(filename_lower)[1]
    
    if ext not in allowed_extensions:
        raise HTTPException(400, f"Extensão {ext} não permitida. Use PDF, PPTX, DOCX ou Imagem.")

    # 2. Gerar nome único para o arquivo (UUID)
    # Ex: a1b2c3d4-1234.pdf
    novo_nome = f"{uuid.uuid4()}{ext}"
    caminho_arquivo = os.path.join(UPLOAD_DIR, novo_nome)

    # 3. Salvar no Disco
    try:
        with open(caminho_arquivo, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(500, f"Erro ao salvar arquivo: {e}")

    # 4. Gerar a URL Pública
    # No frontend, você usará: http://localhost:8000/arquivos/{novo_nome}
    url_final = f"/arquivos/{novo_nome}"

    # 5. Salvar metadados no MongoDB
    mat_col = db.get_collection("materials")
    semestre_key = semestre.replace(".", "_") # Mongo não aceita ponto em chave
    
    novo_arquivo_obj = ArquivoMaterial(
        titulo=titulo,
        url=url_final, # Salva o caminho relativo
        tipo=tipo,
        aluno_autor_id=aluno_id
    )
    
    mongo_path = f"acervo.{semestre_key}.{professor_id}"

    # Atualiza o repositório da disciplina
    await mat_col.update_one(
        {"codigo_disciplina": codigo_disciplina},
        {"$push": {mongo_path: novo_arquivo_obj.model_dump()}},
        upsert=True
    )

    return {
        "message": "Upload realizado com sucesso!",
        "url": url_final,
        "filename": novo_nome
    }

@router.get("/{codigo_disciplina}", response_model=MaterialRepository)
async def get_materials(codigo_disciplina: str):
    """Retorna todo o acervo daquela disciplina"""
    repo = await db.get_collection("materials").find_one({"codigo_disciplina": codigo_disciplina})
    if not repo:
        raise HTTPException(404, "Nenhum material encontrado.")
    return repo