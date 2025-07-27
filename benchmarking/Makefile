# Benchmarking Makefile for Musiclist Project
# Performance testing and analysis tools

.PHONY: help scrapers parallel parallel-fast parallel-custom clean-reports clean

# Default target
help:
	@echo "⚡ Musiclist Benchmarking Tools"
	@echo ""
	@echo "🔍 Individual Scraper Benchmarks:"
	@echo "  scrapers     - Benchmark each scraper individually (no cache)"
	@echo ""
	@echo "⚡ Parallel Scraper Benchmarks:"
	@echo "  parallel     - Test parallel scraping with default worker counts (1,2,4,6,8,10)"
	@echo "  parallel-fast - Test parallel scraping with fewer worker counts (1,2,4,8)"
	@echo "  parallel-custom WORKERS='1,2,4' - Test parallel scraping with custom worker counts"
	@echo ""
	@echo "🧹 Maintenance:"
	@echo "  clean-reports - Remove all benchmark report files"
	@echo "  clean        - Clean reports and any temp files"

# Benchmark individual scrapers
scrapers:
	@echo "🔍 Benchmarking individual scrapers..."
	@python benchmark.py

# Benchmark parallel scraping with default settings
parallel:
	@echo "⚡ Benchmarking parallel scraping (default worker counts)..."
	@python benchmark.py --parallel

# Benchmark parallel scraping with fewer worker counts (faster)
parallel-fast:
	@echo "⚡ Benchmarking parallel scraping (fast mode)..."
	@python benchmark.py --parallel --workers 1,2,4,8

# Benchmark parallel scraping with custom worker counts
# Usage: make parallel-custom WORKERS='1,2,4,8'
parallel-custom:
	@echo "⚡ Benchmarking parallel scraping with custom worker counts: $(WORKERS)"
	@python benchmark.py --parallel --workers '$(WORKERS)'

# Clean up benchmark report files
clean-reports:
	@echo "🧹 Cleaning benchmark reports..."
	@rm -f benchmark_report_*.json
	@echo "✅ Benchmark reports cleaned"

# Full cleanup
clean: clean-reports
	@echo "🧹 Full benchmark cleanup complete" 