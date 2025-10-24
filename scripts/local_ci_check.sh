#!/bin/bash
# Quick CI Test Script for Local Development
# Run this before pushing to catch issues early

set -e

echo "🔍 Running local CI checks..."

# Python checks
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt > /dev/null 2>&1 || echo "⚠️  Some dependencies failed to install"

echo "🧹 Running linting (ruff)..."
ruff check . --quiet || echo "⚠️  Linting issues found"

echo "🎨 Running formatting check (black)..."
black --check --quiet . || echo "⚠️  Formatting issues found"

echo "🔍 Running type check (mypy)..."
mypy backend/ --ignore-missing-imports --quiet || echo "⚠️  Type check issues found"

# Go checks
if [ -f "go-services/go.mod" ]; then
    echo "🐹 Running Go build..."
    cd go-services && go build main.go && cd .. || echo "⚠️  Go build failed"
fi

# Rust checks
if [ -f "rust-protocol/Cargo.toml" ]; then
    echo "🦀 Running Rust build..."
    cd rust-protocol && cargo build --quiet && cd .. || echo "⚠️  Rust build failed"
fi

echo "✅ Local CI checks complete!"
echo "💡 Push to trigger GitHub Actions workflow"
