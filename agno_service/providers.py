from __future__ import annotations

import json
from typing import Any, Iterator

from agno.agent import Agent
from agno.models.ollama import Ollama
from agno.models.openai import OpenAIChat
from agno.run.agent import RunContentEvent
from pydantic import BaseModel

from .config import Settings


class AgnoProviderGateway:
  def __init__(self, settings: Settings):
    self.settings = settings

  def resolve_model_name(self, requested_model: str | None) -> str:
    model_name = (requested_model or '').strip()
    if model_name and model_name in self.settings.model_aliases:
      return self.settings.model_aliases[model_name]
    if model_name:
      return model_name
    return self.settings.default_model

  def build_model(self, requested_model: str | None, temperature: float = 0.3):
    model_name = self.resolve_model_name(requested_model)
    provider = self.settings.normalized_model_provider

    if provider == 'ollama':
      return Ollama(
        id=model_name,
        host=self.settings.ollama_host,
        options={
          'temperature': temperature,
        },
        timeout=self.settings.request_timeout,
      )

    if provider == 'openai':
      return OpenAIChat(
        id=model_name,
        api_key=self.settings.openai_api_key or None,
        base_url=self.settings.openai_base_url or None,
        temperature=temperature,
        timeout=self.settings.request_timeout,
        max_retries=self.settings.max_retries,
      )

    raise ValueError(f'不支持的模型提供方: {self.settings.model_provider}')

  def ensure_backend_ready(self) -> None:
    provider = self.settings.normalized_model_provider

    if provider == 'openai' and not self.settings.openai_api_key:
      raise ValueError('当前 provider=openai，但缺少 AGNO_OPENAI_API_KEY。')

    if provider not in ('ollama', 'openai'):
      raise ValueError('AGNO_MODEL_PROVIDER 仅支持 ollama 或 openai。')

  def build_agent(
    self,
    *,
    requested_model: str | None,
    temperature: float,
    instructions: list[str],
    expected_output: str,
  ) -> Agent:
    return Agent(
      name='PPTist Agno Agent',
      model=self.build_model(requested_model, temperature=temperature),
      instructions=instructions,
      expected_output=expected_output,
      markdown=False,
      add_datetime_to_context=True,
    )

  @staticmethod
  def extract_model_payload(run_output: Any) -> dict[str, Any]:
    content = getattr(run_output, 'content', None)
    if isinstance(content, BaseModel):
      return content.model_dump(exclude_none=True)
    if isinstance(content, dict):
      return content
    if isinstance(content, str):
      return json.loads(content)
    raise ValueError('Agno 返回了无法识别的结构化结果')

  @staticmethod
  def iter_run_content(agent: Agent, prompt: str, *, raise_on_empty: bool = True) -> Iterator[str]:
    emitted = False

    for event in agent.run(input=prompt, stream=True):
      event_name = getattr(event, 'event', '')
      event_content = getattr(event, 'content', None)

      if event_name == 'RunError':
        raise ValueError(str(event_content or '模型流式输出失败'))

      if isinstance(event, RunContentEvent) and event_content:
        emitted = True
        yield str(event_content)

    if raise_on_empty and not emitted:
      raise ValueError('模型未返回任何内容')