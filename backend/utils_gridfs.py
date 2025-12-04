from bson import ObjectId
from database import fs_bucket
from fastapi.responses import StreamingResponse

async def salvar_pdf(nome_arquivo: str, dados: bytes) -> str:
    file_id = await fs_bucket.upload_from_stream(nome_arquivo, dados)
    return str(file_id)

async def obter_pdf(file_id: str):
    stream = await fs_bucket.open_download_stream(ObjectId(file_id))
    return stream
