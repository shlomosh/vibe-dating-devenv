# Hosting Service

## Overview

The Hosting Service provides static hosting infrastructure for the Vibe Dating App frontend application. It sets up and manages AWS infrastructure for hosting the frontend application on CloudFront under the `tma.vibe-dating.io` domain.

## Architecture

### Components

The hosting service consists of three main infrastructure components:

1. **CloudFront Distribution** (`01-cloudfront.yaml`): Global CDN with SSL and security headers
2. **S3 Bucket** (`02-s3.yaml`): Secure storage for frontend assets
3. **Route53 DNS** (`03-route53.yaml`): DNS configuration for the custom domain

### Infrastructure Stack

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Route53 DNS   │    │ CloudFront CDN   │    │   S3 Bucket     │
│                 │    │                  │    │                 │
│ tma.vibe-       │◄───┤ • SSL Certificate│◄───┤ • Frontend      │
│ dating.io       │    │ • Security Headers│   │   Assets        │
│                 │    │ • Caching        │    │ • Versioning    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Features

### Security
- **SSL/TLS**: Automatic SSL certificate management via ACM
- **Security Headers**: Comprehensive security headers via Lambda@Edge
- **CORS Policy**: Configured for Telegram domains
- **Access Control**: S3 bucket with CloudFront-only access

### Performance
- **Global CDN**: CloudFront distribution with edge locations
- **Caching Strategy**: Optimized caching for different file types
- **Compression**: Gzip compression for text assets
- **HTTP/2**: Modern protocol support

### Reliability
- **Versioning**: S3 bucket versioning for rollback capability
- **Error Handling**: SPA routing support (404 → index.html)
- **Monitoring**: CloudWatch integration for performance monitoring

## Prerequisites

### AWS Requirements
- AWS CLI configured with appropriate credentials
- Route53 hosted zone for `vibe-dating.io`
- IAM permissions for CloudFormation, S3, CloudFront, Route53, ACM, and Lambda

### Frontend Requirements
- Frontend repository with Vite build configuration
- `package.json` with build script
- Node.js and npm installed

### Environment Variables
```bash
# Required for build process
export VIBE_FRONTEND_PATH="/Users/ont/vibe/vibe-dating-backend"

# Optional AWS configuration
export AWS_PROFILE="vibe-dev"
export AWS_REGION="il-central-1"
```

## Quick Start

### 1. Deploy Infrastructure

```bash
# Deploy hosting infrastructure
poetry run service-deploy hosting
```

This will create:
- S3 bucket for frontend assets
- CloudFront distribution with SSL
- Route53 DNS records
- Security headers Lambda function

### 2. Build and Deploy Frontend

```bash
# Set frontend path
export VIBE_FRONTEND_PATH="/Users/ont/vibe/vibe-dating-backend"

# Build and upload frontend assets
poetry run service-build hosting
```

This will:
- Install frontend dependencies
- Build frontend with Vite
- Upload assets to S3
- Invalidate CloudFront cache

### 3. Access Your Application

Your frontend will be available at: `https://tma.vibe-dating.io`

## Detailed Usage

### Deployment Commands

```bash
# Deploy infrastructure
poetry run service-deploy hosting

# Update infrastructure
poetry run service-update hosting

# Build frontend assets
poetry run service-build hosting

# Run tests
poetry run service-test hosting
```

### Manual Deployment

```bash
# Deploy S3 bucket
poetry run service-deploy hosting --stack s3

# Deploy CloudFront distribution
poetry run service-deploy hosting --stack cloudfront

# Deploy Route53 configuration
poetry run service-deploy hosting --stack route53
```

### Frontend Integration

The hosting service integrates with your frontend build process:

1. **Vite Configuration**: Uses existing Vite build scripts
2. **Asset Optimization**: Automatically optimizes and uploads assets
3. **Cache Management**: Handles CloudFront cache invalidation
4. **Environment Support**: Supports dev, staging, and production environments

### Environment Configuration

The service reads configuration from `src/config/parameters.yaml`:

```yaml
Environment: "dev"
DeploymentUUID: "8e64f92e-580e-11f0-80ef-00155d453b17"
AppRegion: "il-central-1"
AppDomainName: "tma.vibe-dating.io"
AllowedOrigins: "https://web.telegram.org,https://t.me,https://tma.vibe-dating.io"
```

## CloudFormation Templates

### 01-cloudfront.yaml - CloudFront Distribution

Sets up global CDN with advanced features:

- **Domain**: Custom domain with SSL certificate
- **Caching**: Optimized caching for different file types
- **Security**: Lambda@Edge for security headers
- **Performance**: HTTP/2, compression, edge optimization

### 02-s3.yaml - S3 Bucket

Creates a secure S3 bucket for frontend assets:

- **Bucket Name**: `vibe-dating-frontend-{environment}`
- **Security**: Private access, encryption, versioning
- **Lifecycle**: Automatic cleanup of old versions
- **Policy**: CloudFront-only access

### 03-route53.yaml - DNS Configuration

Configures DNS records for the custom domain:

- **A Record**: Points to CloudFront distribution
- **AAAA Record**: IPv6 support
- **CNAME**: www subdomain support
- **TXT Record**: Domain verification

## Security Features

### Security Headers

The CloudFront distribution includes comprehensive security headers:

