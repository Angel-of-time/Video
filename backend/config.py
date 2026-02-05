import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import validator

class Settings(BaseSettings):
    """Application settings"""
    
    # Server
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    workers: int = int(os.getenv("WORKERS", "2"))
    log_level: str = os.getenv("LOG_LEVEL", "info")
    
    # Security
    jwt_secret: str = os.getenv("JWT_SECRET", "change-in-production")
    token_expire_minutes: int = int(os.getenv("TOKEN_EXPIRE_MINUTES", "30"))
    cors_origins: List[str] = os.getenv("CORS_ORIGINS", "*").split(",")
    
    # Features
    has_ffmpeg: bool = os.getenv("HAS_FFMPEG", "true").lower() == "true"
    max_file_size_mb: int = int(os.getenv("MAX_FILE_SIZE_MB", "500"))
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
    
    # Redis
    redis_url: Optional[str] = os.getenv("REDIS_URL")
    
    # Rate limiting
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    rate_limit_per_hour: int = int(os.getenv("RATE_LIMIT_PER_HOUR", "1000"))
    
    # Domain
    domain: str = os.getenv("DOMAIN", "media.localhost")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    @validator("jwt_secret")
    def validate_jwt_secret(cls, v):
        if v == "change-in-production":
            import warnings
            warnings.warn(
                "JWT_SECRET is set to default value. Change it in production!",
                UserWarning
            )
        return v
    
    @validator("cors_origins")
    def validate_cors_origins(cls, v):
        if "*" in v and len(v) > 1:
            import warnings
            warnings.warn(
                "CORS_ORIGINS contains '*' along with other origins. '*' will override all others.",
                UserWarning
            )
        return v

# Global settings instance
settings = Settings()

# Export constants
HOST = settings.host
PORT = settings.port
WORKERS = settings.workers
LOG_LEVEL = settings.log_level
JWT_SECRET = settings.jwt_secret
TOKEN_EXPIRE_MINUTES = settings.token_expire_minutes
CORS_ORIGINS = settings.cors_origins
HAS_FFMPEG = settings.has_ffmpeg
MAX_FILE_SIZE_MB = settings.max_file_size_mb
CACHE_TTL_SECONDS = settings.cache_ttl_seconds
REDIS_URL = settings.redis_url
RATE_LIMIT_PER_MINUTE = settings.rate_limit_per_minute
RATE_LIMIT_PER_HOUR = settings.rate_limit_per_hour
DOMAIN = settings.domain