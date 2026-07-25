#!/usr/bin/env bash
# Run promotion locally against the live S3 state.
#   1. Pull resources.csv + state.json down from S3 (the source of truth).
#   2. Run post_all.sh (both channels) using local config.json.
#   3. Push the updated resources.csv + state.json back to S3.
#
# Use this to post from your workstation while keeping the same live state the
# scheduled Fargate task uses. Do not run it concurrently with an ECS task.
#
# Usage: AWS_PROFILE=vibe-dev ./run_local.sh

set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
PROFILE="${AWS_PROFILE:-vibe-dev}"
BUCKET="${PROMOTION_BUCKET:-shoss-promotion}"

export AWS_PROFILE="$PROFILE"
export AWS_DEFAULT_REGION="$REGION"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

CSV_KEY="resources/resources.csv"          # S3 key  <-> local resources/resources.csv
STATE_KEY="state/state.json"               # S3 key  <-> local state.json

s3_has() { aws s3api head-object --bucket "$BUCKET" --key "$1" >/dev/null 2>&1; }

echo "==> profile=$PROFILE region=$REGION bucket=$BUCKET"

echo "==> Pulling live state from s3://$BUCKET/"
if s3_has "$CSV_KEY"; then
  aws s3 cp "s3://$BUCKET/$CSV_KEY" resources/resources.csv
else
  echo "    (no s3://$BUCKET/$CSV_KEY — using local resources/resources.csv as source)"
fi
if s3_has "$STATE_KEY"; then
  aws s3 cp "s3://$BUCKET/$STATE_KEY" state.json
else
  echo "    (no s3://$BUCKET/$STATE_KEY — starting from local state.json if present)"
fi

echo "==> Posting..."
# Persist state regardless of how the run ends: resources.csv/state.json are
# written in place per successful post, so we always push back what we have.
./twitter_to_telegram_promotion.py run --channel GayCheckMyAss
./twitter_to_telegram_promotion.py run --channel GayCheckMeOut
./twitter_to_telegram_promotion.py run --channel OhDaddy
./twitter_to_telegram_promotion.py run --channel HotGays
rc=$?

echo "==> Pushing updated state back to s3://$BUCKET/"
aws s3 cp resources/resources.csv "s3://$BUCKET/$CSV_KEY"
if [[ -f state.json ]]; then
  aws s3 cp state.json "s3://$BUCKET/$STATE_KEY"
fi

rm -rf downloads/*

echo "==> done (post_all exit $rc)"
exit "$rc"
