from __future__ import annotations

import json
import logging
from time import perf_counter
from typing import Any, Iterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .config import Settings, get_settings
from .protocol import build_deck_command, build_outline_command, build_writing_command
from .providers import AgnoProviderGateway
from .runtime import HeadlessRuntime
from .schemas import AIPPTOutlineRequest, AIPPTRequest, AIWritingRequest


logger = logging.getLogger('uvicorn.error')


def create_app(settings: Settings | None = None) -> FastAPI:
  resolved_settings = settings or get_settings()
  providers = AgnoProviderGateway(resolved_settings)
  runtime = HeadlessRuntime(resolved_settings, providers)

  app = FastAPI(title=resolved_settings.app_name)
  app.add_middleware(
    CORSMiddleware,
    allow_origins=resolved_settings.cors_origin_list or ['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
  )
  app.state.runtime = runtime
  app.state.providers = providers

  @app.middleware('http')
  async def log_http_requests(request: Request, call_next):
    started_at = perf_counter()
    client_host = request.client.host if request.client else '-'
    logger.info('http request started method=%s path=%s client=%s', request.method, request.url.path, client_host)

    try:
      response = await call_next(request)
    except Exception:
      duration_ms = (perf_counter() - started_at) * 1000
      logger.exception('http request failed method=%s path=%s client=%s duration_ms=%.2f', request.method, request.url.path, client_host, duration_ms)
      raise

    duration_ms = (perf_counter() - started_at) * 1000
    logger.info('http request completed method=%s path=%s client=%s status=%s duration_ms=%.2f', request.method, request.url.path, client_host, response.status_code, duration_ms)
    return response

  @app.get('/health')
  def health() -> dict[str, str]:
    logger.info('health check provider=%s model=%s', resolved_settings.normalized_model_provider, resolved_settings.default_model)
    return {
      'status': 'ok',
      'provider': resolved_settings.normalized_model_provider,
      'model': resolved_settings.default_model,
    }

  @app.post('/_internal/shutdown')
  def shutdown(request: Request):
    client_host = request.client.host if request.client else None
    if not is_loopback_host(client_host):
      logger.warning('shutdown rejected client=%s', client_host)
      return JSONResponse({'state': -1, 'message': 'forbidden'}, status_code=403)

    server = getattr(request.app.state, 'uvicorn_server', None)
    if server is None:
      logger.error('shutdown unavailable server_handle_missing=true')
      return error_response('当前启动方式不支持优雅关闭', status_code=500)

    logger.warning('shutdown requested client=%s', client_host)
    server.should_exit = True
    return {'status': 'shutting_down'}

  @app.post('/tools/aippt_outline')
  def aippt_outline(payload: AIPPTOutlineRequest):
    command = build_outline_command(payload)
    context = build_log_context(
      providers,
      'aippt_outline',
      request_id=command.context.request_id,
      model=payload.model,
      content=payload.content,
      language=payload.language,
    )
    logger.info('aippt_outline request received %s', context)

    if not payload.content.strip():
      logger.warning('aippt_outline rejected empty content %s', context)
      return error_response('PPT 主题不能为空')

    try:
      providers.ensure_backend_ready()
      stream = runtime.iter_outline_chunks(command)
      first_chunk = next(stream)

      def response_stream() -> Iterator[bytes]:
        yield first_chunk.encode('utf-8')
        for chunk in stream:
          yield chunk.encode('utf-8')

      return StreamingResponse(
        log_stream('aippt_outline', response_stream(), context),
        media_type='text/markdown; charset=utf-8',
      )
    except StopIteration:
      logger.warning('aippt_outline returned empty stream %s', context)
      return error_response('模型未返回任何大纲内容')
    except Exception as exc:
      logger.exception('aippt_outline failed %s', context)
      return error_response(str(exc))

  @app.post('/tools/aippt')
  def aippt(payload: AIPPTRequest):
    command = build_deck_command(payload)
    context = build_log_context(
      providers,
      'aippt',
      request_id=command.context.request_id,
      model=payload.model,
      content=payload.content,
      language=payload.language,
      style=payload.style,
    )
    logger.info('aippt request received %s', context)

    if not payload.content.strip():
      logger.warning('aippt rejected empty content %s', context)
      return error_response('PPT 大纲不能为空')

    try:
      providers.ensure_backend_ready()
      return StreamingResponse(
        log_stream('aippt', encode_slide_stream(runtime.iter_slides(command)), context),
        media_type='text/event-stream; charset=utf-8',
        headers={
          'Cache-Control': 'no-cache',
          'X-Accel-Buffering': 'no',
        },
      )
    except Exception as exc:
      logger.exception('aippt failed %s', context)
      return error_response(str(exc))

  @app.post('/tools/ai_writing')
  def ai_writing(payload: AIWritingRequest):
    command = build_writing_command(payload)
    context = build_log_context(
      providers,
      'ai_writing',
      request_id=command.context.request_id,
      model=payload.model,
      content=payload.content,
      command_text=payload.command,
    )
    logger.info('ai_writing request received %s', context)

    if not payload.content.strip():
      logger.warning('ai_writing rejected empty content %s', context)
      return error_response('没有可以改写的文本内容')

    try:
      providers.ensure_backend_ready()
      return StreamingResponse(
        log_stream('ai_writing', encode_text_stream(runtime.iter_text_chunks(command)), context),
        media_type='text/plain; charset=utf-8',
      )
    except Exception as exc:
      logger.exception('ai_writing failed %s', context)
      return error_response(str(exc))

  return app


def summarize_text(text: str, limit: int = 80) -> str:
  normalized = ' '.join(text.split())
  if len(normalized) <= limit:
    return normalized
  return f'{normalized[:limit]}...'


def build_log_context(
  providers: AgnoProviderGateway,
  endpoint: str,
  *,
  request_id: str,
  model: str | None = None,
  content: str = '',
  language: str | None = None,
  style: str | None = None,
  command_text: str | None = None,
) -> str:
  parts = [
    f'endpoint={endpoint}',
    f'request_id={request_id}',
    f'model={providers.resolve_model_name(model)}',
    f'content_len={len(content.strip())}',
  ]
  if language:
    parts.append(f'language={language}')
  if style:
    parts.append(f'style={style}')
  if command_text:
    parts.append(f'command={summarize_text(command_text, 48)!r}')

  preview = summarize_text(content, 96)
  if preview:
    parts.append(f'preview={preview!r}')

  return ' '.join(parts)


def log_stream(name: str, stream: Iterator[bytes], context: str) -> Iterator[bytes]:
  chunk_count = 0
  byte_count = 0

  try:
    for chunk in stream:
      chunk_count += 1
      byte_count += len(chunk)
      yield chunk
  except Exception:
    logger.exception('%s stream failed %s', name, context)
    raise

  logger.info('%s stream completed chunks=%s bytes=%s %s', name, chunk_count, byte_count, context)


def error_response(message: str, status_code: int = 200) -> JSONResponse:
  return JSONResponse({'state': -1, 'message': message}, status_code=status_code)


def is_loopback_host(host: str | None) -> bool:
  return host in ('127.0.0.1', '::1', 'localhost')


def serialize_slide(slide: dict[str, Any]) -> str:
  return json.dumps(slide, ensure_ascii=False)


def encode_slide_sse(slide: dict[str, Any]) -> bytes:
  return f'data: {serialize_slide(slide)}\n\n'.encode('utf-8')


def encode_slide_stream(slides: Iterator[dict[str, Any]]) -> Iterator[bytes]:
  for slide in slides:
    yield encode_slide_sse(slide)


def encode_text_stream(chunks: Iterator[str]) -> Iterator[bytes]:
  for chunk in chunks:
    yield chunk.encode('utf-8')