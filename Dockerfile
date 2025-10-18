# ===== Base image (match local Python 3.9) =====
FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps for building wheels (pandas, numpy, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

# Work inside /app
WORKDIR /app

# Install dependencies first (layer cache)
COPY perfume-recommender/backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy the backend (includes app/, data/, static/, templates/)
COPY perfume-recommender/backend /app/backend

# Default envs (override at runtime)
ENV HOST=0.0.0.0 \
    PORT=8000

EXPOSE 8000

# Run FastAPI (use JSON-form CMD)
WORKDIR /app/backend
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]