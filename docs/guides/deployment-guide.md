# Deployment Guide

## Overview

The Vibe Dating App backend uses a modern Poetry-based deployment system that provides consistent, reproducible deployments across all environments. This guide covers the complete deployment process from local development to production.

## Architecture

### Deployment Components

1. **Poetry Dependency Management**: Modern Python package management
2. **AWS Lambda Functions**: Serverless compute for authentication and API endpoints
3. **CloudFormation**: Infrastructure as Code for AWS resources
4. **S3 Artifact Storage**: Lambda package storage and versioning
5. **API Gateway**: REST API endpoints with Lambda integration

### Service Structure

```
vibe-dating-backend/
├── src/services/
│   └── auth/                    # Authentication Service
│       ├── aws_lambdas/         # Lambda Functions
│       │   ├── core/            # Shared utilities
│       │   ├── auth_platform/   # Telegram authentication
│       │   ├── auth_jwt_authorizer/  # JWT token validation
│       │   └── test/            # Lambda tests
│       └── cloudformation/      # Infrastructure templates
├── scripts/                     # Poetry-based deployment scripts
└── pyproject.toml              # Poetry configuration
```

## Prerequisites

### Required Software

1. **Python 3.11+**
   ```bash
   python3 --version
   # Should show Python 3.11.x or higher
   ```

2. **Poetry**
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   poetry --version
   ```

3. **AWS CLI**
   ```bash
   aws --version
   aws configure  # Configure your credentials
   ```

4. **Docker** (Optional)
   ```bash
   docker --version
   ```

### AWS Configuration

1. **AWS Profile Setup**
   ```bash
   aws configure --profile vibe-dev
   # Enter your AWS Access Key ID
   # Enter your AWS Secret Access Key
   # Enter your default region (il-central-1)
   # Enter your output format (json)
   ```

2. **Environment Variables**
   ```bash
   export AWS_PROFILE=vibe-dev
   export AWS_REGION=il-central-1
   export ENVIRONMENT=dev
   ```

## Installation

### Project Setup

1. **Clone Repository**
   ```bash
   git clone <repository-url>
   cd vibe-dating-backend
   ```

2. **Install Dependencies**
   ```bash
   # Install all dependencies
   poetry install
   
   # Install Lambda-specific dependencies
   poetry install --with lambda
   ```

3. **Verify Installation**
   ```bash
   poetry run python -c "import jwt, boto3, requests; print('Dependencies installed successfully')"
   ```

## Build System

### Lambda Package Building

The build system creates optimized Lambda packages with proper dependency management:

```bash
poetry run build-lambda
```

#### Generated Artifacts

- **`build/lambda/core_layer.zip`**: Shared Python dependencies layer
- **`build/lambda/auth_platform.zip`**: Telegram authentication function
- **`build/lambda/auth_jwt_authorizer.zip`**: JWT authorization function

#### Build Process Details

1. **Dependency Export**: Poetry exports Lambda dependencies to requirements.txt
2. **Layer Creation**: Creates shared dependency layer for code reuse
3. **Function Packaging**: Packages individual Lambda functions with minimal dependencies
4. **Optimization**: Removes unnecessary files and optimizes package sizes

#### Build Configuration

The build process is configured in `pyproject.toml`:

```toml
[tool.poetry.group.lambda.dependencies]
PyJWT = "2.8.0"
boto3 = "1.34.0"
botocore = "1.34.0"
requests = "2.31.0"
urllib3 = "2.0.7"
python-dateutil = "2.8.2"

[tool.poetry.scripts]
build-lambda = "scripts.build:build_lambda"
```

## Testing

### Comprehensive Test Suite

```bash
poetry run service-test auth
```

#### Test Categories

1. **Lambda Layer Tests**: Validates dependency availability and compatibility
2. **Structure Tests**: Ensures proper code organization and imports
3. **Authentication Tests**: Tests Telegram auth and JWT validation logic
4. **Unit Tests**: Pytest-based unit tests for individual components
5. **Code Quality**: Black, isort, and mypy for code formatting and type checking

#### Individual Test Commands

```bash
# Lambda layer tests
poetry run python src/services/auth/aws_lambdas/test/test_layer.py

# Code structure tests
poetry run python src/services/auth/aws_lambdas/test/test_structure.py

# Authentication tests
poetry run python src/services/auth/aws_lambdas/test/test_auth.py

# Unit tests
poetry run pytest tests/

# Code quality checks
poetry run black --check src/
poetry run isort --check-only src/
```

## Deployment

### Authentication Service Deployment

```bash
poetry run service-deploy auth
```

#### Deployment Process

1. **Prerequisites Check**: Validates AWS credentials, Poetry installation, and build artifacts
2. **Lambda Building**: Automatically builds Lambda packages if not present
3. **S3 Upload**: Uploads packages to environment-specific S3 bucket
4. **CloudFormation Deployment**: Deploys/updates infrastructure stack
5. **Output Display**: Shows API Gateway URLs and other outputs

#### Environment-Specific Deployment

```bash
# Development
export ENVIRONMENT=dev
poetry run service-deploy auth

# Staging
export ENVIRONMENT=staging
poetry run service-deploy auth

