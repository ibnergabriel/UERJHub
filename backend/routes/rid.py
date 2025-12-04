from fastapi import APIRouter, UploadFile, HTTPException, Depends
from auth import get_current_user
from utils_gridfs import salvar_pdf, obter_pdf
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/rid", tags=["RID"])

@router.post("/upload")
async def upload_rid(file: UploadFile, user=Depends(get_current_user)):
    if file.content_type != "application/pdf":
        raise HTTPException(400, "Envie apenas PDF")

    dados = await file.read()
    file_id = await salvar_pdf(file.filename, dados)

    return {"mensagem": "Upload OK", "id_pdf": file_id}


@router.get("/download/{id_pdf}")
async def download_rid(id_pdf: str, user=Depends(get_current_user)):
    stream = await obter_pdf(id_pdf)

    return StreamingResponse(stream, media_type="application/pdf")
