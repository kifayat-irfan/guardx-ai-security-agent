# GuardX — Phase 1: exact commands

Run from the repository root (`~/workspace/guardx`). Assumes Docker and
Python 3.11+ and Node 20+ are installed on the dev machine.

## 1. Enter the repo, create env file

```bash
cd ~/workspace/guardx
cp .env.example .env
# edit .env only if you need to change passwords/ports
```

## 2. Backend scaffold

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
```

Create `backend/requirements.txt` with (minimum viable for Phase 1):

```
fastapi==0.115.*
uvicorn[standard]==0.30.*
sqlalchemy==2.0.*
alembic==1.13.*
psycopg2-binary==2.9.*
pydantic==2.*
pydantic-settings==2.*
pytest==8.*
httpx==0.27.*
```

```bash
pip install -r requirements.txt
```

## 3. FastAPI app skeleton

Create these files (Phase 1 content only):

- `app/__init__.py` — empty
- `app/main.py` — FastAPI app, includes routers, startup event runs
  `alembic upgrade head`
- `app/core/config.py` — `Settings(BaseSettings)` reading `.env`
- `app/core/logging.py` — basic structured logging
- `app/api/v1/routers/health.py` — `GET /health`, `GET /api/v1/health/detailed`
  (detailed checks postgres via SQLAlchemy + chroma via httpx, YOLO reports
  `loaded: false` until Phase 2)
- `app/models/` — `camera.py`, `zone.py`, `policy.py` (SQLAlchemy)
- `app/schemas/` — matching Pydantic models

## 4. Database migration

```bash
alembic init alembic
# edit alembic/env.py → import models, use DATABASE_URL from settings
alembic revision --autogenerate -m "phase1: cameras, zones, policies"
alembic upgrade head
```

## 5. Backend tests

```bash
pytest tests/ -v
# tests/test_health.py must pass before continuing
```

## 6. Frontend scaffold

```bash
cd ../frontend
npx create-next-app@latest . --typescript --tailwind --app --no-src-dir \
  --import-alias "@/*" --use-npm
npm install
```

- Set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `.env.local`.
- Edit `app/page.tsx`: fetch `${NEXT_PUBLIC_API_URL}/health`, render status.
- `npm run dev` → http://localhost:3000 shows "backend: ok".

## 7. Dockerfiles + compose (write these files)

- `backend/Dockerfile` (`python:3.11-slim`, install requirements, run
  `uvicorn app.main:app --host 0.0.0.0 --port 8000`)
- `frontend/Dockerfile` (`node:20-alpine`, `npm run build`, `next start`)
- `docker-compose.yml` — services `postgres`, `chromadb`, `backend`,
  `frontend` (+ `n8n` under `profiles: [automation]`), volumes `pgdata`,
  `chroma-data`, bind mount `./assets:/app/assets`

## 8. Bring it all up

```bash
cd ~/workspace/guardx
docker compose up --build
```

Verify:
- http://localhost:8000/docs — Swagger loads, `/health` → 200
- http://localhost:3000 — shows backend status ok
- `docker compose exec postgres pg_isready -U guardx`
- `curl localhost:8001/api/v2/heartbeat` — ChromaDB alive

## 9. Phase 1 done when

- [ ] `pytest` green
- [ ] `docker compose up --build` clean from scratch
- [ ] backend `/docs` + frontend both reachable
- [ ] migration up/down round-trip works
- [ ] commit: `git init && git add -A && git commit -m "Phase 1: foundation"`
