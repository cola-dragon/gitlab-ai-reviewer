from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    gitlab_base_url: str = 'https://gitlab.example.com'
    gitlab_token: str = 'dev-token'
    gitlab_webhook_secret: str = 'dev-secret'
    auto_review_enabled: bool = True
    openai_base_url: str = 'https://api.openai.com/v1'
    openai_api_key: str = 'dev-openai-key'
    openai_model: str = 'gpt-5.4'
    openai_api_style: str = 'chat_completions'
    openai_structured_output_mode: str = 'json_schema'
    prompt_dir: Path = Path('prompts')
    request_timeout_seconds: float = 120.0

    model_config = SettingsConfigDict(env_file='.env', env_prefix='', extra='ignore')


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
