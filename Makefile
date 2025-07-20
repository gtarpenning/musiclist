# Musiclist Project Makefile
# Simple automation for development tasks

.PHONY: help format test test-list install clean setup calendar scrape venues

# Default target
help:
	@echo "🎵 Musiclist Project Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  calendar   - Show calendar view (current + next month)"
	@echo "  scrape     - Scrape all venues and show all events"
	@echo "  venues     - List all available venues"
	@echo "  format     - Format code using black"
	@echo "  test       - Run all tests"
	@echo "  test-list  - List available tests"
	@echo "  install    - Install dependencies"
	@echo "  setup      - Set up development environment"
	@echo "  clean      - Clean up temporary files"
	@echo ""
	@echo "Examples:"
	@echo "  make calendar                           # Show events for July & August 2025"
	@echo "  make scrape                            # Show all upcoming events"
	@echo "  make venues                            # List Brick & Mortar Music Hall, The Warfield"
	@echo "  make test                              # Run all venue tests"
	@echo "  python cli.py --help                  # Show CLI options"
	@echo "  python tests/run_tests.py brick --generate  # Generate test data"

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

# Show calendar view with all venues (current + next month)
calendar:
	@echo "🗓️  Loading music calendar..."
	@python cli.py calendar

# Scrape all venues and show all events
scrape:
	@echo "🎵 Scraping all venues..."
	@python cli.py scrape

# List all available venues
venues:
	@echo "📍 Available venues:"
	@python cli.py --list-venues

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