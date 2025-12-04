import jwt
from datetime import datetime, timedelta
from bson import ObjectId

SECRET_KEY = "CHAVE_SUPER_SECRETA"
ALGORITHM = "HS256"
EXPIRE_MINUTES = 60

def criar_jwt(usuario_id, email: str) -> str:

    # Converte ObjectId para string automaticamente
    if isinstance(usuario_id, ObjectId):
        usuario_id = str(usuario_id)

    payload = {
        "sub": usuario_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(minutes=EXPIRE_MINUTES),
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
