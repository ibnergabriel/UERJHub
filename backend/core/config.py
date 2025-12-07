# backend/core/config.py
import os

from dotenv import load_dotenv
from fastapi_mail import ConnectionConfig

# Carrega as variáveis do .env imediatamente
load_dotenv()

# Configuração do FastMail usando as variáveis de ambiente
conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM", "admin@uerjhub.com"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", 2525)),
    MAIL_SERVER=os.getenv("MAIL_SERVER"),
    MAIL_STARTTLS=False,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)