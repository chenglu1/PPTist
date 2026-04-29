from __future__ import annotations

import uvicorn

from .config import get_settings
from .http_app import create_app


def main() -> None:
  settings = get_settings()
  app = create_app(settings)
  config = uvicorn.Config(
    app=app,
    host=settings.host,
    port=settings.port,
    log_level='info',
    access_log=True,
  )
  server = uvicorn.Server(config)
  app.state.uvicorn_server = server
  server.run()


if __name__ == '__main__':
  main()