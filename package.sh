#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
OUTPUT="${SCRIPT_DIR}/drone-ops-ai-reporter-submission.zip"

command -v zip >/dev/null 2>&1 || {
  echo "Error: the zip utility is required." >&2
  exit 1
}

rm -f "$OUTPUT"

cd "$SCRIPT_DIR"
zip -q "$OUTPUT" \
  app.py \
  agent.py \
  data_cleaner.py \
  monday_client.py \
  requirements.txt \
  README.md \
  "Decision Log.md" \
  DEPLOYMENT.md \
  tests/test_data_cleaner.py \
  -x '__pycache__/*' '.git/*' '.env' '.env.*' '*.pyc'

echo "Created: $OUTPUT"
echo "Included source, documentation, requirements, and offline tests."
