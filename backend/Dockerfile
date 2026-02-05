# Backend Dockerfile with Rust Support
# ==========================================

# Stage 1: Build Rust Extension
# Stage 1: Build Rust Extension
FROM rust:latest AS builder

# Install Python and build tools
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install maturin
RUN pip3 install maturin --break-system-packages

WORKDIR /src
COPY rust-protocol/Cargo.toml ./rust-protocol/
COPY rust-protocol/src ./rust-protocol/src
COPY rust-protocol/pyproject.toml ./rust-protocol/

WORKDIR /src/rust-protocol
# Build wheel for the Python version used in the final stage (3.11)
# Note: Using python3 as the interpreter since we installed it above
RUN maturin build --release --interpreter python3

# Stage 2: Final Runtime
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install the Rust extension wheel from builder stage
COPY --from=builder /src/rust-protocol/target/wheels/*.whl /tmp/
RUN pip install /tmp/*.whl && rm /tmp/*.whl

# Copy application code
COPY backend/ .

# Create necessary directories
RUN mkdir -p /app/logs /app/data

# Expose ports
EXPOSE 8000 2222 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/status || exit 1

# Run the application
# Using a shell form or explicit entry to ensure internal port binding matches
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
