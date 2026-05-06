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
    # 是否在 review 前拉取被审项目仓库中的 .md 文档作为 LLM 上下文
    project_docs_enabled: bool = True
    # 拉取的 .md 文件数量上限（按优先级取前 N 个）
    project_docs_max_files: int = 20
    # 单文件 utf-8 字节上限，超出时按字符截断并标记 truncated
    project_docs_max_bytes_per_file: int = 8192
    # 项目文档总字节上限，达到此上限即停止后续拉取
    project_docs_max_total_bytes: int = 60000

    model_config = SettingsConfigDict(env_file='.env', env_prefix='', extra='ignore')


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
