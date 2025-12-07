import os
from motor.motor_asyncio import AsyncIOMotorClient

# Configuração
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = "uerjhub_db"

class Database:
    client: AsyncIOMotorClient = None
    db = None

    @classmethod
    async def connect(cls):
        try:
            cls.client = AsyncIOMotorClient(MONGO_URL)
            cls.db = cls.client[DB_NAME]
            # Teste rápido de conexão
            await cls.db.command("ping")
            print(f"✅ Conectado ao MongoDB: {DB_NAME}")
        except Exception as e:
            print(f"❌ Erro ao conectar no MongoDB: {e}")
            cls.db = None

    @classmethod
    async def close(cls):
        if cls.client:
            cls.client.close()
            print("❌ Conexão com MongoDB fechada.")

    # Helper para pegar a collection com segurança
    @classmethod
    def get_collection(cls, name):
        if cls.db is None:
            raise Exception("Banco de dados não conectado! Verifique se o MongoDB está rodando.")
        return cls.db[name]

db = Database