# Musiclist Project Makefile
# Simple automation for development tasks

.PHONY: help format test test-list install clean setup music version-update build push publish-update

# Default target
help:
	@echo "🎵 Musiclist Project Makefile"
	@echo ""
	@echo "🗓️  Calendar & Events:"
	@echo "  music        - Show calendar view (current + next month)"
	@echo ""
	@echo "🔧 Development:"
	@echo "  version-update  - Bump patch version (e.g. 0.1.5 -> 0.1.6)"
	@echo "  build           - Build package for PyPI"
	@echo "  push            - Publish package to PyPI"
	@echo "  publish-update  - Bump version, build, and publish to PyPI"
	@echo "  format          - Format code using black"
	@echo "  test            - Run all tests"
	@echo "  test-list       - List available tests"
	@echo "  install         - Install dependencies"
	@echo "  setup           - Set up development environment"
	@echo "  clean           - Clean up temporary files"

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
	@pip install black pytest build twine
	@echo "✅ Development environment ready"

# Show calendar view with all venues (current + next month)
music:
	@echo "🗓️  Loading music calendar..."
	@music music

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

# Update version (bump patch version)
version-update:
	@echo "🔢 Updating version..."
	@python utils/version_utils.py bump
	@echo "✅ Version updated successfully"

# Build package for PyPI
build: clean
	@echo "🏗️  Building package for PyPI..."
	@python -m build
	@echo "📦 Package built successfully"

# Publish package to PyPI
push:
	@echo "🚀 Publishing to PyPI..."
	@python -m twine upload dist/*
	@echo "✅ Package published to PyPI successfully"

# Full release workflow: bump version, build, and publish
publish-update: version-update build push
	@echo "🎉 Release complete! Package updated and published to PyPI" 