# Launch Instructions

## Quick Start (Copy & Paste)

### Step 1: Kill any existing processes
```bash
taskkill /F /IM node.exe
taskkill /F /IM python.exe
```

### Step 2: Start Backend
```bash
cd "C:\Projects\Scraper token review and classification review project"
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8021
```

### Step 3: Start Frontend (New Terminal)
```bash
cd "C:\Projects\Scraper token review and classification review project\frontend"
npm run dev
```

### Step 4: Access
- **Frontend**: http://localhost:3000  (Vite proxies `/api` → 8021)
- **Backend**: http://127.0.0.1:8021
- **API Docs**: http://127.0.0.1:8021/docs

## Verification
```bash
curl http://127.0.0.1:8021/api/health
```

## Deployment (Railway)
- **Repo**: https://github.com/varunjain1095-alt/token_classifier (`main` branch)
- **Flow**: local change → `git push` → Railway rebuilds via `Dockerfile` → healthcheck `/healthz`
- **Production shape**: single service — FastAPI serves `frontend/dist` (SPA fallback in `src/api/main.py`, `PORT` env honored)
- **Railway vars**: `OPENAI_API_KEY`, `SECRET_KEY`, `FLASK_ENV=production`, `DEBUG=false` (DB/Redis optional — in-memory fallback)
- **Local prod-parity check**: `cd frontend && npm run build`, then uvicorn serves the app on :8021 (no Vite needed)
- **Caveat**: `tmp/uploads` + sessions are ephemeral on Railway unless a volume is attached

## Current Model
`OPENAI_MODEL_NAME=gpt-5-mini` (`.env`, default also in `src/shared/config.py`).

## Test Dataset
`google_photos_reviews_100.csv` — 100 rows; sampling/eligibility verified end-to-end.

## Resume Notes (end of day state)
- Preview pipeline: shared draft taxonomy (stored per config, id+version, reuse on reruns,
  explicit "Regenerate Taxonomy" button) → per-record classification → reliability
  diagnostics + batched consistency check + optional stability run.
- Session/project state is **in-memory** (no Redis) — resets on backend restart.
- Discussed but NOT yet implemented (candidate next tasks):
  1. Keep taxonomy `description` fields and inject them into per-record prompts.
  2. Add `other`/`unmatched` as a first-class taxonomy label.
  3. Rephrase theme guidance in prompts as conditional ("include only where data supports").
  4. Warn/regenerate taxonomy when the sample differs from the one it was discovered from.
  5. Flag guidance-named themes that never get assigned (diagnostics).
- `.devin/rules/implementation-session.md` has further context.
