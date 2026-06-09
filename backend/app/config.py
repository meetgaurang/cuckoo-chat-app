"""Application configuration, sourced entirely from environment variables.

AWS credentials are intentionally NOT defined here — boto3 resolves them from
the standard provider chain (env vars, shared profile, instance role, etc.).
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # AWS / Bedrock
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "google.gemma-3-4b-it"

    # Inference params
    max_tokens: int = 1024
    temperature: float = 0.7

    # Default system prompt (overridable per-request)
    system_prompt: str = "You are Cuckoo, a concise and helpful AI assistant."

    # CORS — origin of the frontend dev server. In the docker setup nginx
    # proxies /api to the backend so this is only needed for local dev.
    allowed_origin: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
