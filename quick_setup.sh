#!/bin/bash
# Quick setup command for immediate resolution (Fixed for PostgreSQL issues)

echo "🔧 Quick setup for Apate API documentation..."

# Activate virtual environment (create if needed)
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install only essential dependencies to avoid PostgreSQL issues
echo "📥 Installing core FastAPI dependencies..."
pip install --upgrade pip
pip install fastapi uvicorn python-multipart pydantic python-dotenv

# Copy environment config
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "📋 Created .env file from template"
else
    echo "📋 .env file already exists"
fi

echo ""
echo "✅ Setup complete! The import errors are now resolved."
echo ""
echo "🚀 Start the API server:"
echo "   source venv/bin/activate"
echo "   python backend/main.py"
echo ""
echo "📚 API documentation will be available at:"
echo "   - Swagger UI: http://localhost:8000/docs"
echo "   - ReDoc: http://localhost:8000/redoc"
echo ""
echo "💡 To install full dependencies later (with PostgreSQL):"
echo "   brew install postgresql  # macOS"
echo "   sudo apt-get install postgresql-dev  # Ubuntu"
echo "   pip install -r requirements-full.txt"