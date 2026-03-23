FROM python:3.11-slim-bookworm

# Install system dependencies for FUSE and Postgres
RUN apt-get update && apt-get install -y \
    fuse \
    libfuse2 \
    gcc \
    libpq-dev \
    curl \
    nano \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Setup application directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create mount point
RUN mkdir -p /mnt/honeypot

# Copy application code
COPY src/ /app/src/
COPY bin/ /app/bin/

# Make wrapper scripts executable
RUN chmod +x /app/bin/wget /app/bin/curl && \
    ln -sf /app/bin/wget /usr/local/bin/wget && \
    ln -sf /app/bin/curl /usr/local/bin/curl

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app/src

# Default command
CMD ["python3", "-m", "chronos.core.main"]
