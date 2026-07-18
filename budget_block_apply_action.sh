#!/bin/bash

# Usage:
#   ./budget-policy.sh attach
#   ./budget-policy.sh detach

ACTION=$1

if [[ "$ACTION" != "attach" && "$ACTION" != "detach" ]]; then
    echo "Usage: $0 [attach|detach]"
    exit 1
fi

export AWS_PROFILE=vibe-dev
echo "Using AWS profile: $AWS_PROFILE"

POLICY_ARN="arn:aws:iam::aws:policy/AWSDenyAll"

mapfile -t ROLES < <(aws iam list-roles \
    --query "Roles[?starts_with(RoleName, 'shoss-')].RoleName" --output text | tr '\t' '\n')

if [[ ${#ROLES[@]} -eq 0 ]]; then
    echo "No shoss-* roles found."
    exit 1
fi
echo "Running action: $ACTION"
echo "Policy: $POLICY_ARN"
echo ""

for ROLE in "${ROLES[@]}"; do
    echo "Processing role: $ROLE"

    ATTACHED=$(aws iam list-attached-role-policies --role-name "$ROLE" \
        --query "AttachedPolicies[?PolicyArn=='$POLICY_ARN']" --output text)

    if [[ "$ACTION" == "attach" ]]; then
        if [[ -z "$ATTACHED" ]]; then
            echo "  -> Attaching AWSDenyAll..."
            aws iam attach-role-policy --role-name "$ROLE" --policy-arn "$POLICY_ARN"
            [[ $? -eq 0 ]] && echo "  -> Success" || echo "  -> FAILED"
        else
            echo "  -> Already attached. Skipping."
        fi
    fi

    if [[ "$ACTION" == "detach" ]]; then
        if [[ -n "$ATTACHED" ]]; then
            echo "  -> Detaching AWSDenyAll..."
            aws iam detach-role-policy --role-name "$ROLE" --policy-arn "$POLICY_ARN"
            [[ $? -eq 0 ]] && echo "  -> Success" || echo "  -> FAILED"
        else
            echo "  -> Not attached. Skipping."
        fi
    fi

    echo ""
done

echo "Done."

