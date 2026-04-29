from __future__ import annotations

import json
from typing import Any, Iterator

from .config import Settings
from .protocol import RuntimeCommand, RuntimeEvent
from .providers import AgnoProviderGateway
from .schemas import (
  AIPPTOutlineRequest,
  AIPPTRequest,
  AIWritingRequest,
  OutlineDocument,
  SlideDeckDocument,
  WritingDocument,
)


class HeadlessRuntime:
  def __init__(self, settings: Settings, providers: AgnoProviderGateway):
    self.settings = settings
    self.providers = providers

  def run(self, command: RuntimeCommand) -> Iterator[RuntimeEvent]:
    runtime_command = self._resolve_command(command)
    yield RuntimeEvent(
      command=runtime_command.command,
      type='run.started',
      payload={'context': runtime_command.context.model_dump(exclude_none=True)},
    )

    if runtime_command.command == 'outline.generate':
      yield from self._run_outline(runtime_command)
    elif runtime_command.command == 'deck.generate':
      yield from self._run_deck(runtime_command)
    elif runtime_command.command == 'writing.rewrite':
      yield from self._run_writing(runtime_command)
    else:
      raise ValueError(f'不支持的运行时命令: {runtime_command.command}')

    yield RuntimeEvent(
      command=runtime_command.command,
      type='run.completed',
      payload={'context': runtime_command.context.model_dump(exclude_none=True)},
    )

  def iter_outline_chunks(self, command: RuntimeCommand) -> Iterator[str]:
    for event in self.run(command):
      if event.type == 'outline.chunk':
        chunk = event.payload.get('chunk')
        if isinstance(chunk, str):
          yield chunk

  def iter_slides(self, command: RuntimeCommand) -> Iterator[dict[str, Any]]:
    for event in self.run(command):
      if event.type == 'slide.generated':
        slide = event.payload.get('slide')
        if isinstance(slide, dict):
          yield slide

  def iter_text_chunks(self, command: RuntimeCommand) -> Iterator[str]:
    for event in self.run(command):
      if event.type == 'text.chunk':
        chunk = event.payload.get('chunk')
        if isinstance(chunk, str):
          yield chunk

  def generate_outline_document(self, payload: AIPPTOutlineRequest) -> OutlineDocument:
    agent = self.providers.build_agent(
      requested_model=payload.model,
      temperature=0.4,
      instructions=[
        '你是 PPTist 的演示文稿策划助手。',
        f'输出语言必须使用 {payload.language}。',
        '请围绕用户主题生成适合演示文稿的大纲。',
        '大纲必须包含 4 到 6 个章节，每章 2 到 4 个小节，每个小节 2 到 4 个要点。',
        '标题要具体，不要空泛重复，不要输出免责声明。',
        '只返回与输出 schema 一致的结构化数据。',
      ],
      expected_output='返回主题标题和章节大纲，便于转换成 Markdown 大纲。',
    )
    result = agent.run(
      input=f'请为以下主题生成演示文稿大纲：\n{payload.content.strip()}',
      output_schema=OutlineDocument,
    )
    return OutlineDocument.model_validate(self.providers.extract_model_payload(result))

  def stream_outline_markdown(self, payload: AIPPTOutlineRequest) -> Iterator[str]:
    agent = self.providers.build_agent(
      requested_model=payload.model,
      temperature=0.4,
      instructions=[
        '你是 PPTist 的演示文稿策划助手。',
        f'输出语言必须使用 {payload.language}。',
        '请围绕用户主题生成适合演示文稿的大纲。',
        '请直接输出 Markdown，不要返回 JSON。',
        'Markdown 格式必须严格使用：一级标题使用 "# "，章节使用 "## "，小节使用 "### "，要点使用 "- "。',
        '大纲必须包含 4 到 6 个章节，每章 2 到 4 个小节，每个小节 2 到 4 个要点。',
        '标题要具体，不要空泛重复，不要输出免责声明，不要输出代码块标记。',
      ],
      expected_output='返回 Markdown 大纲文本。',
    )

    prompt = f'请为以下主题生成演示文稿大纲：\n{payload.content.strip()}'
    yield from self.providers.iter_run_content(agent, prompt)

  def generate_slide_document(self, payload: AIPPTRequest) -> SlideDeckDocument:
    slide_targets = get_outline_slide_targets(payload.content)
    agent = self.providers.build_agent(
      requested_model=payload.model,
      temperature=0.5,
      instructions=[
        '你是 PPTist 的 AIPPT 结构化生成助手。',
        f'输出语言必须使用 {payload.language}。',
        f'整体文风参考：{payload.style}。',
        '请把用户提供的 Markdown 大纲转换为 PPTist 所需的结构化幻灯片数据。',
        '必须生成一页 cover、一页 contents、每章一页 transition、若干页 content，最后一页 end。',
        f'当前大纲共有 {slide_targets["chapter_count"]} 个章节、{slide_targets["section_count"]} 个小节。',
        '每个 ## 章节必须对应 1 页 transition。',
        '每个 ### 小节至少对应 1 页 content，不要把不同小节合并到同一页。',
        '如果某个章节没有 ### 小节，仍然要为该章节输出 1 页 content。',
        'content 页每页保留 2 到 4 个内容项，每个内容项都要包含 title 和 text。',
        'transition 页的 text 用一句话概括本章内容。',
        'contents 页只保留章节标题。',
        '只返回与输出 schema 一致的结构化数据。',
      ],
      expected_output='返回 PPTist 幻灯片列表，供前端逐页消费。',
    )
    result = agent.run(
      input=f'请根据以下 Markdown 大纲生成演示文稿：\n{payload.content.strip()}',
      output_schema=SlideDeckDocument,
    )
    return SlideDeckDocument.model_validate(self.providers.extract_model_payload(result))

  def generate_writing_document(self, payload: AIWritingRequest) -> WritingDocument:
    agent = self.providers.build_agent(
      requested_model=payload.model,
      temperature=0.6,
      instructions=[
        '你是 PPTist 的文案优化助手。',
        '根据用户给出的命令改写文本。',
        '只返回纯文本内容，不要使用 Markdown，不要解释过程。',
        '保持原意，不要编造事实。',
      ],
      expected_output='返回改写后的纯文本。',
    )
    result = agent.run(
      input=f'改写指令：{payload.command}\n\n原文：\n{payload.content.strip()}',
      output_schema=WritingDocument,
    )
    return WritingDocument.model_validate(self.providers.extract_model_payload(result))

  def _resolve_command(self, command: RuntimeCommand) -> RuntimeCommand:
    resolved_model = self.providers.resolve_model_name(command.context.requested_model)
    context = command.context.model_copy(update={'resolved_model': resolved_model})
    return command.model_copy(update={'context': context})

  def _run_outline(self, command: RuntimeCommand) -> Iterator[RuntimeEvent]:
    payload = AIPPTOutlineRequest(
      content=str(command.input.get('content') or ''),
      language=command.context.language,
      model=command.context.requested_model,
      stream=True,
    )
    for chunk in self.stream_outline_markdown(payload):
      yield RuntimeEvent(
        command=command.command,
        type='outline.chunk',
        payload={'chunk': chunk},
      )

  def _run_deck(self, command: RuntimeCommand) -> Iterator[RuntimeEvent]:
    payload = AIPPTRequest(
      content=str(command.input.get('content') or ''),
      language=command.context.language,
      style=command.context.style or '通用',
      model=command.context.requested_model,
      stream=True,
    )
    for slide in self.stream_deck_slides(payload):
      yield RuntimeEvent(
        command=command.command,
        type='slide.generated',
        payload={'slide': slide},
      )

  def _run_writing(self, command: RuntimeCommand) -> Iterator[RuntimeEvent]:
    payload = AIWritingRequest(
      content=str(command.input.get('content') or ''),
      command=command.context.command_text or '',
      model=command.context.requested_model,
      stream=True,
    )
    document = self.generate_writing_document(payload)
    for chunk in chunk_text(document.content.strip(), self.settings.stream_chunk_size):
      yield RuntimeEvent(
        command=command.command,
        type='text.chunk',
        payload={'chunk': chunk},
      )

  def stream_deck_slides(self, payload: AIPPTRequest) -> Iterator[dict[str, Any]]:
    slide_targets = get_outline_slide_targets(payload.content)
    agent = self.providers.build_agent(
      requested_model=payload.model,
      temperature=0.5,
      instructions=[
        '你是 PPTist 的 AIPPT 幻灯片生成助手。',
        f'输出语言必须使用 {payload.language}。',
        f'整体文风参考：{payload.style}。',
        '请把用户提供的 Markdown 大纲转换为 PPTist 前端可直接消费的幻灯片数据。',
        '请严格按 NDJSON 输出，每个 slide 输出一行 JSON，对象之间不要放在数组里，不要输出代码块，不要解释。',
        '服务端会自行补充 cover、contents、end。你只需要输出 transition 和 content 两种 type。',
        '每个对象必须是最终格式：transition 使用 data.title 和 data.text；content 使用 data.title 和 data.items，其中 items 为 2 到 4 个 {title, text}。',
        f'当前大纲共有 {slide_targets["chapter_count"]} 个章节、{slide_targets["section_count"]} 个小节。',
        f'transition 和 content 合计至少输出 {slide_targets["minimum_streamed_slide_count"]} 页。',
        '输出顺序必须是：每章先 transition，再按该章的小节顺序输出 content。',
        '每个 ## 章节必须对应 1 页 transition。',
        '每个 ### 小节至少对应 1 页 content，不要把不同小节合并到同一页。',
        '如果某个章节没有 ### 小节，仍然要为该章节输出 1 页 content。',
        '如果单个小节信息过多，可以继续拆成 2 到 3 页 content，但不能少于上述最低页数。',
        '字符串内容保持单行，不要在 JSON 字符串中输出真实换行。',
      ],
      expected_output='按 NDJSON 逐页输出 PPTist 幻灯片对象。',
    )

    has_cover = False
    has_contents = False
    has_end = False
    streamed_slide_count = 0

    def emit_slide(slide: dict[str, Any]) -> Iterator[dict[str, Any]]:
      nonlocal has_cover, has_contents, has_end
      slide_type = slide['type']

      if slide_type == 'cover':
        if has_cover:
          return
        has_cover = True
      elif slide_type == 'contents':
        if not has_cover:
          has_cover = True
          yield build_default_cover_slide(payload.content, payload.language)
        if has_contents:
          return
        has_contents = True
      elif slide_type != 'end':
        if not has_cover:
          has_cover = True
          yield build_default_cover_slide(payload.content, payload.language)
        if not has_contents:
          has_contents = True
          yield build_default_contents_slide(payload.content)
      else:
        if has_end:
          return
        if not has_cover:
          has_cover = True
          yield build_default_cover_slide(payload.content, payload.language)
        if not has_contents:
          has_contents = True
          yield build_default_contents_slide(payload.content)
        has_end = True

      yield slide

    def iter_content_chunks() -> Iterator[str]:
      prompt = f'请根据以下 Markdown 大纲生成演示文稿：\n{payload.content.strip()}'
      yield from self.providers.iter_run_content(agent, prompt, raise_on_empty=False)

    yield from emit_slide(build_default_cover_slide(payload.content, payload.language))
    yield from emit_slide(build_default_contents_slide(payload.content))

    for raw_object in parse_streamed_json_objects(iter_content_chunks()):
      try:
        parsed_slide = json.loads(raw_object)
      except json.JSONDecodeError:
        continue

      slide = normalize_stream_slide(parsed_slide, payload.content, payload.language)
      if not slide:
        continue

      if slide['type'] in ('cover', 'contents', 'end'):
        continue

      streamed_slide_count += 1
      yield from emit_slide(slide)

    if streamed_slide_count == 0:
      document = self.generate_slide_document(payload)
      slides = normalize_slides(document, payload.content, payload.language)
      skipped_cover = False
      skipped_contents = False
      for slide in slides:
        slide_type = slide['type']
        if slide_type == 'cover' and not skipped_cover:
          skipped_cover = True
          continue
        if slide_type == 'contents' and not skipped_contents:
          skipped_contents = True
          continue
        if slide_type == 'end':
          has_end = True
        yield slide

    if not has_end:
      yield from emit_slide({'type': 'end'})


