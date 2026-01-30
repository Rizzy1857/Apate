#!/bin/bash

# start.sh - Startup script for Mirage (Apate)

# 1. Resolve Project Root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

echo "🚀 Starting Mirage (Apate)..."

# 2. Check for Virtual Environment
if [ -d ".venv" ]; then
    echo "📦 Activating virtual environment..."
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo "📦 Activating virtual environment (venv)..."
    source venv/bin/activate
else
    echo "⚠️  No virtual environment found! Running with system python..."
    echo "   (Recommended: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt)"
fi

# 3. Set Python Path
export PYTHONPATH=$PYTHONPATH:$(pwd)

# 4. Start Application
echo "✅ Launching Backend..."
python3 -m backend.app.main
