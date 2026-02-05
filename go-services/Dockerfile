# Go Services Dockerfile
FROM golang:1.25-alpine AS builder

WORKDIR /app
COPY . .

RUN if [ ! -f go.mod ]; then go mod init go-services; fi && \
    go mod tidy && \
    CGO_ENABLED=0 go build -o iot-gateway main.go && \
    chmod +x iot-gateway

FROM alpine:latest

RUN apk --no-cache add ca-certificates wget

WORKDIR /app
COPY --from=builder /app/iot-gateway .
RUN chmod +x iot-gateway && chown 1000:1000 iot-gateway

EXPOSE 8081

# Healthcheck requires wget or curl, which are present in Alpine.
# docker-compose.yml uses: wget --quiet --tries=1 --spider http://localhost:8081/status

CMD ["/app/iot-gateway"]
