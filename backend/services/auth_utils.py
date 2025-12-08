# backend/services/auth_utils.py
import secrets
from datetime import datetime, timedelta
from typing import List

from core.config import conf  # Importa a configuração que criamos acima
from database import db
from fastapi_mail import FastMail, MessageSchema, MessageType

# --- Constantes ---
DOMINIOS_VALIDOS = [ "@graduacao.uerj.br", "@uerj.br"]
VERIFICATION_COLLECTION = "verification_tokens"
TOKEN_EXPIRATION_MINUTES = 15

# Inicializa o enviador de e-mail
fm = FastMail(conf)

def validar_dominio_graduacao(email: str) -> bool:
    """Verifica se o email termina com um dos domínios permitidos."""
    email = email.lower().strip()
    return any(email.endswith(dom) for dom in DOMINIOS_VALIDOS)

def generate_six_digit_token() -> str:
    """Gera token numérico de 6 dígitos seguro."""
    return str(secrets.randbelow(1000000)).zfill(6)

async def save_token_to_db(email: str, token: str):
    """Salva o token no Mongo com data de expiração."""
    coll = db.get_collection(VERIFICATION_COLLECTION)
    expiration = datetime.now() + timedelta(minutes=TOKEN_EXPIRATION_MINUTES)
    
    # Upsert: Se já existe token pra esse email, atualiza. Se não, cria.
    await coll.update_one(
        {"email": email},
        {"$set": {
            "token": token,
            "expires_at": expiration,
            "created_at": datetime.now()
        }},
        upsert=True
    )

async def send_validation_email(email: str, token: str):
    """Envia o e-mail usando o Mailtrap."""
    html = f"""
    <div style="font-family: Arial; padding: 20px; color: #333;">
        <h2>Bem-vindo ao UERJHUB</h2>
        <p>Seu código de verificação é:</p>
        <h1 style="background: #eee; padding: 10px; display: inline-block; border-radius: 5px;">{token}</h1>
        <p>Este código expira em {TOKEN_EXPIRATION_MINUTES} minutos.</p>
    </div>
    """

    message = MessageSchema(
        subject="Seu Código de Acesso UERJHUB",
        recipients=[email],
        body=html,
        subtype=MessageType.html
    )

    await fm.send_message(message)

async def verify_and_delete_token(email: str, token: str) -> bool:
    """Verifica se o token bate e não expirou. Se ok, deleta."""
    coll = db.get_collection(VERIFICATION_COLLECTION)
    now = datetime.now()
    
    # Busca token que bate email, código e DATA DE EXPIRAÇÃO > AGORA
    record = await coll.find_one({
        "email": email,
        "token": token,
        "expires_at": {"$gt": now}
    })
    
    if record:
        # Token válido! Deletar para não ser usado de novo
        await coll.delete_one({"_id": record["_id"]})
        return True
    return False

async def send_reset_password_email(email: str, token: str):
    """Envia o e-mail de redefinição de senha."""
    html = f"""
    <div style="font-family: Arial; padding: 20px; color: #333; border: 1px solid #ddd; border-radius: 8px;">
        <h2 style="color: #d9534f;">Recuperação de Senha</h2>
        <p>Recebemos uma solicitação para alterar sua senha no UERJHUB.</p>
        <p>Seu código de segurança é:</p>
        <h1 style="background: #fdf2f2; padding: 10px; display: inline-block; border-radius: 5px; color: #d9534f; letter-spacing: 5px;">{token}</h1>
        <p>Se você não solicitou essa alteração, ignore este e-mail. Sua senha permanecerá a mesma.</p>
        <p><small>Este código expira em {TOKEN_EXPIRATION_MINUTES} minutos.</small></p>
    </div>
    """

    message = MessageSchema(
        subject="Redefinir Senha - UERJHUB",
        recipients=[email],
        body=html,
        subtype=MessageType.html
    )

    await fm.send_message(message)