# Production
export ENVIRONMENT=prod
poetry run service-deploy auth
```

### CloudFormation Configuration

#### Stack Details

- **Stack Name**: `vibe-dating-auth-service`
- **ApiRegion**: `il-central-1` (default)
- **Capabilities**: `CAPABILITY_NAMED_IAM` for IAM role creation
- **Tags**: Environment and Service tags for resource management

#### Required Parameters

Update `src/config/cloudformation/parameters.yaml`:

```yaml
Parameters:
  Environment:
    Type: String
    Description: Deployment environment
    Default: "dev"
    AllowedValues: ["dev", "staging", "prod"]
```

### Manual Deployment Steps

If you need to deploy manually:

```bash
# 1. Build Lambda packages
poetry run service-build auth

# 2. Upload to S3 (if needed)
aws s3 cp build/lambda/ s3://vibe-dating-code-dev-<uuid-suffix>/lambda/ --recursive

# 3. Deploy CloudFormation stack
aws cloudformation deploy \
  --template-file src/services/auth/cloudformation/template.yaml \
  --stack-name vibe-dating-auth-service \
  --parameter-overrides file://src/config/cloudformation/parameters.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --region il-central-1
```

## Monitoring & Maintenance

### Deployment Monitoring

#### CloudFormation Events
```bash
aws cloudformation describe-stack-events \
  --stack-name vibe-dating-auth-service \
  --region il-central-1
```

#### Lambda Metrics
```bash
# Get function metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=auth-platform-function \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-01T23:59:59Z \
  --period 3600 \
  --statistics Average
```

#### API Gateway Logs
```bash
# Enable API Gateway logging
aws apigateway update-stage \
  --rest-api-id your-api-id \
  --stage-name dev \
  --patch-operations op=replace,path=/accessLogSettings/destinationArn,value=arn:aws:logs:il-central-1:account:log-group:/aws/apigateway/vibe-auth
```

### Maintenance Tasks

#### Dependency Updates
```bash
# Update dependencies
poetry update

# Update Lambda dependencies specifically
poetry update --with lambda

# Check for security vulnerabilities
poetry audit
```

#### Cleanup Tasks
```bash
# Clean build artifacts
rm -rf build/

# Clean Poetry cache
poetry cache clear . --all

# Remove old CloudFormation stacks
aws cloudformation delete-stack --stack-name old-stack-name
```

#### Validation Tasks
```bash
# Validate CloudFormation templates
aws cloudformation validate-template \
  --template-body file://src/services/auth/cloudformation/template.yaml

# Test Lambda functions locally
poetry run python -m pytest tests/ -v

# Check code quality
poetry run black --check src/
poetry run isort --check-only src/
```

## Troubleshooting

### Common Issues

#### Build Failures
```bash
# Clean and rebuild
rm -rf build/
poetry install --with lambda
poetry run service-build auth
```

#### Deployment Failures
```bash
# Check CloudFormation events
aws cloudformation describe-stack-events --stack-name vibe-dating-auth-service

# Validate template
aws cloudformation validate-template --template-body file://template.yaml

# Check AWS credentials
aws sts get-caller-identity
```

#### Test Failures
```bash
# Run tests with verbose output
poetry run pytest tests/ -v -s

# Run specific test
poetry run python src/services/auth/aws_lambdas/test/test_auth.py

# Check dependencies
poetry show --tree
```

### Performance Optimization

#### Lambda Optimization
- Use Lambda layers for shared dependencies
- Minimize package sizes by excluding unnecessary files
- Configure appropriate memory and timeout settings
- Use connection pooling for database connections

#### Deployment Optimization
- Use S3 for Lambda package storage
- Implement blue-green deployments for zero downtime
- Use CloudFormation change sets for safe updates
- Monitor deployment times and optimize as needed

## Security Considerations

### AWS Security
- Use IAM roles with minimal required permissions
- Enable CloudTrail for API call logging
- Use VPC endpoints for private communication
- Implement proper encryption for data at rest and in transit

### Application Security
- Validate all input parameters
- Use secure JWT secrets
- Implement rate limiting
- Monitor for suspicious activity

### Secrets Management
- Use AWS Secrets Manager for sensitive data
- Rotate secrets regularly
- Never commit secrets to version control
- Use environment-specific secrets

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy to AWS

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install Poetry
        run: |
          curl -sSL https://install.python-poetry.org | python3 -
      
      - name: Install dependencies
        run: |
          poetry install --with lambda
      
      - name: Run tests
        run: |
          poetry run service-test auth
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: il-central-1
      
      - name: Deploy to AWS
        run: |
          export ENVIRONMENT=prod
          poetry run service-deploy auth
```

### Environment Promotion

```bash
# Promote from dev to staging
export ENVIRONMENT=staging
poetry run service-deploy auth

# Promote from staging to production
export ENVIRONMENT=prod
poetry run service-deploy auth
```

## Best Practices

### Development Workflow
1. Always run tests before deployment
2. Use feature branches for development
3. Review CloudFormation changes before deployment
4. Monitor deployments and rollback if needed

### Deployment Strategy
1. Use blue-green deployments for zero downtime
2. Implement proper rollback procedures
3. Monitor application metrics after deployment
4. Use environment-specific configurations

### Security Practices
1. Rotate secrets regularly
2. Use least privilege IAM policies
3. Enable security monitoring
4. Regular security audits

### Performance Practices
1. Optimize Lambda package sizes
2. Use appropriate memory and timeout settings
3. Implement caching where appropriate
4. Monitor and optimize performance metrics 