#!/usr/bin/env bash
# Trigger a one-off ECS Fargate promotion run — the same task the 6-hour
# EventBridge schedule launches. Network config (subnet/SG) and task definition
# are taken from the CloudFormation stack output, so nothing is hardcoded.
#
# Usage: AWS_PROFILE=vibe-dev ./run_ecs.sh [--follow]
#   --follow   tail the task's CloudWatch logs after starting it

set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
ENV="${ENVIRONMENT:-dev}"
PROFILE="${AWS_PROFILE:-vibe-dev}"
STACK="shoss-promotion-fargate-${ENV}"
LOG_GROUP="/ecs/shoss-promotion-${ENV}"

FOLLOW=0
[[ "${1:-}" == "--follow" ]] && FOLLOW=1

export AWS_PROFILE="$PROFILE"
export AWS_DEFAULT_REGION="$REGION"

echo "==> profile=$PROFILE region=$REGION stack=$STACK"

RUN_CMD="$(aws cloudformation describe-stacks --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='RunTaskCommand'].OutputValue" --output text)"

if [[ -z "$RUN_CMD" || "$RUN_CMD" == "None" ]]; then
  echo "ERROR: RunTaskCommand output not found — is stack $STACK deployed?" >&2
  exit 1
fi

# --enable-execute-command lets you `aws ecs execute-command` into this task.
echo "==> $RUN_CMD --enable-execute-command"
TASK_ARN="$(eval "$RUN_CMD" --enable-execute-command --query 'tasks[0].taskArn' --output text)"

if [[ -z "$TASK_ARN" || "$TASK_ARN" == "None" ]]; then
  echo "ERROR: task did not start (check ECS console / RunTask failures)" >&2
  exit 1
fi

TASK_ID="${TASK_ARN##*/}"
echo "==> Started task: $TASK_ARN"
echo "    Exec in (once RUNNING): aws ecs execute-command --cluster shoss-promotion-${ENV} \\"
echo "             --task $TASK_ID --container promotion --interactive --command /bin/bash --region $REGION"

if [[ "$FOLLOW" -eq 1 ]]; then
  echo "==> Waiting for task to stop, then showing logs..."
  aws ecs wait tasks-stopped --cluster shoss-promotion-"${ENV}" --tasks "$TASK_ARN" || true
  aws logs tail "$LOG_GROUP" --since 15m
else
  echo "    Follow logs: aws logs tail $LOG_GROUP --follow"
fi
