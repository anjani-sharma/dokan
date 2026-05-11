FROM python:3.12-slim

WORKDIR /app

# Install backend dependencies first for layer caching.
# Build context is the repo root (set in Render: Docker Build Context = ".").
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy both backend (the FastAPI app) and bot (services imported by the
# embedded webhook + OCR endpoints).
COPY backend /app/backend
COPY bot /app/bot

WORKDIR /app/backend

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
