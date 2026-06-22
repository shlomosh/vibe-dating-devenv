#!/bin/bash
# Run the promotion for each channel. config.json, resources.csv and state.json
# live on the S3 Files mount at /promotion; the app code is baked into the image.
set -uo pipefail

MOUNT="${PROMOTION_MOUNT:-/promotion}"
CONFIG="${PROMOTION_CONFIG:-$MOUNT/config.json}"
APP_DIR="/opt/promotion"

mkdir -p "$MOUNT/state" /tmp/downloads

cd "$APP_DIR"
export PYTHONPATH="$APP_DIR"

CHANNELS="${PROMOTION_CHANNELS:-GayCheckMyAss GayCheckMeOut}"

# Run each channel independently: a failure in one must not skip the others.
status=0
for channel in $CHANNELS; do
  echo "==> run --channel $channel"
  if ! python twitter_to_telegram_promotion.py --config "$CONFIG" run --channel "$channel"; then
    echo "!! channel $channel failed" >&2
    status=1
  fi
done

echo "==> done (exit $status)"
exit "$status"
