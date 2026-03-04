# Secrets Management

## Overview

A comprehensive AWS Secrets Manager integration has been added to the Vibe Dating App backend to provide secure, centralized secret management for all application secrets.

## New Files Added

### Core Script
- **`scripts/manage_secrets.py`**: Main secrets management script with full CLI interface

### Documentation Updates
- **`README.md`**: Added secrets management section to main documentation

## Features

### 🔐 Core Functionality
- **Interactive Setup**: Guided setup for core and optional secrets
- **Automatic Generation**: Secure JWT secret generation using cryptographically secure methods
- **Environment Support**: Multi-environment secret management (dev/staging/prod)
- **Validation**: Comprehensive secret validation and health checks
- **Export**: Export secrets to environment files or console output
- **Rotation**: Secure secret rotation with new value generation
- **Audit Trail**: All operations logged in CloudTrail

### 🛡️ Security Features
- **Automatic Tagging**: All secrets tagged with environment and service information
- **Access Control**: Managed through AWS IAM roles and policies
- **Recovery Window**: 7-day recovery window for deleted secrets
- **Secure Storage**: All secrets encrypted at rest using AWS KMS
- **Audit Logging**: Complete audit trail of all secret operations

### 📋 Supported Secrets

#### Core Secrets (Required)
- `telegram_bot_token`: Telegram Bot Token for WebApp authentication
- `jwt_secret`: Secret key for JWT token signing (auto-generated)
- `uuid_namespace`: UUID namespace for generating consistent UUIDs (auto-generated)

## Usage Examples

### Initial Setup
```bash
# Install dependencies
pip install -r scripts/requirements-secrets.txt

# Setup core secrets interactively
python scripts/manage_secrets.py setup

```

### Daily Operations
```bash
# List all secrets
python scripts/manage_secrets.py list

# Validate all secrets
python scripts/manage_secrets.py validate

# Export secrets to environment file
python scripts/manage_secrets.py export --output .env

# Get a specific secret value
python scripts/manage_secrets.py get --secret telegram_bot_token
```

### Security Operations
```bash
# Rotate JWT secret
python scripts/manage_secrets.py rotate --secret jwt_secret

# Delete a secret (with recovery window)
python scripts/manage_secrets.py delete --secret old_api_key

# Force delete a secret (immediate)
python scripts/manage_secrets.py delete --secret old_api_key --force
```

## Environment Configuration

### Required Environment Variables
```bash
export ENVIRONMENT=dev|staging|prod
export AWS_REGION=il-central-1
export AWS_PROFILE=vibe-dev
```

### Secret Naming Convention
- Format: `vibe-dating/{secret-name}/{environment}`
- Examples:
  - `vibe-dating/telegram-bot-token/dev`
  - `vibe-dating/jwt-secret/prod`
  - `vibe-dating/agora-app-id/staging`

## Integration with Existing Systems

### Poetry Integration
The secrets management script works alongside the existing Poetry-based deployment system:
- **Independent Operation**: Can be used independently of Poetry
- **Environment Consistency**: Uses same environment variables as deployment scripts
- **AWS Profile**: Uses same AWS profile configuration

### Deployment Workflow
```bash
# 1. Setup secrets
python scripts/manage_secrets.py setup

# 2. Validate secrets
python scripts/manage_secrets.py validate

# 3. Deploy infrastructure
poetry run service-deploy auth
```

## Benefits

### 🔒 Enhanced Security
- **Centralized Management**: All secrets in one secure location
- **Access Control**: Fine-grained IAM permissions
- **Audit Trail**: Complete visibility into secret operations
- **Encryption**: All secrets encrypted at rest

### 🚀 Operational Efficiency
- **Automated Setup**: Interactive guided setup process
- **Validation**: Built-in secret validation and health checks
- **Export**: Easy export to environment files
- **Rotation**: Automated secret rotation capabilities

### 📈 Scalability
- **Multi-Environment**: Support for dev/staging/prod environments
- **Extensible**: Easy to add new secret types
- **Standardized**: Consistent naming and tagging conventions
- **Future-Ready**: Designed to support additional services

## Migration from Manual Secret Management

### Before (Manual)
- Secrets stored in environment files
- Manual secret generation and management
- No audit trail or access control
- Risk of secrets in version control

### After (AWS Secrets Manager)
- Centralized secure storage
- Automated secret generation
- Complete audit trail
- IAM-based access control
- Environment-specific secret isolation

## Next Steps

### Immediate Actions
1. **Setup Core Secrets**: Run `python scripts/manage_secrets.py setup`
2. **Validate Configuration**: Run `python scripts/manage_secrets.py validate`
3. **Update Documentation**: Review and update team documentation

### Future Enhancements
1. **CI/CD Integration**: Add secrets validation to deployment pipelines
2. **Monitoring**: Add CloudWatch alarms for secret access patterns
3. **Automation**: Automated secret rotation schedules
4. **Backup**: Cross-region secret replication for disaster recovery

## Support

For questions or issues with the secrets management system:
1. Check the script help: `python scripts/manage_secrets.py --help`
3. Validate AWS credentials and permissions
4. Check CloudTrail logs for detailed operation history 