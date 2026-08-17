# Argus Custode Backend Service
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

WORKDIR /workspace

# Install system utilities and GDAL libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libgdal-dev \
    gdal-bin \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY app/requirements.txt /workspace/app/requirements.txt
RUN pip install --no-cache-dir -r /workspace/app/requirements.txt

# Copy backend application code
COPY app /workspace/app
COPY tests /workspace/tests

# Expose default HTTP port
EXPOSE 8000

# Start Uvicorn server with dynamic port assignment for Render/Cloud environments
CMD ["sh", "-c", "uvicorn app.backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
