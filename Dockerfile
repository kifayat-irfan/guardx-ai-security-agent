# GuardX backend — production image for Render (repo-root context).
# Local dev still uses backend/Dockerfile with backend/ as context.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
# CPU-only torch: the PyPI default bundles ~800MB+ of unused CUDA libs and can
# exceed free-tier build limits. Install the CPU wheel first so dependents
# (ultralytics, sentence-transformers) reuse it.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch torchvision
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY policies ./policies

EXPOSE 8000

# Migrate, then serve.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