def chunk_text(text: str, chunk_size: int) -> Iterator[str]:
  normalized_chunk_size = max(chunk_size, 1)
  if not text:
    yield ''
    return

  for index in range(0, len(text), normalized_chunk_size):
    yield text[index:index + normalized_chunk_size]


def parse_streamed_json_objects(chunks: Iterator[str]) -> Iterator[str]:
  current_chars: list[str] = []
  object_depth = 0
  in_string = False
  is_escaped = False

  for chunk in chunks:
    for char in chunk:
      if object_depth == 0:
        if char != '{':
          continue
        current_chars = ['{']
        object_depth = 1
        in_string = False
        is_escaped = False
        continue

      current_chars.append(char)

      if in_string:
        if is_escaped:
          is_escaped = False
        elif char == '\\':
          is_escaped = True
        elif char == '"':
          in_string = False
        continue

      if char == '"':
        in_string = True
      elif char == '{':
        object_depth += 1
      elif char == '}':
        object_depth -= 1
        if object_depth == 0:
          yield ''.join(current_chars)
          current_chars = []


def normalize_stream_slide(raw_slide: dict[str, Any], outline_markdown: str, language: str) -> dict[str, Any] | None:
  if not isinstance(raw_slide, dict):
    return None

  parsed_outline = parse_outline_markdown(outline_markdown)
  chapter_titles = [chapter['title'] for chapter in parsed_outline['chapters'] if chapter.get('title')]
  slide_type = str(raw_slide.get('type') or '').strip()
  data = raw_slide.get('data') if isinstance(raw_slide.get('data'), dict) else {}

  if slide_type == 'cover':
    title = str(data.get('title') or raw_slide.get('title') or parsed_outline['title']).strip()
    text = str(data.get('text') or raw_slide.get('text') or fallback_cover_text(parsed_outline['title'], language)).strip()
    return {
      'type': 'cover',
      'data': {
        'title': title,
        'text': text,
      }
    }

  if slide_type == 'contents':
    raw_items = data.get('items') if isinstance(data.get('items'), list) else raw_slide.get('bullet_items')
    items: list[str] = []
    for item in raw_items or []:
      if isinstance(item, dict):
        item_title = str(item.get('title') or '').strip()
        if item_title:
          items.append(item_title)
      else:
        item_text = str(item).strip()
        if item_text:
          items.append(item_text)
    return {
      'type': 'contents',
      'data': {
        'items': items or chapter_titles,
      }
    }

  if slide_type == 'transition':
    title = str(data.get('title') or raw_slide.get('title') or '').strip()
    text = str(data.get('text') or raw_slide.get('text') or '').strip()
    if not title:
      return None
    return {
      'type': 'transition',
      'data': {
        'title': title,
        'text': text or fallback_cover_text(title, language),
      }
    }

  if slide_type == 'content':
    title = str(data.get('title') or raw_slide.get('title') or '').strip()
    raw_items = data.get('items') if isinstance(data.get('items'), list) else raw_slide.get('content_items')
    items: list[dict[str, str]] = []
    for item in raw_items or []:
      if not isinstance(item, dict):
        continue
      item_title = str(item.get('title') or '').strip()
      item_text = str(item.get('text') or '').strip()
      if item_title and item_text:
        items.append({
          'title': item_title,
          'text': item_text,
        })
      if len(items) >= 4:
        break

    if not title or not items:
      return None

    return {
      'type': 'content',
      'data': {
        'title': title,
        'items': items,
      }
    }

  if slide_type == 'end':
    return {'type': 'end'}

  return None


