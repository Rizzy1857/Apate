# Deploying Mirage (Apate) 🚀

This guide steps you through running the full Mirage Honeypot locally, including the specialized AI Engine.

## Prerequisites
*   Python 3.10+
*   Rus (optional for Layer 0, but Python fallback enabled)

## 1. Setup Environment

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## 2. Run the Application

The application uses FastAPI and Uvicorn. The AI Engine starts automatically with the server.

```bash
# Start the server (Development Mode)
python3 -m backend.app.main
```

Or using uvicorn directly:

```bash
uvicorn backend.app.main:app --reload
```

## 3. Verify System Components

Once running, access the following endpoints:

*   **Health Check**: [http://localhost:8000/](http://localhost:8000/)
*   **Status**: [http://localhost:8000/status](http://localhost:8000/status)
*   **Active Sessions**: [http://localhost:8000/api/v1/sessions](http://localhost:8000/api/v1/sessions)

## 4. Test Interaction (Dry Run)

You can use `curl` to simulate an attacker.

**Simulate SSH Command:**
```bash
curl -X POST "http://localhost:8000/honeypot/ssh/interact" \
     -H "Content-Type: application/json" \
     -d '{"command": "whoami", "session_id": "test_session_1"}'
```

**Simulate Unknown Command (AI Hallucination):**
```bash
curl -X POST "http://localhost:8000/honeypot/ssh/interact" \
     -H "Content-Type: application/json" \
     -d '{"command": "glarb_mcguffin", "session_id": "test_session_1"}'
```

**Check AI Analysis:**
Only internal logs show the risk score updates for now, but you can see the session sticking in memory.

## 5. Persistence
The AI Engine will save its state to `backend/app/ai/data` (or configured path) upon shutdown (Ctrl+C).

---
**Note**: For production, use `docker-compose.yml`.
