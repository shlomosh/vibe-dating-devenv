# Hosting Service

## Overview

Create a new hosting service for the Vibe Dating App backend that will set up and manage AWS infrastructure for hosting the frontend application on CloudFront under the `tma.vibe-dating.io` domain.

## Service Requirements

### Service Structure
The hosting service should follow the existing service architecture pattern established in `src/services/core` and `src/services/auth`:

```
src/services/hosting/
├── cloudformation/
│   ├── 01-cloudfront.yaml      # CloudFront distribution
│   ├── 02-s3.yaml              # S3 bucket for frontend assets
│   └── 03-route53.yaml         # Route53 DNS configuration
├── build.py                    # Service build script
├── deploy.py                   # Service deployment script
├── test.py                    # Service test script
└── README.md                   # Service documentation
```

### Implementation Requirements

#### 1. Build System Integration
- **Build Script**: Create `src/services/hosting/build.py` following the pattern from `src/services/auth/build.py`
- **Frontend Integration**: Use `VIBE_FRONTEND_PATH` environment variable to locate frontend repository
- **Vite Build Integration**: Leverage existing Vite build scripts from frontend repository
- **Build Artifacts**: Generate optimized frontend assets for CloudFront deployment and upload to S3

#### 2. Deployment Infrastructure
- **S3 Bucket**: Create dedicated S3 bucket for frontend assets with proper permissions
- **CloudFront Distribution**: Configure CloudFront with:
  - Custom domain: `tma.vibe-dating.io`
  - SSL certificate via ACM
  - Optimized caching policies for static assets
  - Security headers and CORS configuration
- **Route53 Configuration**: Set up DNS records for the custom domain
- **IAM Roles**: Create appropriate IAM roles for deployment automation

#### 3. Deployment Automation
- **Build Pipeline**: Integrate with frontend Vite build process
- **Asset Upload**: Automatically upload built assets to S3
- **Cache Invalidation**: Trigger CloudFront cache invalidation after deployment

#### 4. Service Integration
- **Core Stack Dependencies**: Integrate with existing core infrastructure
- **Parameters Integration**: Read deployment parameters from `src/config/parameters.yaml`
- **Environment Support**: Support dev, staging, and production environments using parameters.yaml
- **Secrets Management**: Use AWS Secrets Manager for sensitive configuration
- **Monitoring**: Integrate with CloudWatch for deployment monitoring

### Naming Conventions

Follow the existing naming patterns:
- **Service Name**: `hosting`
- **Stack Names**: `vibe-dating-hosting-{component}-{environment}`
- **S3 Bucket**: `vibe-dating-frontend-{environment}`
- **CloudFront Distribution**: `vibe-dating-frontend-{environment}`

### Deployment Parameters

The service should read deployment parameters from `src/config/parameters.yaml`:

- `Environment`: Deployment environment (dev/staging/prod)
- `DeploymentUUID`: Unique identifier for deployment tracking
- `AppRegion`: AWS region for deployment  
- `AppDomainName`: Domain for the application (tma.vibe-dating.io)
- `AllowedOrigins`: CORS allowed origins configuration

### Environment Variables

The service should use these environment variables in addition to parameters.yaml:
- `VIBE_FRONTEND_PATH`: Path to frontend repository
- `AWS_PROFILE`: AWS profile for credentials

### Testing Requirements

Create comprehensive tests following the pattern from `src/services/auth/test.py`:
- **Structure Tests**: Ensure proper code organization
- **Infrastructure Tests**: Validate CloudFormation templates
- **Integration Tests**: Test deployment automation

### Documentation

Create comprehensive documentation following the pattern from `src/services/auth/README.md`:
- **Service Overview**: Architecture and components
- **Deployment Guide**: Step-by-step deployment instructions
- **Configuration**: Environment variables, parameters.yaml, and secrets
- **Troubleshooting**: Common issues and solutions
- **Integration Guide**: How to integrate with frontend build process

### Security Considerations

- **SSL/TLS**: Configure HTTPS with proper SSL certificates
- **Security Headers**: Implement security headers in CloudFront
- **CORS Policy**: Configure appropriate CORS policies for Telegram domains
- **Access Control**: Implement proper IAM roles and policies
- **Secrets Management**: Use AWS Secrets Manager for sensitive data

### Performance Requirements

- **CDN Optimization**: Configure CloudFront for optimal performance
- **Caching Strategy**: Implement appropriate caching policies
- **Compression**: Enable gzip compression for assets
- **Edge Locations**: Optimize for target geographic regions

## Success Criteria

1. **Infrastructure Deployment**: Successfully deploy all AWS infrastructure components
2. **Frontend Integration**: Seamlessly integrate with frontend Vite build process
4. **Domain Configuration**: Properly configure `tma.vibe-dating.io` domain
5. **Testing Coverage**: Achieve comprehensive test coverage
6. **Documentation**: Complete and accurate documentation
7. **Security Compliance**: Meet all security requirements
8. **Performance**: Optimized for fast loading and caching

## Dependencies

- Existing core infrastructure (S3, IAM, CloudWatch)
- Frontend repository with Vite build configuration
- AWS CLI and credentials
- Poetry for dependency management

## Timeline

- **Week 1**: Infrastructure setup and CloudFormation templates
- **Week 2**: Testing and documentation
- **Week 3**: Deployment automation and optimization 