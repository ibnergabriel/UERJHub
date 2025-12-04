from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket

MONGO_URL = "mongodb://localhost:27017"

client = AsyncIOMotorClient(MONGO_URL)
db = client["faculdade"]

alunos_collection = db["alunos"]

# GridFS assíncrono correto
fs_bucket = AsyncIOMotorGridFSBucket(db)
