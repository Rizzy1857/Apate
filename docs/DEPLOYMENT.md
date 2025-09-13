# Deployment Guide

## 🚀 **Overview**

This guide covers deployment options for the Apate Honeypot Platform, from development environments to production-ready deployments with security hardening and monitoring.

## 📋 **Deployment Options**

| Method | Use Case | Complexity | Security | Scalability |
|--------|----------|------------|----------|-------------|
| **Docker Compose** | Development, Small Scale | Low | Medium | Low |
| **Kubernetes** | Production, Enterprise | High | High | High |
| **Cloud Services** | Managed Deployment | Medium | High | High |
| **Bare Metal** | Maximum Control | High | High | Medium |

## 🐳 **Docker Compose Deployment**

### Quick Start

```bash
# Clone repository
git clone https://github.com/Rizzy1857/Apate.git
cd Apate

# Production deployment
docker-compose up -d

# Development with database
docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d

# View logs
docker-compose logs -f backend

# Stop services
docker-compose down
```

### Production Configuration

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  backend:
    image: apate/backend:latest
    container_name: apate-backend
    restart: unless-stopped
    environment:
      - ENVIRONMENT=production
      - LOG_LEVEL=INFO
      - DATABASE_URL=postgresql://apate:${DB_PASSWORD}@postgres:5432/apate
      - REDIS_URL=redis://redis:6379/0
      - AI_PROVIDER=openai
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
    networks:
      - apate-network
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp
    user: "1000:1000"

  postgres:
    image: postgres:15-alpine
    container_name: apate-postgres
    restart: unless-stopped
    environment:
      - POSTGRES_DB=apate
      - POSTGRES_USER=apate
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/init.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - apate-network
    security_opt:
      - no-new-privileges:true

  redis:
    image: redis:7-alpine
    container_name: apate-redis
    restart: unless-stopped
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    networks:
      - apate-network
    security_opt:
      - no-new-privileges:true

  nginx:
    image: nginx:alpine
    container_name: apate-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
    depends_on:
      - backend
    networks:
      - apate-network

volumes:
  postgres_data:
  redis_data:

networks:
  apate-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

### Environment Configuration

Create `.env` file:

```bash
# Database
DB_PASSWORD=your_secure_database_password
REDIS_PASSWORD=your_secure_redis_password

# AI Provider
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# Security
SECRET_KEY=your_secret_key_for_jwt
ENCRYPTION_KEY=your_encryption_key

# Monitoring
ENABLE_METRICS=true
METRICS_PORT=9090
```

## ☸️ **Kubernetes Deployment**

### Namespace Setup

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: apate-honeypot
  labels:
    name: apate-honeypot
    security-level: high
```

### ConfigMap

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: apate-config
  namespace: apate-honeypot
data:
  ENVIRONMENT: "production"
  LOG_LEVEL: "INFO"
  AI_PROVIDER: "openai"
  DATABASE_URL: "postgresql://apate:password@postgres:5432/apate"
  REDIS_URL: "redis://redis:6379/0"
```

### Secrets

```yaml
# secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: apate-secrets
  namespace: apate-honeypot
type: Opaque
data:
  db-password: <base64-encoded-password>
  redis-password: <base64-encoded-password>
  openai-api-key: <base64-encoded-key>
  secret-key: <base64-encoded-secret>
```

### Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: apate-backend
  namespace: apate-honeypot
spec:
  replicas: 3
  selector:
    matchLabels:
      app: apate-backend
  template:
    metadata:
      labels:
        app: apate-backend
    spec:
      serviceAccountName: apate-service-account
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
      - name: apate-backend
        image: apate/backend:v1.0.0
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: apate-config
        env:
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: apate-secrets
              key: db-password
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: apate-secrets
              key: openai-api-key
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /status
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop:
              - ALL
```

### Service

```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: apate-backend-service
  namespace: apate-honeypot
