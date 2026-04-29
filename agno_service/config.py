from __future__ import annotations

import json
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
  app_name: str = Field(default='PPTist Agno Service', alias='AGNO_APP_NAME')
  host: str = Field(default='127.0.0.1', alias='AGNO_HOST')
  port: int = Field(default=8000, alias='AGNO_PORT')

  model_provider: str = Field(default='ollama', alias='AGNO_MODEL_PROVIDER')
  ollama_host: str = Field(default='http://127.0.0.1:11434', alias='AGNO_OLLAMA_HOST')
  openai_api_key: str = Field(default='', alias='AGNO_OPENAI_API_KEY')
  openai_base_url: str | None = Field(default=None, alias='AGNO_OPENAI_BASE_URL')
  default_model: str = Field(default='qwen2.5:3b', alias='AGNO_DEFAULT_MODEL')
  model_aliases_raw: str = Field(
    default='{"glm-4.7-flash":"qwen2.5:3b","doubao-seed-1.6-flash":"qwen2.5:3b"}',
    alias='AGNO_MODEL_ALIASES',
  )

  request_timeout: float = Field(default=120.0, alias='AGNO_REQUEST_TIMEOUT')
  max_retries: int = Field(default=2, alias='AGNO_MAX_RETRIES')
  stream_chunk_size: int = Field(default=48, alias='AGNO_STREAM_CHUNK_SIZE')
  cors_origins: str = Field(
    default='http://127.0.0.1:5173,http://localhost:5173',
    alias='AGNO_CORS_ORIGINS',
  )

  model_config = SettingsConfigDict(
    env_file=('agno_service/.env', '.env'),
    env_file_encoding='utf-8',
    extra='ignore',
    populate_by_name=True,
  )

  @property
  def model_aliases(self) -> dict[str, str]:
    try:
      data = json.loads(self.model_aliases_raw)
    except json.JSONDecodeError:
      return {}

    if not isinstance(data, dict):
      return {}

    return {
      str(key).strip(): str(value).strip()
      for key, value in data.items()
      if str(key).strip() and str(value).strip()
    }

  @property
  def cors_origin_list(self) -> list[str]:
    return [origin.strip() for origin in self.cors_origins.split(',') if origin.strip()]

  @property
  def normalized_model_provider(self) -> str:
    return self.model_provider.strip().lower() or 'ollama'


@lru_cache(maxsize=1)
def get_settings() -> Settings:
  return Settings()