# backend/security.py

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import bcrypt # Usando o que já funcionou pra você
from database import db
from models import User

# CONFIGURAÇÕES (Em produção, use variáveis de ambiente .env)
SECRET_KEY = "sua_chave_super_secreta_e_aleatoria_aqui"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 # Token dura 1 hora

# Isso diz ao FastAPI: "Para pegar o token, vá na rota /token"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha bate com o hash do banco"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict):
    """Gera o Token JWT com validade"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Função DEPOLICE (Guarda).
    Ela intercepta a requisição, lê o token, e descobre quem é o usuário.
    Se o token for falso ou expirado, ela bloqueia o acesso (Erro 401).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas ou token expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Tenta decodificar o token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_email: str = payload.get("sub") # O email está guardado no campo 'sub'
        if user_email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Busca o usuário no banco
    user = await db.get_collection("users").find_one({"email": user_email})
    if user is None:
        raise credentials_exception
        
    # Retorna o objeto User completo (agora sabemos quem ele é!)
    return User(**user)