def build_default_cover_slide(outline_markdown: str, language: str) -> dict[str, Any]:
  parsed_outline = parse_outline_markdown(outline_markdown)
  return {
    'type': 'cover',
    'data': {
      'title': parsed_outline['title'],
      'text': fallback_cover_text(parsed_outline['title'], language),
    }
  }


def build_default_contents_slide(outline_markdown: str) -> dict[str, Any]:
  parsed_outline = parse_outline_markdown(outline_markdown)
  chapter_titles = [chapter['title'] for chapter in parsed_outline['chapters'] if chapter.get('title')]
  return {
    'type': 'contents',
    'data': {
      'items': chapter_titles,
    }
  }


def parse_outline_markdown(markdown: str) -> dict[str, Any]:
  title = ''
  chapters: list[dict[str, Any]] = []
  current_chapter: dict[str, Any] | None = None
  current_section: dict[str, Any] | None = None

  for raw_line in markdown.splitlines():
    line = raw_line.strip()
    if not line:
      continue

    if line.startswith('# '):
      title = line[2:].strip()
      continue

    if line.startswith('## '):
      current_chapter = {'title': line[3:].strip(), 'sections': []}
      chapters.append(current_chapter)
      current_section = None
      continue

    if line.startswith('### '):
      if current_chapter is None:
        current_chapter = {'title': '核心内容', 'sections': []}
        chapters.append(current_chapter)
      current_section = {'title': line[4:].strip(), 'bullets': []}
      current_chapter['sections'].append(current_section)
      continue

    if line.startswith('- '):
      if current_chapter is None:
        current_chapter = {'title': '核心内容', 'sections': []}
        chapters.append(current_chapter)
      if current_section is None:
        current_section = {'title': '核心要点', 'bullets': []}
        current_chapter['sections'].append(current_section)
      current_section['bullets'].append(line[2:].strip())

  return {
    'title': title or 'AI 生成演示文稿',
    'chapters': chapters,
  }