```javascript
// Applied via Lambda@Edge
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), GEOHASH=()
```

### CORS Configuration

Configured for Telegram Mini-App requirements:

```javascript
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization
```

### Access Control

- S3 bucket is private with CloudFront-only access
- Origin Access Control (OAC) for secure S3 access
- IAM roles with minimal required permissions

## Performance Optimization

### Caching Strategy

Different file types have optimized caching:

- **HTML**: 24 hours (with cache invalidation on deployment)
- **CSS/JS**: 1 year (with versioning)
- **Images**: 1 year (with versioning)
- **Fonts**: 1 year (with versioning)

### Compression

- **Enabled**: For text assets (HTML, CSS, JS, SVG)
- **Disabled**: For binary assets (images, fonts)
- **Algorithm**: Gzip compression

### Edge Optimization

- **HTTP/2**: Modern protocol support
- **IPv6**: Dual-stack support
- **Price Class**: Optimized for cost and performance
- **Edge Locations**: Global distribution

## Monitoring and Maintenance

### CloudWatch Integration

- **Metrics**: Request count, error rates, latency
- **Logs**: Access logs and error logs
- **Alarms**: Automated alerting for issues

### Cache Management

```bash
# Manual cache invalidation
aws cloudfront create-invalidation \
  --distribution-id <DISTRIBUTION_ID> \
  --paths "/*"
```

### SSL Certificate Management

- **Automatic**: ACM handles certificate renewal
- **Validation**: DNS validation for domain ownership
- **Coverage**: Includes wildcard subdomains

## Troubleshooting

### Common Issues

#### 1. Frontend Build Fails

```bash
# Check frontend path
echo $VIBE_FRONTEND_PATH

# Verify package.json exists
ls $VIBE_FRONTEND_PATH/package.json

# Install dependencies manually
cd $VIBE_FRONTEND_PATH && npm install
```

#### 2. S3 Upload Fails

```bash
# Check AWS credentials
aws sts get-caller-identity

# Verify S3 bucket exists
aws s3 ls s3://vibe-dating-frontend-dev
```

#### 3. CloudFront Not Updating

```bash
# Check cache invalidation status
aws cloudfront list-invalidations --distribution-id <DISTRIBUTION_ID>

# Force cache invalidation
aws cloudfront create-invalidation --distribution-id <DISTRIBUTION_ID> --paths "/*"
```

#### 4. DNS Not Resolving

```bash
# Check Route53 records
aws route53 list-resource-record-sets --hosted-zone-id <ZONE_ID>

# Verify domain configuration
nslookup tma.vibe-dating.io
```

### Debug Commands

```bash
# Validate CloudFormation templates
poetry run service-deploy hosting --validate

# Check stack status
aws cloudformation describe-stacks --stack-name vibe-dating-hosting-s3-dev

# View stack outputs
aws cloudformation describe-stacks --stack-name vibe-dating-hosting-cloudfront-dev --query 'Stacks[0].Outputs'
```

## Development

### Local Development

```bash
# Clone repository
git clone <repository-url>
cd vibe-dating-backend

# Install dependencies
poetry install

# Set environment variables
export VIBE_FRONTEND_PATH="/Users/ont/vibe/vibe-dating-frontend"
export AWS_PROFILE="vibe-dev"

# Run tests
poetry run service-test hosting

# Deploy to dev environment
poetry run service-deploy hosting
```

### Adding New Features

1. **Update CloudFormation templates** in `cloudformation/`
2. **Modify deployment logic** in `deploy.py`
3. **Update build process** in `build.py`
4. **Add tests** in `test.py`
5. **Update documentation** in `README.md`

### Testing

```bash
# Run all tests
poetry run service-test hosting

# Run specific tests
python src/services/hosting/test.py

# Validate templates
aws cloudformation validate-template --template-body file://src/services/hosting/cloudformation/01-s3.yaml
```

## Cost Optimization

### CloudFront Pricing

- **Data Transfer**: Pay for data transferred out
- **Requests**: Pay per request
- **Price Class**: Use PriceClass_100 for cost optimization

### S3 Pricing

- **Storage**: Pay for stored data
- **Requests**: Pay for GET/PUT requests
- **Lifecycle**: Automatic cleanup reduces storage costs

### Cost Monitoring

```bash
# Check CloudFront usage
aws cloudfront get-distribution --id <DISTRIBUTION_ID>

# Monitor S3 usage
aws s3 ls s3://vibe-dating-frontend-dev --recursive --summarize
```

## Security Best Practices

### SSL/TLS

- Use ACM for automatic certificate management
- Enable HSTS for security
- Use TLS 1.2+ for modern security

### Access Control

- Restrict S3 access to CloudFront only
- Use IAM roles with minimal permissions
- Enable CloudTrail for audit logging

### Content Security

- Implement security headers
- Configure CORS properly
- Use Content Security Policy (CSP)

## Support

### Documentation

- **API Documentation**: `docs/api.md`
- **Architecture**: `docs/context.md`
- **Deployment**: This README

### Issues

For issues and questions:
1. Check the troubleshooting section
2. Review CloudFormation stack events
3. Check CloudWatch logs
4. Contact the development team

### Contributing

1. Follow the established patterns
2. Add comprehensive tests
3. Update documentation
4. Use Poetry for dependency management
5. Follow the code style guidelines 
