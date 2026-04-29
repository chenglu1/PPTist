from __future__ import annotations

from fastapi import FastAPI

from agno_service.http_app import create_app


backend_app = create_app()

# Vercel's Python runtime can expose the ASGI app either with or without the
# /api prefix depending on how the mixed static+function project is routed.
# Mount both so the existing backend remains reachable in local and Vercel flows.
app = FastAPI()
app.mount('/api', backend_app)
app.mount('/', backend_app)