from pydantic import BaseModel

class Settings(BaseModel):
    MONGO_URI: str = "mongodb://localhost:27017"
    JWT_SECRET: str = "supersegredo"
    JWT_EXPIRE_MIN: int = 60 * 24

settings = Settings()
