import os

from pydantic import BaseModel, SecretStr


class Config(BaseModel):
    # ==================================================
    DEBUG: bool = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')
    BASE_DIR: str = os.path.dirname(os.path.dirname(__file__))
    # ==================================================
    DATABASE_HOST: str = os.getenv("POSTGRES_HOST", 'localhost')
    DATABASE_NAME: str = os.getenv("POSTGRES_DB", 'db_name')
    DATABASE_USER: str = os.getenv("POSTGRES_USER", 'user_db')
    DATABASE_PASSWORD: str = os.getenv('POSTGRES_PASSWORD', 'password')
    DATABASE_PORT: int = int(os.getenv("POSTGRES_PORT", 5432))
    DATABASE_URL: str = f'postgresql+asyncpg://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}'
    # ==================================================
    REDIS_HOST: str = os.getenv('REDIS_HOST', 'redis')
    REDIS_PORT: int = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB: int = int(os.getenv('REDIS_DB', 0))
    # ==================================================
    BANK_API_URL: str = "http://bank.api"
    BANK_API_TIMEOUT: int = 10

config = Config()