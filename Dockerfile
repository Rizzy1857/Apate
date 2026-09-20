FROM python:3.11-slim-trixie@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534

# Install system dependencies for FUSE and Postgres
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    fuse \
    libfuse2 \
    libseccomp2 \
    && rm -rf /var/lib/apt/lists/*

# Setup application directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip==26.2.1 setuptools==84.0.0 wheel==0.48.0 \
    && pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y pip setuptools wheel \
    && rm -r /usr/local/lib/python3.11/ensurepip

# Create mount point
RUN mkdir -p /mnt/honeypot

# Copy application code
COPY src/ /app/src/
COPY config/ /app/config/

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app/src

# Default command
CMD ["python3", "-m", "chronos.core.main"]
