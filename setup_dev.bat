@echo off
REM Apate Honeypot - Windows Development Environment Setup Script

echo 🚀 Setting up Apate Honeypot development environment...

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python 3.11+ is required but not found in PATH
    exit /b 1
)

echo ✅ Python found

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
) else (
    echo 📦 Virtual environment already exists
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo ⬆️ Upgrading pip...
python -m pip install --upgrade pip

REM Install production dependencies
echo 📥 Installing production dependencies...
pip install -r requirements.txt

REM Install development dependencies
echo 🛠️ Installing development dependencies...
pip install -r requirements-dev.txt

REM Install pre-commit hooks
echo 🔗 Setting up pre-commit hooks...
pre-commit install

echo 🎉 Setup complete!
echo.
echo To activate the environment in the future, run:
echo   venv\Scripts\activate.bat
echo.
echo To start the API server, run:
echo   python backend\main.py
echo.
echo API documentation will be available at:
echo   - Swagger UI: http://localhost:8000/docs
echo   - ReDoc: http://localhost:8000/redoc