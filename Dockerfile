# ==========================================================
# 🚀 Perfume Recommender – Dockerfile
# Base: Python 3.9 (matches your local environment)
# ==========================================================

FROM python:3.9-slim

# --- Environment settings ---
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# --- Install OS dependencies for building wheels (pandas, numpy, etc.) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

# --- Set working directory ---
WORKDIR /app

# --- Copy and install Python dependencies ---
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# --- Copy backend source code (includes app/, data/, static/, templates/) ---
COPY backend /app/backend

# --- Default environment variables (Render will override PORT automatically) ---
ENV HOST=0.0.0.0
ENV PORT=8000

# --- Expose the app port (informational) ---
EXPOSE ${PORT}

# --- Run FastAPI app ---
CMD ["sh", "-c", "uvicorn --app-dir /app/backend app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]