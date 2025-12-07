# services/utils.py
from database import db

async def get_system_semester() -> str:
    """
    Retorna o semestre ativo configurado pelo Admin (ex: '2025.1').
    Se der erro ou não achar, retorna um fallback seguro.
    """
    try:
        config = await db.get_collection("system_config").find_one({"key": "semestre_ativo"})
        if config and "valor" in config:
            return config["valor"]
        return "2025.2" # Fallback
    except Exception as e:
        print(f"Erro ao buscar semestre: {e}")
        return "2025.2"