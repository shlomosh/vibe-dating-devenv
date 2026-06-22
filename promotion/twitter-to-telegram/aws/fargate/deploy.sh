#!/usr/bin/env bash
# Build image, sync config/resources to S3, deploy the Fargate stack.
# The task accesses config/resources/state via the S3 Files mount at /promotion.
# Usage: AWS_PROFILE=vibe-dev ./aws/fargate/deploy.sh

set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
ENV="${ENVIRONMENT:-dev}"
STACK="shoss-promotion-fargate-${ENV}"
PROFILE="${AWS_PROFILE:-vibe-dev}"
BUCKET="${PROMOTION_BUCKET:-shoss-promotion}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROMOTION_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
TEMPLATE="$SCRIPT_DIR/cloudformation/promotion-fargate.yaml"
ENV_FILE="$PROMOTION_DIR/.env"

export AWS_PROFILE="$PROFILE"
export AWS_DEFAULT_REGION="$REGION"

[[ -f "$ENV_FILE" ]] || { echo "ERROR: $ENV_FILE not found" >&2; exit 1; }
[[ -f "$PROMOTION_DIR/resources/resources.csv" ]] || { echo "ERROR: resources.csv not found" >&2; exit 1; }

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR_REPO="shoss-promotion-${ENV}"
IMAGE_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}:${IMAGE_TAG}"

SUBNET_ID="$(aws ec2 describe-subnets \
  --filters Name=default-for-az,Values=true Name=availability-zone,Values=us-east-1a \
  --query 'Subnets[0].SubnetId' --output text)"
VPC_ID="$(aws ec2 describe-subnets --subnet-ids "$SUBNET_ID" --query 'Subnets[0].VpcId' --output text)"
# Route table for the subnet (falls back to the VPC main table) — the S3 Gateway
# endpoint route is added here so the S3 Files mount target can reach S3.
ROUTE_TABLE_ID="$(aws ec2 describe-route-tables \
  --filters Name=association.subnet-id,Values="$SUBNET_ID" \
  --query 'RouteTables[0].RouteTableId' --output text)"
if [[ -z "$ROUTE_TABLE_ID" || "$ROUTE_TABLE_ID" == "None" ]]; then
  ROUTE_TABLE_ID="$(aws ec2 describe-route-tables \
    --filters Name=vpc-id,Values="$VPC_ID" Name=association.main,Values=true \
    --query 'RouteTables[0].RouteTableId' --output text)"
fi

echo "==> profile=$PROFILE region=$REGION stack=$STACK bucket=$BUCKET rt=$ROUTE_TABLE_ID"

echo "==> Ensuring ECR repository exists"
aws ecr describe-repositories --repository-names "$ECR_REPO" 2>/dev/null \
  || aws ecr create-repository --repository-name "$ECR_REPO" >/dev/null

echo "==> Building and pushing Docker image $IMAGE_URI"
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
docker build -f "$SCRIPT_DIR/Dockerfile" -t "$IMAGE_URI" "$PROMOTION_DIR"
docker push "$IMAGE_URI"

echo "==> Syncing config and resources to s3://$BUCKET/"
# Bucket must exist before stack deploy. S3 Files needs versioning + SSE-S3. App
# code is baked into the image, so there is no app/ overlay to sync.
aws s3 mb "s3://$BUCKET" 2>/dev/null || true
aws s3api put-bucket-versioning --bucket "$BUCKET" \
  --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption --bucket "$BUCKET" \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
aws s3 cp "$PROMOTION_DIR/config.fargate.json" "s3://$BUCKET/config.json"
# resources.csv is the live state store — the task writes used-dates back to it.
# Sync everything else, but never overwrite or delete the live CSV; seed it only
# on first deploy when it does not yet exist in the bucket.
aws s3 sync "$PROMOTION_DIR/resources/" "s3://$BUCKET/resources/" --delete --exclude "resources.csv"
if aws s3api head-object --bucket "$BUCKET" --key resources/resources.csv >/dev/null 2>&1; then
  echo "    (keeping existing s3://$BUCKET/resources/resources.csv — live state preserved)"
else
  echo "    (seeding s3://$BUCKET/resources/resources.csv)"
  aws s3 cp "$PROMOTION_DIR/resources/resources.csv" "s3://$BUCKET/resources/resources.csv"
fi

echo "==> Updating Secrets Manager from .env"
export ENV_FILE
SECRET_JSON="$(python3 <<'PY'
import json, os
from pathlib import Path
env = {}
for line in Path(os.environ["ENV_FILE"]).read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    env[k.strip()] = v.strip()
print(json.dumps({
    "TELEGRAM_BOT_TOKEN": env.get("TELEGRAM_BOT_TOKEN", ""),
    "X_AUTH_TOKEN": env.get("X_AUTH_TOKEN", ""),
    "X_CT0": env.get("X_CT0", ""),
}))
PY
)"

echo "==> Deploying CloudFormation stack"
aws cloudformation deploy \
  --stack-name "$STACK" \
  --template-file "$TEMPLATE" \
  --parameter-overrides \
    "Environment=$ENV" \
    "BucketName=$BUCKET" \
    "SubnetId=$SUBNET_ID" \
    "VpcId=$VPC_ID" \
    "RouteTableId=$ROUTE_TABLE_ID" \
    "ImageUri=$IMAGE_URI" \
    "ScheduleExpression=rate(6 hours)" \
    "TaskCpu=${TASK_CPU:-4096}" \
    "TaskMemory=${TASK_MEMORY:-16384}" \
  --capabilities CAPABILITY_IAM \
  --no-fail-on-empty-changeset

aws secretsmanager put-secret-value \
  --secret-id "shoss/promotion/${ENV}/credentials" \
  --secret-string "$SECRET_JSON"

echo "==> Stack outputs:"
aws cloudformation describe-stacks --stack-name "$STACK" \
  --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' --output table

echo ""
echo "Update workflow (no image rebuild needed for config only):"
echo "  aws s3 cp config.fargate.json s3://$BUCKET/config.json"
echo "  # NOTE: resources/resources.csv is live state — do not overwrite it; edit in place."
echo ""
echo "Manual run:"
CLUSTER="$(aws cloudformation describe-stacks --stack-name "$STACK" --query "Stacks[0].Outputs[?OutputKey=='ClusterName'].OutputValue" --output text)"
TASK_DEF="$(aws cloudformation describe-stacks --stack-name "$STACK" --query "Stacks[0].Outputs[?OutputKey=='TaskDefinitionArn'].OutputValue" --output text)"
echo "  aws ecs run-task --cluster $CLUSTER --task-definition $TASK_DEF --launch-type FARGATE \\"
echo "    --network-configuration 'awsvpcConfiguration={subnets=[$SUBNET_ID],securityGroups=[$(aws cloudformation describe-stack-resources --stack-name $STACK --logical-resource-id EcsSecurityGroup --query 'StackResources[0].PhysicalResourceId' --output text)],assignPublicIp=ENABLED}'"
