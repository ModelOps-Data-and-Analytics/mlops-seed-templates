.PHONY: install test lint deploy clean

# Variables
ENVIRONMENT ?= dev
AGENT_ID ?= 
AWS_REGION ?= us-east-1

# Install dependencies
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

# Linting
lint:
	flake8 deploy_agent/ tests/
	black --check deploy_agent/ tests/
	isort --check-only deploy_agent/ tests/

format:
	black deploy_agent/ tests/
	isort deploy_agent/ tests/

# Testing
test: test-unit

test-unit:
	pytest tests/unittests/ -v --tb=short

test-integration:
	pytest tests/integration_tests/ -v --tb=short \
		--agent-id $(AGENT_ID) \
		--environment $(ENVIRONMENT)

test-all: test-unit test-integration

# CDK commands
synth:
	cdk synth -c environment=$(ENVIRONMENT)

diff:
	cdk diff -c environment=$(ENVIRONMENT)

deploy:
	cdk deploy -c environment=$(ENVIRONMENT) --require-approval never

deploy-dev:
	$(MAKE) deploy ENVIRONMENT=dev

deploy-staging:
	$(MAKE) deploy ENVIRONMENT=staging

deploy-prod:
	$(MAKE) deploy ENVIRONMENT=prod

destroy:
	cdk destroy -c environment=$(ENVIRONMENT) --force

# Agent deployment
deploy-agent:
	python deploy_agent.py \
		--agent-id $(AGENT_ID) \
		--target-alias $(ENVIRONMENT) \
		--region $(AWS_REGION)

# Clean
clean:
	rm -rf cdk.out/
	rm -rf .pytest_cache/
	rm -rf __pycache__/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

# Help
help:
	@echo "Available targets:"
	@echo "  install          - Install production dependencies"
	@echo "  install-dev      - Install development dependencies"
	@echo "  lint             - Run linters"
	@echo "  format           - Format code"
	@echo "  test-unit        - Run unit tests"
	@echo "  test-integration - Run integration tests"
	@echo "  synth            - Synthesize CDK stack"
	@echo "  diff             - Show CDK diff"
	@echo "  deploy           - Deploy CDK stack"
	@echo "  deploy-agent     - Deploy agent to environment"
	@echo "  clean            - Clean build artifacts"
