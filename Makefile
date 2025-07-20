# Musiclist Project Makefile
# Simple automation for development tasks

.PHONY: help format test test-brick test-list install clean setup

# Default target
help:
	@echo "🎵 Musiclist Project Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  format     - Format code using black"
	@echo "  test       - Run all tests"
	@echo "  test-list  - List available tests"
	@echo "  install    - Install dependencies"
	@echo "  setup      - Set up development environment"
	@echo "  clean      - Clean up temporary files"
	@echo ""
	@echo "Examples:"
	@echo "  make format"
	@echo "  make test"
	@echo "  make test-brick"

# Format code using black
format:
	@echo "🎨 Formatting code with black..."
	@black --line-length 88 --target-version py39 .
	@echo "✅ Code formatting complete"

# Run all tests
test:
	@echo "🧪 Running all tests..."
	@python tests/run_tests.py

# List available tests
test-list:
	@echo "📋 Available tests:"
	@python tests/run_tests.py --list

# Install dependencies
install:
	@echo "📦 Installing dependencies..."
	@pip install -r requirements.txt
	@echo "✅ Dependencies installed"

# Set up development environment
setup: install
	@echo "🔧 Setting up development environment..."
	@pip install black pytest
	@echo "✅ Development environment ready"

# Clean up temporary files
clean:
	@echo "🧹 Cleaning up temporary files..."
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -delete
	@find . -type d -name "*.egg-info" -exec rm -rf {} +
	@rm -rf .pytest_cache/
	@rm -rf build/
	@rm -rf dist/
	@echo "✅ Cleanup complete" 