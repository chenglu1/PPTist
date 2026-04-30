from __future__ import annotations

from fastapi import FastAPI

from agno_service.http_app import create_app


backend_app = create_app()

app = FastAPI()
app.mount('/api', backend_app)
app.mount('/', backend_app)