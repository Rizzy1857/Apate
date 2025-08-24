# Go Services Dockerfile
FROM golang:1.21-alpine AS builder

WORKDIR /app
COPY . .

RUN go mod init go-services && \
    go mod tidy && \
    go build -o iot-gateway main.go

FROM alpine:latest

RUN apk --no-cache add ca-certificates wget

WORKDIR /root/

COPY --from=builder /app/iot-gateway .

EXPOSE 8081

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:8081/status || exit 1

CMD ["./iot-gateway"]
