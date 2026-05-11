# ─── EduFlow Makefile — Test Commands ────────────────────────────────────────
# Usage: make <target>

.PHONY: help test test-e2e test-e2e-headed test-e2e-debug test-backend \
        test-backend-unit test-backend-api test-backend-cov \
        playwright-install playwright-report

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-28s\033[0m %s\n", $$1, $$2}'

# ─── E2E Tests (Playwright) ──────────────────────────────────────────────────

playwright-install: ## Install Playwright and browser binaries
	cd frontend && npx playwright install --with-deps

test-e2e: ## Run all E2E tests (headless)
	npx playwright test --config=playwright.config.js

test-e2e-headed: ## Run E2E tests with a visible browser
	npx playwright test --config=playwright.config.js --headed

test-e2e-debug: ## Run E2E tests in debug mode (Playwright Inspector)
	npx playwright test --config=playwright.config.js --debug

test-e2e-ui: ## Launch Playwright UI mode
	npx playwright test --config=playwright.config.js --ui

playwright-report: ## Open the last HTML test report
	npx playwright show-report

# ─── Backend Tests (pytest) ──────────────────────────────────────────────────

test-backend: ## Run all backend tests
	cd backend && python -m pytest ../tests/backend -v

test-backend-unit: ## Run only unit tests (no DB/network)
	cd backend && python -m pytest ../tests/backend/unit -v -m unit

test-backend-api: ## Run API tests (requires running backend + seeded DB)
	cd backend && python -m pytest ../tests/backend/api -v -m api

test-backend-integration: ## Run integration tests
	cd backend && python -m pytest ../tests/backend/integration -v -m integration

test-backend-cov: ## Run backend tests with coverage report
	cd backend && python -m pytest ../tests/backend \
		--cov=. \
		--cov-report=html:../htmlcov \
		--cov-report=term-missing \
		-v

# ─── Combined ────────────────────────────────────────────────────────────────

test: test-backend test-e2e ## Run all tests (backend + E2E)
