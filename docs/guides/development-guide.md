# Development Guide

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

## Development Workflow

### Local Development
```bash
# Install development dependencies
poetry install --with dev

# Run code quality checks
poetry run black src/
poetry run isort src/
poetry run mypy src/

# Run tests
poetry run pytest tests/
```

### Poetry-Based Development Environment
The project uses Poetry for dependency management and provides a modern, consistent development experience across all environments.

#### Prerequisites
- **Python 3.11+**: Required for Lambda runtime compatibility
- **Poetry**: Modern Python dependency management
- **AWS CLI**: Configured with appropriate credentials
- **Docker**: Optional, for local development and testing

### Testing System

#### Comprehensive Test Suite
```bash
# Run all tests
poetry run service-test auth
```

**Test Categories**:
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

#### Test Configuration
- **Framework**: pytest with coverage reporting
- **Linting**: Black (formatting), isort (imports), mypy (types)
- **Coverage**: Configurable coverage thresholds and exclusions
- **Markers**: Unit, integration, and slow test markers

## Environment Configuration

### Secrets Management

The project includes a comprehensive secrets management system using AWS Secrets Manager:

```bash
# Install secrets management dependencies
pip install -r scripts/requirements-secrets.txt

# Setup core secrets interactively
python scripts/manage_secrets.py setup

# List all secrets
python scripts/manage_secrets.py list

# Export secrets to environment file
python scripts/manage_secrets.py export --output .env

# Validate all secrets
python scripts/manage_secrets.py validate

# Rotate JWT secret
python scripts/manage_secrets.py rotate --secret jwt_secret

# Get a secret value
python scripts/manage_secrets.py get --secret telegram_bot_token
```

#### Supported Secrets
**Core Secrets** (Required):
- `telegram_bot_token`: Telegram Bot Token for WebApp authentication
- `jwt_secret`: Secret key for JWT token signing (auto-generated)
- `uuid_namespace`: UUID namespace for generating consistent UUIDs (auto-generated)

#### Secret Naming Convention
Secrets are stored with environment-specific naming:
- Format: `vibe-dating/{secret-name}/{environment}`
- Examples:
  - `vibe-dating/telegram-bot-token/dev`
  - `vibe-dating/jwt-secret/prod`
  - `vibe-dating/agora-app-id/staging`

### Environment Variables
```bash
# Set environment for secrets management
export ENVIRONMENT=dev|staging|prod
export AWS_REGION=il-central-1
export AWS_PROFILE=vibe-dev
```

## Code Quality

### Development Guidelines

1. **TypeScript First**: All new code should be TypeScript
2. **Component Architecture**: Use functional components with hooks
3. **Context Usage**: Prefer context over prop drilling
4. **Responsive Design**: Mobile-first approach with Tailwind
5. **Accessibility**: Follow WCAG guidelines
6. **Performance**: Monitor bundle size and loading times
7. **Testing**: Unit tests for critical components

### Code Quality Checks
```bash
# Run code quality checks
poetry run black src/
poetry run isort src/
poetry run mypy src/

# Check code quality
poetry run black --check src/
poetry run isort --check-only src/
```

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

### The Poetry-based system integrates well with CI/CD pipelines:
- **Dependency Caching**: Poetry lock file for reproducible builds
- **Environment Isolation**: Virtual environments for each deployment
- **Artifact Management**: S3-based package storage and versioning
- **Rollback Support**: CloudFormation stack rollback capabilities

## Best Practices

### Development Workflow
1. Always run tests before deployment
2. Use feature branches for development
3. Review CloudFormation changes before deployment
4. Monitor deployments and rollback if needed

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

## Troubleshooting

### Common Issues

#### Build Failures
```bash
# Clean and rebuild
rm -rf build/
poetry install --with lambda
poetry run service-build auth
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
```