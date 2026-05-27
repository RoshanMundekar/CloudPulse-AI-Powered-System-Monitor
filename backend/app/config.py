"""
CloudPulse Configuration
Loads all environment variables and provides app-wide settings.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "CloudPulse"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://cloudpulse:cloudpulse123@localhost:5432/cloudpulse"
    DATABASE_SYNC_URL: str = "postgresql://cloudpulse:cloudpulse123@localhost:5432/cloudpulse"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 10  # seconds

    # Alerts thresholds
    CPU_ALERT_THRESHOLD: float = 85.0
    RAM_ALERT_THRESHOLD: float = 85.0
    DISK_ALERT_THRESHOLD: float = 90.0

    # ML Model
    MODEL_CONTAMINATION: float = 0.05  # 5% anomaly rate assumption
    MODEL_RETRAIN_INTERVAL: int = 3600  # retrain every 1 hour

    # Security — optional API key the monitoring agent must send
    # Leave empty ("") to disable auth in development
    AGENT_API_KEY: str = ""

    # CORS
    ALLOWED_ORIGINS: list = ["http://localhost:3000", "http://localhost:5173"]

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
