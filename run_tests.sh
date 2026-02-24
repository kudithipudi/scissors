#!/bin/bash
# Test runner script for Rock Paper Scissors

set -e  # Exit on error

echo "🧪 Rock Paper Scissors Test Suite"
echo "=================================="
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "📦 Activating virtual environment..."
    source venv/bin/activate
fi

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "❌ pytest not found. Installing test dependencies..."
    pip install -r requirements.txt
fi

# Run tests based on arguments
if [ "$1" == "unit" ]; then
    echo "🔬 Running unit tests only..."
    pytest tests/ -m "not integration" "$@"
elif [ "$1" == "integration" ]; then
    echo "🔗 Running integration tests only..."
    pytest tests/test_integration.py "$@"
elif [ "$1" == "coverage" ]; then
    echo "📊 Running tests with detailed coverage..."
    pytest tests/ --cov=app --cov-report=html --cov-report=term
    echo ""
    echo "📈 Coverage report generated at: htmlcov/index.html"
elif [ "$1" == "fast" ]; then
    echo "⚡ Running fast tests (no coverage)..."
    pytest tests/ --no-cov -x "$@"
elif [ "$1" == "watch" ]; then
    echo "👀 Running tests in watch mode..."
    pytest-watch tests/
else
    echo "🧪 Running all tests..."
    pytest tests/ "$@"
fi

echo ""
echo "✅ Test run complete!"
