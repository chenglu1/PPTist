from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AIPPTOutlineRequest(BaseModel):
  content: str
  language: str = '中文'
  model: str | None = None
  stream: bool = True


class AIPPTRequest(BaseModel):
  content: str
  language: str = '中文'
  style: str = '通用'
  model: str | None = None
  stream: bool = True


class AIWritingRequest(BaseModel):
  content: str
  command: str
  model: str | None = None
  stream: bool = True


class OutlineSection(BaseModel):
  title: str = Field(description='小节标题，简洁明确。')
  bullets: list[str] = Field(
    default_factory=list,
    description='该小节下的 2 到 4 个要点，单条不超过 18 个字或 12 个英文单词。',
  )


class OutlineChapter(BaseModel):
  title: str = Field(description='章节标题，适合目录页展示。')
  sections: list[OutlineSection] = Field(default_factory=list)


class OutlineDocument(BaseModel):
  title: str = Field(description='整份演示文稿的主题标题。')
  chapters: list[OutlineChapter] = Field(default_factory=list)


class SlideContentItem(BaseModel):
  title: str = Field(description='单个内容项的小标题。')
  text: str = Field(description='对该内容项的说明，1 到 2 句话。')


class SlideSchema(BaseModel):
  type: Literal['cover', 'contents', 'transition', 'content', 'end']
  title: str | None = None
  text: str | None = None
  bullet_items: list[str] = Field(default_factory=list)
  content_items: list[SlideContentItem] = Field(default_factory=list)


class SlideDeckDocument(BaseModel):
  slides: list[SlideSchema] = Field(default_factory=list)


class WritingDocument(BaseModel):
  content: str = Field(description='改写后的正文，只返回纯文本。')