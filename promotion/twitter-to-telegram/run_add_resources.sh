#!/usr/bin/env bash
# Append new resource rows to the live resources.csv on S3.
# Only rows with a URL not already present are added (safe to re-run).
#
# Usage: AWS_PROFILE=vibe-dev ./run_add_resources.sh <appended_file>
#   e.g. AWS_PROFILE=vibe-dev ./run_add_resources.sh new_resources.csv

set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
PROFILE="${AWS_PROFILE:-vibe-dev}"
BUCKET="${PROMOTION_BUCKET:-shoss-promotion}"
CSV_KEY="resources/resources.csv"
HEADER="url,date,source,class"

ADD_FILE="${1:?usage: ./append_to_resource.sh <appended_file>}"
[[ -f "$ADD_FILE" ]] || { echo "ERROR: $ADD_FILE not found" >&2; exit 1; }
[[ "$(head -1 "$ADD_FILE")" == "$HEADER" ]] || {
  echo "ERROR: $ADD_FILE header must be: $HEADER" >&2; exit 1; }

export AWS_PROFILE="$PROFILE"
export AWS_DEFAULT_REGION="$REGION"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
csv="$work/resources.csv"

echo "==> Fetching s3://$BUCKET/$CSV_KEY"
aws s3 cp "s3://$BUCKET/$CSV_KEY" "$csv"
[[ -n "$(tail -c1 "$csv")" ]] && echo >> "$csv"   # ensure trailing newline

added=0 skipped=0
while IFS= read -r row; do
  [[ -z "$row" ]] && continue
  url="${row%%,*}"
  if grep -qF -- "$url," "$csv"; then              # already present
    skipped=$((skipped + 1))
  else
    printf '%s\n' "$row" >> "$csv"
    added=$((added + 1))
  fi
done < <(tail -n +2 "$ADD_FILE")

echo "==> $added new row(s), $skipped already present"
if [[ "$added" -gt 0 ]]; then
  echo "==> Uploading updated resources.csv ($(($(wc -l < "$csv") - 1)) rows)"
  aws s3 cp "$csv" "s3://$BUCKET/$CSV_KEY"
else
  echo "==> Nothing to upload"
fi
