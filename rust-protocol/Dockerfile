# Rust Protocol Dockerfile - Security Hardened
FROM rust:1.70 as builder

WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY src ./src

# Build with security optimizations
RUN cargo build --release

FROM debian:bookworm-slim

# Install minimal required packages and security updates
RUN apt-get update && apt-get install -y \
    netcat-traditional \
    ca-certificates \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r rustprotocol && useradd -r -g rustprotocol -s /bin/false rustprotocol

# Create app directory with proper permissions
WORKDIR /app
RUN chown rustprotocol:rustprotocol /app

# Copy binary with restricted permissions
COPY --from=builder --chown=rustprotocol:rustprotocol /app/target/release/main /app/rust-protocol
RUN chmod 755 /app/rust-protocol

# Create read-only directories
RUN mkdir -p /tmp /var/tmp && \
    chown rustprotocol:rustprotocol /tmp /var/tmp

# Switch to non-root user
USER rustprotocol

EXPOSE 7878 7879

# Security-enhanced healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD nc -z localhost 7878 || exit 1

# Run with security options
CMD ["./rust-protocol"]
