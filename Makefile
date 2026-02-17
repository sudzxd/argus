.DEFAULT_GOAL := help

# =============================================================================
# Development
# =============================================================================

.PHONY: install
install: ## Install all dependencies and pre-commit hooks
	uv sync --all-extras
	uv run pre-commit install
	uv run pre-commit install --hook-type commit-msg

.PHONY: update
update: ## Update all dependencies
	uv lock --upgrade
	uv sync --all-extras

# =============================================================================
# Quality
# =============================================================================

.PHONY: fmt
fmt: ## Format code
	uv run ruff format src tests

.PHONY: lint
lint: ## Run linter
	uv run ruff check src tests

.PHONY: lint-fix
lint-fix: ## Run linter with auto-fix
	uv run ruff check --fix src tests

.PHONY: typecheck
typecheck: ## Run type checker
	uv run pyright

.PHONY: check
check: lint typecheck ## Run all quality checks

# =============================================================================
# Testing
# =============================================================================

.PHONY: test
test: ## Run tests with coverage
	uv run pytest

.PHONY: test-unit
test-unit: ## Run unit tests only
	uv run pytest tests/unit

.PHONY: test-integration
test-integration: ## Run integration tests only
	uv run pytest tests/integration

.PHONY: test-smoke
test-smoke: ## Run smoke tests against live LLM providers (needs API keys)
	uv run pytest tests/smoke -v --no-cov

.PHONY: test-cov
test-cov: ## Run tests and open HTML coverage report
	uv run pytest --cov-report=html
	open htmlcov/index.html 2>/dev/null || xdg-open htmlcov/index.html 2>/dev/null || true

# =============================================================================
# Pre-commit
# =============================================================================

.PHONY: pre-commit
pre-commit: ## Run all pre-commit hooks
	@command -v pre-commit >/dev/null 2>&1 || uv run pre-commit install
	uv run pre-commit run --all-files

# =============================================================================
# Cleanup
# =============================================================================

.PHONY: clean
clean: ## Remove build artifacts and caches
	rm -rf .ruff_cache .pytest_cache htmlcov .coverage dist build
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# =============================================================================
# Help
# =============================================================================

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
