# GuardX backend — FastAPI
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
# CPU-only torch: the PyPI default bundles ~800MB+ of unused CUDA libs and can
# exceed free-tier build limits. Install the CPU wheel first so dependents
# (ultralytics, sentence-transformers) reuse it.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch torchvision
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Migrate, then serve. (Local dev: run `alembic upgrade head` manually.)
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
