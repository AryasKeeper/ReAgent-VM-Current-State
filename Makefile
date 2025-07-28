# ReAgent Sydney - Development Makefile

.PHONY: help install dev test lint format clean build docker-build docker-test deploy

# Default target
help:
	@echo "ReAgent Sydney Development Commands"
	@echo "=================================="
	@echo ""
	@echo "Setup:"
	@echo "  install     Install all dependencies"
	@echo "  dev         Start development environment"
	@echo ""
	@echo "Development:"
	@echo "  test        Run all tests"
	@echo "  test-unit   Run unit tests only"
	@echo "  test-integration  Run integration tests"
	@echo "  lint        Run all linting checks"
	@echo "  format      Format code with black and isort"
	@echo "  security    Run security checks"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build    Build all Docker images"
	@echo "  docker-test     Run tests in Docker"
	@echo "  docker-dev      Start development with Docker Compose"
	@echo "  docker-clean    Clean Docker containers and images"
	@echo ""
	@echo "Deployment:"
	@echo "  deploy-staging    Deploy to staging environment"
	@echo "  deploy-prod       Deploy to production"
	@echo ""
	@echo "Utilities:"
	@echo "  clean       Clean temporary files"
	@echo "  logs        Show application logs"

# Installation and setup
install:
	@echo "Installing dependencies..."
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install -r requirements-dev.txt || echo "No dev requirements found"
	@echo "✅ Dependencies installed"

# Development environment
dev:
	@echo "Starting development environment..."
	cp .env.example .env || echo ".env already exists"
	docker-compose up -d postgres redis weaviate
	@echo "⏳ Waiting for services to be ready..."
	sleep 10
	@echo "🚀 Development environment ready!"
	@echo "Database: postgresql://reagent:reagent_dev_password@localhost:5432/reagent"
	@echo "Redis: redis://localhost:6379/0"
	@echo "Weaviate: http://localhost:8080"
	@echo ""
	@echo "Start the API with: uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000"

# Testing
test:
	@echo "Running all tests..."
	pytest tests/ -v --cov=src --cov-report=term-missing

test-unit:
	@echo "Running unit tests..."
	pytest tests/unit/ -v

test-integration:
	@echo "Running integration tests..."
	pytest tests/integration/ -v -m integration

test-e2e:
	@echo "Running end-to-end tests..."
	pytest tests/e2e/ -v -m e2e

test-watch:
	@echo "Running tests in watch mode..."
	pytest-watch tests/ -- -v

# Code quality
lint:
	@echo "Running linting checks..."
	ruff check src/ tests/
	black --check --diff src/ tests/
	isort --check-only --diff src/ tests/
	mypy src/

format:
	@echo "Formatting code..."
	black src/ tests/
	isort src/ tests/
	ruff check --fix src/ tests/
	@echo "✅ Code formatted"

security:
	@echo "Running security checks..."
	bandit -r src/ -f json -o bandit-report.json || true
	safety check -r requirements.txt || true
	semgrep --config=auto src/ || true
	@echo "✅ Security checks complete"

# Docker commands
docker-build:
	@echo "Building Docker images..."
	docker build -f Dockerfile.api -t reagent-api:latest .
	docker build -f Dockerfile.agents -t reagent-agents:latest .
	docker build -f Dockerfile.celery -t reagent-celery:latest .
	@echo "✅ Docker images built"

docker-test:
	@echo "Running tests in Docker..."
	docker-compose -f docker-compose.test.yml up -d --build
	@echo "⏳ Waiting for test services..."
	sleep 30
	docker-compose -f docker-compose.test.yml exec -T api-test pytest tests/ -v
	docker-compose -f docker-compose.test.yml down -v
	@echo "✅ Docker tests complete"

docker-dev:
	@echo "Starting full development stack with Docker..."
	cp .env.example .env || echo ".env already exists"
	docker-compose up -d --build
	@echo "🚀 Full stack running!"
	@echo "API: http://localhost:8000"
	@echo "Frontend: http://localhost:3000"
	@echo "Grafana: http://localhost:3001"
	@echo "Prometheus: http://localhost:9090"

docker-clean:
	@echo "Cleaning Docker containers and images..."
	docker-compose down -v
	docker system prune -f
	docker volume prune -f
	@echo "✅ Docker cleaned"

# Database commands
db-migrate:
	@echo "Running database migrations..."
	alembic upgrade head
	@echo "✅ Database migrated"

db-reset:
	@echo "Resetting database..."
	docker-compose down -v
	docker-compose up -d postgres
	sleep 5
	alembic upgrade head
	@echo "✅ Database reset"

# Deployment
deploy-staging:
	@echo "Deploying to staging..."
	@echo "🚧 Configure Railway CLI first: railway login"
	railway up --service reagent-api-staging --dockerfile Dockerfile.api
	@echo "✅ Deployed to staging"

deploy-prod:
	@echo "Deploying to production..."
	@echo "⚠️  Production deployment requires manual approval"
	@echo "Push to main branch to trigger deployment pipeline"

# Utilities
clean:
	@echo "Cleaning temporary files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type f -name "*.log" -delete
	@echo "✅ Cleaned temporary files"

logs:
	@echo "Showing application logs..."
	docker-compose logs -f api agents celery-worker

logs-api:
	@echo "Showing API logs..."
	docker-compose logs -f api

logs-agents:
	@echo "Showing agents logs..."
	docker-compose logs -f agents

# Health checks
health:
	@echo "Checking service health..."
	@curl -f http://localhost:8000/health && echo "✅ API healthy" || echo "❌ API unhealthy"
	@curl -f http://localhost:8080/v1/.well-known/ready && echo "✅ Weaviate healthy" || echo "❌ Weaviate unhealthy"
	@redis-cli ping && echo "✅ Redis healthy" || echo "❌ Redis unhealthy"
	@docker-compose exec -T postgres pg_isready -U reagent -d reagent && echo "✅ PostgreSQL healthy" || echo "❌ PostgreSQL unhealthy"

# Environment setup
env-example:
	@echo "Creating .env.example from current .env..."
	@if [ -f .env ]; then \
		sed 's/=.*/=/' .env > .env.example; \
		echo "✅ .env.example updated"; \
	else \
		echo "❌ .env file not found"; \
	fi