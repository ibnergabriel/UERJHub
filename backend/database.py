import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient

# Configuração de Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = "uerjhub_db"
# Valor padrão caso o banco esteja vazio
DEFAULT_SEMESTER = "2025.2" 

class Database:
    client: AsyncIOMotorClient = None
    db = None

    @classmethod
    async def connect(cls):
        try:
            cls.client = AsyncIOMotorClient(MONGO_URL)
            cls.db = cls.client[DB_NAME]
            
            await cls.db.command("ping")
            logger.info(f"✅ Conectado ao MongoDB: {DB_NAME}")

            # --- INICIALIZAÇÃO AUTOMÁTICA DO SEMESTRE ---
            await cls._init_system_config()

        except Exception as e:
            logger.error(f"❌ Erro ao conectar no MongoDB: {e}")
            cls.db = None

    @classmethod
    async def _init_system_config(cls):
        """
        Garante que exista um semestre ativo configurado no banco.
        Usa $setOnInsert para não sobrescrever se o Admin já tiver mudado.
        """
        try:
            col = cls.db["system_config"]
            # Tenta encontrar e criar se não existir
            await col.update_one(
                {"key": "semestre_ativo"},
                {"$setOnInsert": {"valor": DEFAULT_SEMESTER}},
                upsert=True
            )
            # Log para debug
            doc = await col.find_one({"key": "semestre_ativo"})
            logger.info(f"📅 Semestre do Sistema: {doc.get('valor')}")
                
        except Exception as e:
            logger.warning(f"⚠️ Erro ao verificar config inicial: {e}")

    @classmethod
    async def close(cls):
        if cls.client:
            cls.client.close()
            logger.info("❌ Conexão fechada.")

    @classmethod
    def get_collection(cls, name):
        if cls.db is None:
            raise Exception("Banco não conectado!")
        return cls.db[name]

db = Database