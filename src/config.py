from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    openwa_api_url: str = "http://localhost:2785"
    openwa_api_key: str = "owa_k1_004b17f2b1c55b048be270ed5ca456443c5b2027b8e98acf18a182377aedef13"

    database_url: str = "postgresql+asyncpg://orderflow:orderflow123@localhost:5432/orderflow"
    database_url_sync: str = "postgresql://orderflow:orderflow123@localhost:5432/orderflow"

    redis_url: str = "redis://localhost:6379"

    llm_provider: str = "opencode"
    opencode_api_key: str = "sk-your-opencode-api-key"
    opencode_base_url: str = "https://opencode.ai/zen/v1"
    model_name: str = "deepseek-v4-flash-free"

    jwt_secret_key: str = "dev-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = True

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
