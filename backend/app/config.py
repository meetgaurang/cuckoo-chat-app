"""Application configuration, sourced entirely from environment variables."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OpenRouter
    openrouter_api_key: str = ""
    openrouter_model: str = "google/gemma-4-31b-it:free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Optional attribution headers OpenRouter recommends (shown on their site).
    openrouter_referer: str = "http://localhost:3000"
    openrouter_title: str = "Cuckoo Chat"

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
