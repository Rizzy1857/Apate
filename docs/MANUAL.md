# Apate Manual

**Version**: 1.0 (Jan 2026)
**Status**: Layer 0 (Rust) + Layer 1 (Python) Active

---

## 🚀 Quick Start

### 1. Prerequisites
- **Docker & Docker Compose** (Recommended)
- **Python 3.11+** (For local dev)
- **Rust 1.70+** (For protocol dev)

### 2. Deployment (Docker)
The easiest way to run Apate is via Docker. This spins up the Rust protocol layer, Python backend, PostgreSQL, and Redis.

```bash
# Clone the repository
git clone https://github.com/Rizzy1857/Apate.git
cd Apate

# Start services
docker-compose up -d

# Verify Status
curl http://localhost:8000/status
```

### 3. Local Development Setup
If you want to contribute or debug:

```bash
# 1. Setup Python Env
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

# 2. Start Infra (DB + Redis)
docker-compose -f docker-compose.override.yml up -d postgres redis

# 3. Run Backend (FastAPI)
cd backend
uvicorn app.main:app --reload --port 8000

# 4. Run Protocol Layer (Rust)
# Open a new terminal
cd rust-protocol
cargo run
```

---

## 📖 Usage Guide

### API Endpoints

#### Interactions
- **SSH Simulation**: `POST /api/v1/interact/ssh`
- **HTTP Simulation**: `POST /api/v1/interact/http`

#### Management
- **Status**: `GET /status`
- **Metrics**: `GET /metrics`

### Testing
We have a comprehensive test suite (66+ tests).

```bash
# Run all tests
pytest tests/

# Run specific suite
pytest tests/test_layer0_reflex.py
```

---

## 🛡️ Guardrails & Safety

### Privacy Architecture
Apate is designed with a "Local First" privacy model.
- **Default**: No cloud export. All data stays local in PostgreSQL/Redis.
- **Telemetry**: Opt-in only. Uses `privacy.py` to scrub PII before export (if enabled).

### Household Safety
- **Fail-Open**: If the AI engine crashes or latency exceeds 200ms, the `AdaptiveCircuitBreaker` (Layer 0) forces a "static" response to ensure network stability.
- **Resource Limits**: The system monitors its own CPU/RAM usage and gracefully sheds load (disables Layer 2+ analysis) if limits are hit.

---

## 🔧 Configuration

Configuration is handled via `.env` file or environment variables.

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Postgres Connection String | `postgresql://...` |
| `REDIS_URL` | Redis Connection String | `redis://...` |
| `AI_PROVIDER` | LLM Provider (openai/anthropic/stub) | `stub` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |

---

## 🤝 Troubleshooting

**Database Connection Failed?**
- Check if Docker container is up: `docker ps`
- Check logs: `docker-compose logs postgres`

**Rust Protocol Error?**
- Ensure you have the latest toolchain: `rustup update`
- Rebuild: `cargo clean && cargo build`
