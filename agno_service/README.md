# PPTist Agno Service

This service implements the AI endpoints used by PPTist:

- `/tools/aippt_outline`
- `/tools/aippt`
- `/tools/ai_writing`

It keeps the existing frontend contract unchanged and supports two backends:

- OpenAI-compatible APIs
- free local Ollama models

## Install

```bash
python -m pip install -r agno_service/requirements.txt
```

## Configure

1. Copy `agno_service/.env.example` to `agno_service/.env`.
2. If you plan to deploy the service, use `AGNO_MODEL_PROVIDER=openai` and fill in `AGNO_OPENAI_API_KEY`.
3. Point `AGNO_OPENAI_BASE_URL` at your OpenAI-compatible provider, or leave it empty for the official OpenAI endpoint.
4. Map the PPTist dropdown values to your real remote model names with `AGNO_MODEL_ALIASES`.
5. Only use `AGNO_MODEL_PROVIDER=ollama` for local-only zero-key experiments.

### Remote provider quick start

This is the recommended path when you do not want to depend on a local model runtime.

```bash
AGNO_MODEL_PROVIDER=openai
AGNO_OPENAI_API_KEY=your_provider_key
AGNO_OPENAI_BASE_URL=https://your-provider.example/v1
AGNO_DEFAULT_MODEL=your-provider-model
AGNO_MODEL_ALIASES={"glm-4.7-flash":"your-provider-model","doubao-seed-1.6-flash":"your-provider-model"}
```

- Works with any OpenAI-compatible provider.
- Fits deployment environments better because the backend only needs outbound HTTP access.
- If you later front the provider with Cloudflare AI Gateway, keep `AGNO_MODEL_PROVIDER=openai` and replace `AGNO_OPENAI_BASE_URL` with your gateway URL.

### Optional local model quick start

```bash
winget install --id Ollama.Ollama -e
ollama pull qwen2.5:3b
```

Recommended free local models:

- `qwen2.5:3b`: smaller, easier to run locally
- `qwen2.5:7b`: better Chinese quality, needs more memory

If your target is Cloudflare-style deployment, prefer the remote provider path and skip Ollama entirely.

## Run

```bash
python -m agno_service.run
```

Or from the project root, use the npm scripts:

```bash
pnpm run dev:api
pnpm run dev:api:stop
pnpm run dev:api:restart
pnpm run dev:all
```

- `pnpm run dev:api`: start only the Agno backend on the stable local port 8000
- `pnpm run dev:api:stop`: try graceful local shutdown first, then clean up any remaining backend processes
- `pnpm run dev:api:restart`: stop existing Agno backend processes, then start one clean backend on 8000
- `pnpm run dev:all`: start frontend and backend together

## Frontend integration

- Vite dev proxy now points to `http://127.0.0.1:8000` by default.
- Override it with `VITE_AI_PROXY_TARGET` if your service runs elsewhere.
- Override runtime API base URL with `VITE_API_BASE_URL` if you want the frontend to call a deployed backend directly.

## Health check

```bash
curl http://127.0.0.1:8000/health
```