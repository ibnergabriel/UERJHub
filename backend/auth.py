from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from auth_jwt import SECRET_KEY, ALGORITHM
from database import alunos_collection

token_auth = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(token_auth)):
    token = credentials.credentials

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("email")

        user = await alunos_collection.find_one({"email": email})
        if not user:
            raise HTTPException(401, "Usuário não encontrado")

        return user

    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expirado")
    except:
        raise HTTPException(401, "Token inválido")
