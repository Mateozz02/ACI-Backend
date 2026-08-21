from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    openwa_api_url: str = "http://localhost:2785"
    openwa_api_key: str = ""
    openwa_session_name: str = ""

    database_url: str = "postgresql+asyncpg://orderflow:orderflow123@localhost:5432/orderflow"
    database_url_sync: str = "postgresql://orderflow:orderflow123@localhost:5432/orderflow"

    redis_url: str = "redis://localhost:6379"

    llm_provider: str = "gemini"
    opencode_api_key: str = ""
    opencode_base_url: str = "https://opencode.ai/zen/v1"
    model_name: str = "deepseek-v4-flash-free"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    response_style: str = "human"  # "human" (templates variados) or "structured" (formato actual)
    llm_timeout_seconds: float = 15.0

    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7

    pending_order_ttl_minutes: int = 720  # 12h — how long a pending unconfirmed order stays in Redis

    def model_post_init(self, _context) -> None:
        if not self.jwt_secret_key:
            raise ValueError("JWT_SECRET_KEY must be set in environment")

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = True

    cors_origins: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
