# Nidavelir Web

Operational web interface for Nidavelir.

The UI is deliberately restrained: dense information, clear hierarchy and no placeholder analytics. The Core API remains the source of truth.

## Local development

```bash
cd web
cp .env.example .env
npm install
npm run dev
```

The app expects Nidavelir Core at `http://127.0.0.1:8000` by default. Override it with `VITE_NIDAVELIR_API_URL`.

## Routes

- `/` — Overview briefing
- `/board` — durable task board
- `/agents` — worker attempts
- `/tasks/:taskId` — task detail

The routes currently provide the operational shell only. Live task data lands in #14 and execution detail in #15.
