# backend/routes/login.py

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from security import verify_password, create_access_token
from database import db

router = APIRouter()

@router.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Rota de Login.
    Recebe 'username' (que será o email) e 'password'.
    Retorna o Token JWT.
    """
    # 1. Busca o usuário pelo email (O campo username do form contém o email)
    user = await db.get_collection("users").find_one({"email": form_data.username})
    
    # 2. Verifica se usuário existe E se a senha está certa
    if not user or not verify_password(form_data.password, user["senha_hash"]):
        raise HTTPException(
            status_code=400, 
            detail="Email ou senha incorretos"
        )
    
    # 3. Gera o token com o email dele dentro
    access_token = create_access_token(data={"sub": user["email"]})
    
    return {"access_token": access_token, "token_type": "bearer"}