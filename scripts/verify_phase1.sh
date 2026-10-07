#!/usr/bin/env bash
# GuardX Phase 1 verification — run from repo root.
# Expects: backend running on :8000, postgres reachable via DATABASE_URL.
set -u
PASS=0; FAIL=0
check() { # $1 = name, $2... = command
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then echo "PASS: $name"; PASS=$((PASS+1));
  else echo "FAIL: $name"; FAIL=$((FAIL+1)); fi
}

cd "$(dirname "$0")/.."
echo "== GuardX Phase 1 verification =="

check "backend venv exists" test -x backend/.venv/bin/python
check "pytest suite green" backend/.venv/bin/python -m pytest backend/tests/ -q
check "alembic heads up-to-date" bash -c 'cd backend && .venv/bin/alembic upgrade head'
check "GET /health -> 200" bash -c 'curl -sf http://127.0.0.1:8000/health | grep -q "\"status\":\"ok\""'
check "GET /api/v1/health -> 200" bash -c 'curl -sf http://127.0.0.1:8000/api/v1/health | grep -q ok'
check "GET /api/v1/health/detailed -> 200" bash -c 'curl -sf http://127.0.0.1:8000/api/v1/health/detailed | grep -q version'
check "postgres reachable" bash -c 'cd backend && .venv/bin/python -c "
from app.core.database import check_postgres
r = check_postgres(); assert r[\"status\"] == \"up\", r
"'
check "tables exist (cameras,zones,policies)" bash -c 'cd backend && .venv/bin/python -c "
from sqlalchemy import inspect
from app.core.database import engine
tables = inspect(engine).get_table_names()
assert {\"cameras\",\"zones\",\"policies\"} <= set(tables), tables
"'
check "frontend production build" bash -c 'cd frontend && test -d .next'
check "docker-compose.yml valid" bash -c 'python3 -c "
import yaml; d = yaml.safe_load(open(\"docker-compose.yml\"))
assert \"automation\" in d[\"services\"][\"n8n\"].get(\"profiles\", [])
"'
check ".env present (gitignored)" test -f .env

echo "---------------------------------"
echo "PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
