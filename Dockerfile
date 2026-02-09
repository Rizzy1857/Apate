FROM python:3.11-slim-bookworm

# Install system dependencies for FUSE and Postgres
RUN apt-get update && apt-get install -y \
    fuse \
    libfuse2 \
    gcc \
    libpq-dev \
    curl \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Setup application directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create mount point
RUN mkdir -p /mnt/honeypot

# Copy entrypoint script if needed (we use command in compose for now)
COPY src/ /app/src/

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app/src

# Default command
CMD ["python3", "-m", "chronos.core.main"]
