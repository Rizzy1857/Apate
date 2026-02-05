# Rust Protocol Dockerfile - Security Hardened
# Rust Protocol Dockerfile - Security Hardened
# Use Alpine for static binary (musl) to avoid glibc version issues
FROM rust:alpine as builder

# Install build dependencies for Alpine
RUN apk add --no-cache musl-dev

WORKDIR /app
COPY Cargo.toml ./
COPY src ./src

# Build with security optimizations, disabling default features (pyo3)
RUN cargo build --release --bin main --no-default-features

# Runtime stage
# Runtime stage
FROM alpine:latest

# Install minimal required packages and security updates
RUN apk --no-cache add \
    netcat-openbsd \
    ca-certificates \
    && rm -rf /var/cache/apk/*

# Create non-root user for security
RUN addgroup -S rustprotocol && adduser -S -G rustprotocol rustprotocol

# Create app directory with proper permissions
WORKDIR /app
# No need to chown since we are root currently, but good practice
RUN chown rustprotocol:rustprotocol /app

# Copy binary
COPY --from=builder /app/target/release/main /app/rust-protocol
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
CMD ["/app/rust-protocol"]
