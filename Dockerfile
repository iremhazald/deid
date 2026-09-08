# Multi-stage build for DeID LegalTech application
FROM python:3.11-slim as backend-builder

WORKDIR /app

# Install system dependencies for PyMuPDF and RapidOCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libfreetype6-dev \
    libjpeg-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install
COPY apps/api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Frontend build stage
FROM node:20-alpine as frontend-builder

WORKDIR /app

# Copy frontend package files
COPY apps/web/package*.json /app/
RUN npm ci --production=false

# Copy frontend source and build
COPY apps/web /app
RUN npm run build

# Final runtime stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libfreetype6 \
    libjpeg62-turbo \
    libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=backend-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend-builder /usr/local/bin /usr/local/bin

# Copy application code
COPY apps/api /app/apps/api

# Copy built frontend assets
COPY --from=frontend-builder /app/dist /app/apps/web/dist

# Create output directory for redacted files
RUN mkdir -p /app/redacted_outputs && chmod 777 /app/redacted_outputs

# Environment defaults
ENV REDACTION_ALLOWED_ORIGIN="*" \
    REDACTION_OUTPUT_DIR="/app/redacted_outputs" \
    REDACTION_JOB_TTL_SECONDS="1800" \
    REDACTION_MAX_FILE_MB="25" \
    PYTHONUNBUFFERED="1"

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health').read()" || exit 1

# Start FastAPI server
CMD ["uvicorn", "app.main:app", "--app-dir", "/app/apps/api", "--host", "0.0.0.0", "--port", "8000"]
