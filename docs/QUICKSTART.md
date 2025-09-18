# Quick Start Guide for Apate Honeypot

## Prerequisites

- Python 3.11 or higher
- Git
- Docker and Docker Compose (optional)

## Setup Instructions

### Option 1: Automated Setup (Recommended)

#### macOS/Linux:

```bash
# Clone the repository
git clone https://github.com/Rizzy1857/Apate.git
cd Apate

# Make setup script executable and run it
chmod +x setup_dev.sh
./setup_dev.sh
```

#### Windows:

```cmd
# Clone the repository
git clone https://github.com/Rizzy1857/Apate.git
cd Apate

# Run setup script
setup_dev.bat
```

### Option 2: Manual Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Copy environment configuration
cp .env.example .env
```

## Running the Application

### Start the API Server

```bash
# Activate virtual environment (if not already active)
source venv/bin/activate

# Start the FastAPI server
python backend/main.py
```

The API will be available at:

- **API Base**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Using Docker (Alternative)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Verification

Test the API is working:

```bash
# Health check
curl http://localhost:8000/health

# Expected response:
# {
#   "status": "healthy",
#   "timestamp": "2024-12-24T10:30:00Z",
#   "services": {
#     "api": "healthy",
#     "database": "healthy",
#     "redis": "healthy"
#   },
#   "version": "1.0.0"
# }
```

## Next Steps

1. **Explore the API**: Visit http://localhost:8000/docs
2. **Run Tests**: `pytest`
3. **Check Code Quality**: `pre-commit run --all-files`
4. **View Documentation**: Check the `/docs` folder

## Troubleshooting

### Import Errors

If you see FastAPI import errors:

```bash
# Ensure virtual environment is activated
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Port Already in Use

If port 8000 is busy:

```bash
# Kill process using port 8000
lsof -ti:8000 | xargs kill -9

# Or run on different port
uvicorn backend.main:app --port 8001
```

## Development Workflow

1. **Activate Environment**: `source venv/bin/activate`
2. **Make Changes**: Edit code files
3. **Run Tests**: `pytest`
4. **Check Quality**: `pre-commit run --all-files`
5. **Commit**: Git will automatically run pre-commit hooks

## Support

- **Issues**: https://github.com/Rizzy1857/Apate/issues
- **Documentation**: `/docs` folder
- **API Reference**: http://localhost:8000/docs