# Nidavelir Core

The Core service owns Nidavelir's durable orchestration state and exposes the HTTP API used by MCP and the web interface.

## Local development

```bash
cd core
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn nidavelir_core.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "nidavelir-core",
  "environment": "development"
}
```

Run tests and lint:

```bash
pytest
ruff check .
```
