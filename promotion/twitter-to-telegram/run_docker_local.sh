#!/usr/bin/env bash
# Run the Fargate promotion image locally with a bind-mounted /promotion dir
# (instead of the S3 Files mount) to reproduce / debug task hangs off-AWS.
#
# This isolates the cause: if it hangs here too, it's the app/network; if it only
# hangs on Fargate, the S3 Files mount is the suspect.
#
# NOTE: it posts to the REAL Telegram channels and downloads from x.com. Resource
# and state changes are written only to the local mount (./.local-mount), never
# back to S3.
#
# Usage: AWS_PROFILE=vibe-dev ./run_docker_local.sh [channel ...]

set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
PROFILE="${AWS_PROFILE:-vibe-dev}"
BUCKET="${PROMOTION_BUCKET:-shoss-promotion}"
IMAGE="${IMAGE:-shoss-promotion:local}"
CHANNELS="${*:-GayCheckMyAss GayCheckMeOut}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
MOUNT="$SCRIPT_DIR/.local-mount"

[[ -f .env ]] || { echo "ERROR: .env not found" >&2; exit 1; }

echo "==> Building image $IMAGE"
docker build -f aws/fargate/Dockerfile -t "$IMAGE" .

echo "==> Staging local mount at $MOUNT"
mkdir -p "$MOUNT/resources" "$MOUNT/state"
cp config.fargate.json "$MOUNT/config.json"
cp resources/*.jpg "$MOUNT/resources/" 2>/dev/null || true

# Pull the live CSV so we process the same rows production would (read-only from S3).
export AWS_PROFILE="$PROFILE" AWS_DEFAULT_REGION="$REGION"
if aws s3 cp "s3://$BUCKET/resources/resources.csv" "$MOUNT/resources/resources.csv" 2>/dev/null; then
  echo "    pulled live resources.csv from s3://$BUCKET/"
else
  echo "    S3 CSV unavailable — using local resources/resources.csv"
  cp resources/resources.csv "$MOUNT/resources/resources.csv"
fi

# The image runs /opt/promotion (baked code) since the local mount has no app/ dir,
# so this exercises exactly the code in the freshly built image.
echo "==> Running container (channels: $CHANNELS)"
docker run --rm -it \
  --env-file .env \
  -e PROMOTION_MOUNT=/promotion \
  -e PROMOTION_CHANNELS="$CHANNELS" \
  -v "$MOUNT:/promotion" \
  "$IMAGE"

echo "==> Container exited. Local state is under $MOUNT (not synced to S3)."
