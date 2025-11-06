.PHONY: help install install-dev test lint format type-check clean \
        test-connection preview-5 preview-10 process-10 process-50 full-run \
        attach-products dry-run report clean-reports

# Default target
.DEFAULT_GOAL := help

# Colors for output
CYAN := \033[0;36m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m # No Color

help:
	@echo "$(CYAN)Additional Companies Product Linker - Available Commands$(NC)"
	@echo ""
	@echo "$(GREEN)Setup & Dependencies:$(NC)"
	@echo "  make install          - Install production dependencies"
	@echo "  make install-dev      - Install development dependencies"
	@echo "  make setup            - Full setup (venv + deps + .env)"
	@echo ""
	@echo "$(GREEN)Development:$(NC)"
	@echo "  make test             - Run tests with coverage"
	@echo "  make lint             - Run all linters (ruff + mypy)"
	@echo "  make format           - Format code with ruff"
	@echo "  make type-check       - Run mypy type checking"
	@echo "  make clean            - Remove generated files"
	@echo ""
	@echo "$(GREEN)Quick Testing:$(NC)"
	@echo "  make test-connection  - Test MongoDB & Pipedrive connection"
	@echo "  make preview-5        - Preview 5 submissions (dry-run)"
	@echo "  make preview-10       - Preview 10 submissions (dry-run)"
	@echo ""
	@echo "$(GREEN)Processing:$(NC)"
	@echo "  make process-10       - Process 10 submissions"
	@echo "  make process-50       - Process 50 submissions"
	@echo "  make full-run         - Process all submissions with report"
	@echo ""
	@echo "$(GREEN)Custom Commands:$(NC)"
	@echo "  make attach-products ARGS='...'  - Run with custom arguments"
	@echo "  make dry-run LIMIT=N              - Dry run with N submissions"
	@echo ""
	@echo "$(GREEN)Utilities:$(NC)"
	@echo "  make report           - Generate CSV report (last run)"
	@echo "  make clean-reports    - Clean old reports"
	@echo ""
	@echo "$(YELLOW)Examples:$(NC)"
	@echo "  make dry-run LIMIT=20"
	@echo "  make attach-products ARGS='--limit 100 --report my_report.csv'"
	@echo "  make attach-products ARGS='--profile aggressive --no-confirm'"

# ============================================================================
# SETUP & INSTALLATION
# ============================================================================

install:
	@echo "$(CYAN)Installing production dependencies...$(NC)"
	pip install -r requirements.txt
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

install-dev:
	@echo "$(CYAN)Installing development dependencies...$(NC)"
	pip install -r requirements-dev.txt
	@echo "$(GREEN)✓ Dev dependencies installed$(NC)"

setup: install install-dev
	@echo "$(CYAN)Checking for .env file...$(NC)"
	@if [ ! -f .env ]; then \
		echo "$(YELLOW)⚠ No .env file found. Creating from .env.example...$(NC)"; \
		cp .env.example .env; \
		echo "$(YELLOW)⚠ Please edit .env with your credentials$(NC)"; \
	else \
		echo "$(GREEN)✓ .env file exists$(NC)"; \
	fi
	@echo "$(GREEN)✓ Setup complete!$(NC)"

# ============================================================================
# DEVELOPMENT
# ============================================================================

test:
	@echo "$(CYAN)Running tests with coverage...$(NC)"
	pytest -v --cov=src --cov-report=xml --cov-report=term-missing --cov-report=html
	@echo "$(GREEN)✓ Tests complete$(NC)"

lint:
	@echo "$(CYAN)Running linters...$(NC)"
	@echo "$(CYAN)Running ruff...$(NC)"
	ruff check .
	@echo "$(CYAN)Running mypy...$(NC)"
	mypy src/
	@echo "$(GREEN)✓ Linting complete$(NC)"

format:
	@echo "$(CYAN)Formatting code with ruff...$(NC)"
	ruff format .
	@echo "$(GREEN)✓ Code formatted$(NC)"

type-check:
	@echo "$(CYAN)Running type checks...$(NC)"
	mypy src/
	@echo "$(GREEN)✓ Type checking complete$(NC)"

clean:
	@echo "$(CYAN)Cleaning generated files...$(NC)"
	rm -rf __pycache__ .pytest_cache .coverage htmlcov .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

# ============================================================================
# QUICK TESTING
# ============================================================================

test-connection:
	@echo "$(CYAN)Testing connection (5 submissions, dry-run)...$(NC)"
	python -m src.main attach-products --dry-run --limit 5 --verbose

preview-5:
	@echo "$(CYAN)Previewing 5 submissions (dry-run)...$(NC)"
	python -m src.main attach-products --dry-run --limit 5

preview-10:
	@echo "$(CYAN)Previewing 10 submissions (dry-run)...$(NC)"
	python -m src.main attach-products --dry-run --limit 10

# ============================================================================
# PROCESSING COMMANDS
# ============================================================================

process-10:
	@echo "$(YELLOW)Processing 10 submissions...$(NC)"
	python -m src.main attach-products --limit 10 --report reports/batch_10_$(shell date +%Y%m%d_%H%M%S).csv

process-50:
	@echo "$(YELLOW)Processing 50 submissions...$(NC)"
	python -m src.main attach-products --limit 50 --report reports/batch_50_$(shell date +%Y%m%d_%H%M%S).csv

full-run:
	@echo "$(YELLOW)⚠ Starting full run - processing ALL submissions$(NC)"
	@echo "$(YELLOW)This will take a while and make changes to Pipedrive$(NC)"
	@echo "Press Ctrl+C in the next 5 seconds to cancel..."
	@sleep 5
	python -m src.main attach-products --report reports/full_run_$(shell date +%Y%m%d_%H%M%S).csv

# ============================================================================
# CUSTOM COMMANDS
# ============================================================================

# Default values for variables
LIMIT ?= 10
ARGS ?=

attach-products:
	@echo "$(CYAN)Running attach-products with custom arguments...$(NC)"
	python -m src.main attach-products $(ARGS)

dry-run:
	@echo "$(CYAN)Dry run with $(LIMIT) submissions...$(NC)"
	python -m src.main attach-products --dry-run --limit $(LIMIT) --verbose

# ============================================================================
# PROFILES
# ============================================================================

profile-conservative:
	@echo "$(CYAN)Running with conservative profile (dry-run)...$(NC)"
	python -m src.main attach-products --profile conservative --dry-run --limit 10

profile-aggressive:
	@echo "$(YELLOW)Running with aggressive profile (dry-run)...$(NC)"
	python -m src.main attach-products --profile aggressive --dry-run --limit 10

profile-migration:
	@echo "$(YELLOW)Running with migration profile (dry-run)...$(NC)"
	python -m src.main attach-products --profile migration --dry-run --limit 10

# ============================================================================
# UTILITIES
# ============================================================================

report:
	@echo "$(CYAN)Generating report...$(NC)"
	python -m src.main attach-products --dry-run --limit 1 --report test_report.csv
	@echo "$(GREEN)✓ Report saved to test_report.csv$(NC)"

clean-reports:
	@echo "$(CYAN)Cleaning old reports...$(NC)"
	rm -f reports/*.csv
	@echo "$(GREEN)✓ Reports cleaned$(NC)"

# Create reports directory if it doesn't exist
reports:
	@mkdir -p reports

# ============================================================================
# CI/CD HELPERS
# ============================================================================

ci: install-dev lint test
	@echo "$(GREEN)✓ CI checks passed$(NC)"

validate:
	@echo "$(CYAN)Validating configuration...$(NC)"
	python -m src.main attach-products --dry-run --limit 1 | head -20

# ============================================================================
# DOCKER SUPPORT (if needed)
# ============================================================================

docker-build:
	@echo "$(CYAN)Building Docker image...$(NC)"
	docker build -t additional-companies-linker .

docker-run:
	@echo "$(CYAN)Running in Docker...$(NC)"
	docker run --env-file .env additional-companies-linker

# ============================================================================
# MONITORING
# ============================================================================

logs:
	@if [ -d logs ]; then \
		echo "$(CYAN)Showing recent logs...$(NC)"; \
		tail -n 50 logs/*.log 2>/dev/null || echo "No logs found"; \
	else \
		echo "$(YELLOW)No logs directory found$(NC)"; \
	fi

tail-logs:
	@echo "$(CYAN)Tailing logs (Ctrl+C to stop)...$(NC)"
	tail -f logs/*.log