spec:
  selector:
    app: apate-backend
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
```

### Ingress

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: apate-ingress
  namespace: apate-honeypot
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  tls:
  - hosts:
    - honeypot.yourdomain.com
    secretName: apate-tls
  rules:
  - host: honeypot.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: apate-backend-service
            port:
              number: 80
```

### Deployment Commands

```bash
# Apply Kubernetes manifests
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secrets.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f ingress.yaml

# Verify deployment
kubectl get pods -n apate-honeypot
kubectl get services -n apate-honeypot
kubectl logs -f deployment/apate-backend -n apate-honeypot

# Scale deployment
kubectl scale deployment apate-backend --replicas=5 -n apate-honeypot
```

## ☁️ **Cloud Deployments**

### AWS ECS Deployment

```json
{
  "family": "apate-honeypot",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::account:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::account:role/apateTaskRole",
  "containerDefinitions": [
    {
      "name": "apate-backend",
      "image": "your-account.dkr.ecr.region.amazonaws.com/apate/backend:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "ENVIRONMENT",
          "value": "production"
        }
      ],
      "secrets": [
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:apate/database-url"
        },
        {
          "name": "OPENAI_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:apate/openai-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/apate-honeypot",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

### Google Cloud Run

```yaml
# cloudbuild.yaml
steps:
- name: 'gcr.io/cloud-builders/docker'
  args: ['build', '-t', 'gcr.io/$PROJECT_ID/apate-backend', './backend']
- name: 'gcr.io/cloud-builders/docker'
  args: ['push', 'gcr.io/$PROJECT_ID/apate-backend']
- name: 'gcr.io/cloud-builders/gcloud'
  args:
  - 'run'
  - 'deploy'
  - 'apate-honeypot'
  - '--image'
  - 'gcr.io/$PROJECT_ID/apate-backend'
  - '--region'
  - 'us-central1'
  - '--platform'
  - 'managed'
  - '--allow-unauthenticated'
```

### Azure Container Instances

```yaml
# azure-container-instance.yaml
apiVersion: 2019-12-01
location: eastus
name: apate-honeypot
properties:
  containers:
  - name: apate-backend
    properties:
      image: youracr.azurecr.io/apate/backend:latest
      ports:
      - port: 8000
        protocol: TCP
      resources:
        requests:
          cpu: 0.5
          memoryInGb: 1
      environmentVariables:
      - name: ENVIRONMENT
        value: production
      - name: DATABASE_URL
        secureValue: postgresql://user:pass@server:5432/db
  ipAddress:
    type: Public
    ports:
    - protocol: TCP
      port: 8000
  osType: Linux
  restartPolicy: Always
type: Microsoft.ContainerInstance/containerGroups
```

## 🛡️ **Security Hardening**

### Network Security

```bash
# Firewall rules (iptables)
# Allow only necessary ports
iptables -A INPUT -p tcp --dport 22 -j ACCEPT    # SSH
iptables -A INPUT -p tcp --dport 80 -j ACCEPT    # HTTP
iptables -A INPUT -p tcp --dport 443 -j ACCEPT   # HTTPS
iptables -A INPUT -p tcp --dport 2222 -j ACCEPT  # SSH Honeypot
iptables -A INPUT -p tcp --dport 8080 -j ACCEPT  # HTTP Honeypot

# Drop all other traffic
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# Save rules
iptables-save > /etc/iptables/rules.v4
```

### SSL/TLS Configuration

```nginx
# nginx/nginx.conf
server {
    listen 443 ssl http2;
    server_name honeypot.yourdomain.com;
    
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;
    
    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    
    location / {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Secret Management

```bash
# Using Docker secrets
echo "your_database_password" | docker secret create db_password -
echo "your_openai_api_key" | docker secret create openai_key -

# Using HashiCorp Vault
vault kv put secret/apate \
    database_password="your_db_password" \
    openai_api_key="your_api_key"

# Using Kubernetes secrets
kubectl create secret generic apate-secrets \
    --from-literal=db-password=your_password \
    --from-literal=openai-api-key=your_key \
    --namespace=apate-honeypot
```

## 📊 **Monitoring & Observability**

### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'apate-honeypot'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:9100']

rule_files:
  - "alert_rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Apate Honeypot Monitoring",
    "panels": [
      {
        "title": "Threat Events",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(threat_events_total[5m])",
            "legendFormat": "Threat Events/sec"
          }
        ]
      },
      {
        "title": "Active Sessions",
        "type": "singlestat",
        "targets": [
          {
            "expr": "active_sessions_total",
            "legendFormat": "Active Sessions"
          }
        ]
      }
    ]
  }
}
```

### Log Aggregation

```yaml
# fluent-bit.conf
[SERVICE]
    Flush         1
    Log_Level     info
    Daemon        off

