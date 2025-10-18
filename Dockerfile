# ------------------------------
# 1️⃣ Base image
# ------------------------------
FROM python:3.9-slim

# Prevents Python from buffering stdout/stderr (good for logs)
ENV PYTHONUNBUFFERED=1

# ------------------------------
# 2️⃣ Install dependencies
# ------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------
# 3️⃣ Set working directory
# ------------------------------
WORKDIR /app

# ------------------------------
# 4️⃣ Copy dependency list and install packages
# ------------------------------
COPY perfume-recommender/backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# ------------------------------
# 5️⃣ Copy source code
# ------------------------------
COPY perfume-recommender/backend /app/backend
COPY perfume-recommender/data /app/data

# ------------------------------
# 6️⃣ Default environment variables (can be overridden by Render)
# ------------------------------
ENV HOST=0.0.0.0
ENV PORT=8000

# ------------------------------
# 7️⃣ Expose the app port
# ------------------------------
EXPOSE ${PORT}

# ------------------------------
# 8️⃣ Start the FastAPI app using Uvicorn
# ------------------------------
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]