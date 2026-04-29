from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from .schemas import AIPPTOutlineRequest, AIPPTRequest, AIWritingRequest


RuntimeCommandName = Literal['outline.generate', 'deck.generate', 'writing.rewrite']
RuntimeEventName = Literal['run.started', 'outline.chunk', 'slide.generated', 'text.chunk', 'run.completed']


class RuntimeContext(BaseModel):
  request_id: str = Field(default_factory=lambda: f'run_{uuid4().hex[:12]}')
  language: str = '中文'
  style: str | None = None
  command_text: str | None = None
  requested_model: str | None = None
  resolved_model: str | None = None


class RuntimeCommand(BaseModel):
  version: str = 'v1'
  command: RuntimeCommandName
  context: RuntimeContext
  input: dict[str, Any] = Field(default_factory=dict)


class RuntimeEvent(BaseModel):
  version: str = 'v1'
  command: RuntimeCommandName
  type: RuntimeEventName
  payload: dict[str, Any] = Field(default_factory=dict)


def build_outline_command(payload: AIPPTOutlineRequest) -> RuntimeCommand:
  return RuntimeCommand(
    command='outline.generate',
    context=RuntimeContext(
      language=payload.language,
      requested_model=payload.model,
    ),
    input={
      'content': payload.content,
    },
  )


def build_deck_command(payload: AIPPTRequest) -> RuntimeCommand:
  return RuntimeCommand(
    command='deck.generate',
    context=RuntimeContext(
      language=payload.language,
      style=payload.style,
      requested_model=payload.model,
    ),
    input={
      'content': payload.content,
    },
  )


def build_writing_command(payload: AIWritingRequest) -> RuntimeCommand:
  return RuntimeCommand(
    command='writing.rewrite',
    context=RuntimeContext(
      command_text=payload.command,
      requested_model=payload.model,
    ),
    input={
      'content': payload.content,
    },
  )