def get_outline_slide_targets(markdown: str) -> dict[str, int]:
  parsed_outline = parse_outline_markdown(markdown)
  chapter_count = len(parsed_outline['chapters'])
  section_count = sum(len(chapter.get('sections') or []) for chapter in parsed_outline['chapters'])
  minimum_streamed_slide_count = sum(
    1 + max(len(chapter.get('sections') or []), 1)
    for chapter in parsed_outline['chapters']
  )

  return {
    'chapter_count': chapter_count,
    'section_count': section_count,
    'minimum_streamed_slide_count': minimum_streamed_slide_count,
  }


def render_outline_markdown(document: OutlineDocument) -> str:
  lines = [f'# {document.title.strip()}']

  for chapter in document.chapters:
    lines.append(f'## {chapter.title.strip()}')
    for section in chapter.sections:
      lines.append(f'### {section.title.strip()}')
      bullets = [bullet.strip() for bullet in section.bullets if bullet.strip()]
      for bullet in bullets[:4]:
        lines.append(f'- {bullet}')

  return '\n'.join(lines)


def fallback_cover_text(title: str, language: str) -> str:
  if language.lower().startswith('english'):
    return f'This presentation focuses on {title} and highlights the key context, structure, and action points.'
  if language.lower().startswith('日本語'):
    return f'{title} をテーマに、背景、構成、実践ポイントを分かりやすく整理します。'
  return f'围绕 {title} 展开，梳理背景、结构与关键行动建议。'