[INPUT]
    Name              tail
    Path              /app/logs/*.log
    Parser            json
    Tag               apate.*

[OUTPUT]
    Name              es
    Match             apate.*
    Host              elasticsearch
    Port              9200
    Index             apate-logs
    Type              _doc
```

## 🔧 **Maintenance & Updates**

### Update Procedure

```bash
# 1. Backup data
docker-compose exec postgres pg_dump -U apate apate > backup_$(date +%Y%m%d).sql

# 2. Pull latest images
docker-compose pull

# 3. Apply updates
docker-compose up -d

# 4. Verify deployment
curl -f http://localhost:8000/status

# 5. Run health checks
./scripts/health_check.sh
```

### Backup Strategy

```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"

# Database backup
docker-compose exec -T postgres pg_dump -U apate apate > "$BACKUP_DIR/database_$DATE.sql"

# Configuration backup
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" docker-compose.yml .env nginx/

# Log backup
tar -czf "$BACKUP_DIR/logs_$DATE.tar.gz" logs/

# Cleanup old backups (keep 30 days)
find "$BACKUP_DIR" -name "*.sql" -mtime +30 -delete
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +30 -delete
```

## 🚨 **Troubleshooting**

### Common Issues

1. **Container Won't Start**
   ```bash
   # Check logs
   docker-compose logs backend
   
   # Check resource usage
   docker stats
   
   # Verify configuration
   docker-compose config
   ```

2. **Database Connection Issues**
   ```bash
   # Test database connectivity
   docker-compose exec backend python -c "
   from backend.app.database import engine
   print('Database connection:', engine.execute('SELECT 1').scalar())
   "
   ```

3. **High Memory Usage**
   ```bash
   # Monitor container resources
   docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"
   
   # Set memory limits
   # In docker-compose.yml:
   deploy:
     resources:
       limits:
         memory: 512M
   ```

### Performance Tuning

```yaml
# docker-compose.yml performance optimizations
services:
  backend:
    environment:
      - WORKERS=4
      - MAX_CONNECTIONS=100
      - CACHE_TTL=3600
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M

  postgres:
    environment:
      - POSTGRES_SHARED_BUFFERS=256MB
      - POSTGRES_EFFECTIVE_CACHE_SIZE=1GB
      - POSTGRES_MAX_CONNECTIONS=200
```

## 📋 **Deployment Checklist**

### Pre-deployment

- [ ] Review security requirements
- [ ] Configure environment variables
- [ ] Set up SSL certificates
- [ ] Configure monitoring and logging
- [ ] Test backup and restore procedures
- [ ] Verify network security rules
- [ ] Review legal and compliance requirements

### Post-deployment

- [ ] Verify all services are running
- [ ] Test API endpoints
- [ ] Check monitoring dashboards
- [ ] Validate log collection
- [ ] Test honeypot functionality
- [ ] Verify alert notifications
- [ ] Document deployment configuration

### Security Validation

- [ ] Run security scanner on containers
- [ ] Verify no default credentials
- [ ] Test network isolation
- [ ] Validate SSL/TLS configuration
- [ ] Review firewall rules
- [ ] Test incident response procedures

---

**Deployment Guide Version**: 1.0  
**Last Updated**: August 25, 2025  
**Next Review**: September 25, 2025
