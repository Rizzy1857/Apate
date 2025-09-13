# Apate Honeypot - Dependencies Installation Guide

## Python Dependencies

Create and activate a virtual environment, then install requirements:

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install FastAPI and dependencies
pip install fastapi uvicorn python-multipart

# Or install from requirements file if it exists:
pip install -r requirements.txt
```

## Required Dependencies for API Documentation

```bash
pip install fastapi[all] uvicorn[standard] python-multipart
```

## Development Dependencies

```bash
pip install pytest pytest-asyncio httpx black ruff mypy
```

## Docker Alternative

If you prefer using Docker (recommended for consistency):

```bash
# Build and run with Docker Compose
docker-compose up --build

# The API documentation will be available at:
# - Swagger UI: http://localhost:8000/docs
# - ReDoc: http://localhost:8000/redoc
```

## IDE Configuration

Configure your IDE to use the correct Python interpreter:

### VS Code
1. Open Command Palette (Cmd+Shift+P)
2. Select "Python: Select Interpreter"
3. Choose the interpreter from your virtual environment

### PyCharm
1. Go to Settings > Project > Python Interpreter
2. Add interpreter from your virtual environment

## Verification

Test that imports work correctly:

```bash
python -c "import fastapi; print('FastAPI installed successfully')"
```