def normalize_slides(document: SlideDeckDocument, outline_markdown: str, language: str) -> list[dict[str, Any]]:
  parsed_outline = parse_outline_markdown(outline_markdown)
  chapter_titles = [chapter['title'] for chapter in parsed_outline['chapters'] if chapter.get('title')]

  slides: list[dict[str, Any]] = []

  for slide in document.slides:
    slide_type = slide.type

    if slide_type == 'cover':
      slides.append({
        'type': 'cover',
        'data': {
          'title': (slide.title or parsed_outline['title']).strip(),
          'text': (slide.text or fallback_cover_text(parsed_outline['title'], language)).strip(),
        }
      })
    elif slide_type == 'contents':
      items = [item.strip() for item in slide.bullet_items if item.strip()]
      slides.append({
        'type': 'contents',
        'data': {
          'items': items or chapter_titles,
        }
      })
    elif slide_type == 'transition':
      title = (slide.title or '').strip()
      text = (slide.text or '').strip()
      if title:
        slides.append({
          'type': 'transition',
          'data': {
            'title': title,
            'text': text or fallback_cover_text(title, language),
          }
        })
    elif slide_type == 'content':
      items = []
      for item in slide.content_items[:4]:
        item_title = item.title.strip()
        item_text = item.text.strip()
        if item_title and item_text:
          items.append({'title': item_title, 'text': item_text})

      title = (slide.title or '').strip()
      if title and items:
        slides.append({
          'type': 'content',
          'data': {
            'title': title,
            'items': items,
          }
        })
    elif slide_type == 'end':
      slides.append({'type': 'end'})

  if not slides or slides[0]['type'] != 'cover':
    slides.insert(0, {
      'type': 'cover',
      'data': {
        'title': parsed_outline['title'],
        'text': fallback_cover_text(parsed_outline['title'], language),
      }
    })

  if chapter_titles:
    has_contents = any(slide['type'] == 'contents' for slide in slides)
    if not has_contents:
      slides.insert(1, {
        'type': 'contents',
        'data': {
          'items': chapter_titles,
        }
      })

  if not slides or slides[-1]['type'] != 'end':
    slides.append({'type': 'end'})

  return slides