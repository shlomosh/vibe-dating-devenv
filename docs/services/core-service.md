# Core Service

This document covers the CloudFormation deployment for the Vibe Dating App core infrastructure.

## Overview

The core service provides the foundational AWS infrastructure that all other services depend on:

- **S3 Bucket**: For storing Lambda function code and other artifacts
- **DynamoDB Table**: Main application database with KMS encryption
- **IAM Roles**: Execution roles for Lambda functions and API Gateway

## Stack Order

The stacks must be deployed in the following order due to dependencies:

1. **S3 Stack** (`01-s3.yaml`) - Creates the Lambda code bucket
2. **DynamoDB Stack** (`02-dynamodb.yaml`) - Creates the main database table and KMS key
3. **IAM Stack** (`03-iam.yaml`) - Creates execution roles (depends on S3 and DynamoDB)

## Prerequisites

- AWS CLI installed and configured
- Appropriate AWS credentials/permissions
- Python 3.11+ with boto3

## Deployment

### Using the Deployment Script

The `deploy.py` script handles the complete deployment process:

```bash
# Deploy to dev environment (default)
python deploy.py

# Deploy to specific environment
python deploy.py --environment staging

# Deploy to specific region
python deploy.py --region us-east-1

# Use specific AWS profile
python deploy.py --profile vibe-dating

# Use custom deployment UUID
python deploy.py --deployment-uuid "your-custom-uuid"
```

### Command Line Options

- `--environment`: Environment to deploy (dev, staging, prod) - default: dev
- `--region`: AWS region - default: il-central-1
- `--profile`: AWS profile to use
- `--deployment-uuid`: Custom deployment UUID (optional)

### Manual Deployment

If you prefer to deploy manually using AWS CLI:

```bash
# 1. Deploy S3 stack
aws cloudformation create-stack \
  --stack-name vibe-dating-core-s3-dev \
  --template-body file://01-s3.yaml \
  --parameters ParameterKey=Environment,ParameterValue=dev \
  --region il-central-1

# 2. Deploy DynamoDB stack
aws cloudformation create-stack \
  --stack-name vibe-dating-core-dynamodb-dev \
  --template-body file://02-dynamodb.yaml \
  --parameters ParameterKey=Environment,ParameterValue=dev \
  --region il-central-1

# 3. Deploy IAM stack (requires outputs from previous stacks)
aws cloudformation create-stack \
  --stack-name vibe-dating-core-iam-dev \
  --template-body file://03-iam.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=dev \
    ParameterKey=DynamoDBTableArn,ParameterValue=<from-dynamodb-stack> \
    ParameterKey=DynamoDBKMSKeyArn,ParameterValue=<from-dynamodb-stack> \
    ParameterKey=LambdaCodeBucketArn,ParameterValue=<from-s3-stack> \
  --capabilities CAPABILITY_NAMED_IAM \
  --region il-central-1
```

## Stack Details

### S3 Stack (`01-s3.yaml`)

Creates an S3 bucket for storing Lambda function code:

- **Bucket Name**: `vibe-dating-code-{environment}-{deployment-uuid}`
- **Features**: Versioning, encryption, public access blocking
- **Outputs**: Bucket name and ARN

### DynamoDB Stack (`02-dynamodb.yaml`)

Creates the main application database:

- **Table Name**: `vibe-dating-{environment}`
- **Features**: 
  - Single-table design with 6 GSIs
  - KMS encryption
  - Point-in-time recovery
  - Pay-per-request billing
- **Outputs**: Table name, ARN, KMS key ARN, and alias

### IAM Stack (`03-iam.yaml`)

Creates execution roles for Lambda functions and API Gateway:

- **LambdaExecutionRole**: For Lambda functions with DynamoDB, KMS, S3, and Secrets Manager access
- **ApiGatewayAuthorizerRole**: For API Gateway to invoke Lambda authorizers
- **Outputs**: Role ARNs

## Outputs

After successful deployment, the script will display all stack outputs. Key outputs include:

- **LambdaCodeBucketName**: S3 bucket for Lambda code
- **LambdaCodeBucketArn**: S3 bucket ARN
- **DynamoDBTableName**: Main database table name
- **DynamoDBTableArn**: Database table ARN
- **DynamoDBKMSKeyArn**: KMS key ARN for encryption
- **LambdaExecutionRoleArn**: Lambda execution role ARN
- **ApiGatewayAuthorizerRoleArn**: API Gateway authorizer role ARN

## Next Steps

After deploying the core infrastructure:

1. **Deploy Service Stacks**: Use the outputs to deploy service-specific stacks (auth, user, media, etc.)
2. **Configure Lambda Functions**: Use the IAM roles and S3 bucket for Lambda deployments
3. **Set Up Database**: Use the DynamoDB table for application data

## Troubleshooting

### Common Issues

1. **Stack Update Errors**: If a stack update fails, check the CloudFormation console for detailed error messages
2. **Permission Errors**: Ensure your AWS credentials have sufficient permissions for CloudFormation, IAM, S3, and DynamoDB
3. **Resource Conflicts**: If resources already exist, you may need to delete them first or use different names

### Cleanup

To remove all stacks:

```bash
# Delete in reverse order
aws cloudformation delete-stack --stack-name vibe-dating-core-iam-dev
aws cloudformation delete-stack --stack-name vibe-dating-core-dynamodb-dev
aws cloudformation delete-stack --stack-name vibe-dating-core-s3-dev
```

**Note**: The S3 bucket has a deletion policy of "Retain" to prevent accidental data loss.

## Security

- All resources are tagged with Environment and Service
- DynamoDB uses KMS encryption
- S3 bucket blocks public access
- IAM roles follow least privilege principle
- KMS key policies restrict access appropriately.