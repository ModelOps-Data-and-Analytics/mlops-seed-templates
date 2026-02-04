.PHONY: install test-pipeline validate clean lint format

# Python interpreter
PYTHON := python3

# Install dependencies
install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r ml_pipelines/requirements.txt
	$(PYTHON) -m pip install -r source_scripts/helpers/requirements.txt

# Run pipeline (dry run for testing)
test-pipeline:
	$(PYTHON) -m ml_pipelines.get_pipeline_definition \
		--module-name ml_pipelines.agent_build.pipeline \
		--dry-run

# Validate agent configuration
validate:
	$(PYTHON) -c "import yaml; yaml.safe_load(open('ml_pipelines/agent_config/knowledge_base_config.yaml'))"
	$(PYTHON) -c "import json; json.load(open('ml_pipelines/agent_config/agent_schema.json'))"
	@echo "Configuration validation passed!"

# Run linting
lint:
	$(PYTHON) -m flake8 ml_pipelines/ source_scripts/ --max-line-length=120
	$(PYTHON) -m pylint ml_pipelines/ source_scripts/ --max-line-length=120

# Format code
format:
	$(PYTHON) -m black ml_pipelines/ source_scripts/
	$(PYTHON) -m isort ml_pipelines/ source_scripts/

# Clean build artifacts
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	rm -rf build/ dist/ .eggs/

# Run tests
test:
	$(PYTHON) -m pytest source_scripts/ -v --tb=short

# Package Lambda functions
package-lambdas:
	@echo "Packaging Lambda functions..."
	cd source_scripts/action_groups/lambda_functions/get_customer_info && \
		zip -r ../../../../lambda_get_customer_info.zip .
	cd source_scripts/action_groups/lambda_functions/process_order && \
		zip -r ../../../../lambda_process_order.zip .
	@echo "Lambda packages created successfully!"

# Upload requirements to S3 (for processing jobs)
upload-requirements:
	@echo "Uploading requirements to S3..."
	aws s3 cp source_scripts/setup/requirements.txt \
		s3://$(S3_BUCKET)/SMUSMLOPS/bedrock-agents/requirements-setup/
	aws s3 cp source_scripts/create_agent/requirements.txt \
		s3://$(S3_BUCKET)/SMUSMLOPS/bedrock-agents/requirements-create-agent/
	aws s3 cp source_scripts/evaluate/requirements.txt \
		s3://$(S3_BUCKET)/SMUSMLOPS/bedrock-agents/requirements-evaluate/
	@echo "Requirements uploaded successfully!"
