#!/bin/bash
set -euo pipefail

APP_DIR="/var/app/current"
MIGRATION_PATH="$APP_DIR/backend/migrations/027_upgrade_role_token_limits_to_1m.py"
PYTHON_BIN=""

for candidate in /var/app/venv/*/bin/python3 /var/app/venv/*/bin/python; do
  if [ -x "$candidate" ]; then
    PYTHON_BIN="$candidate"
    break
  fi
done

if [ ! -f "$MIGRATION_PATH" ]; then
  echo "[eduflow] token-limit migration not found; skipping."
  exit 0
fi

if [ -z "$PYTHON_BIN" ]; then
  echo "[eduflow] app virtualenv python not found; skipping token-limit migration."
  exit 0
fi

echo "[eduflow] running token-limit migration 027..."
cd "$APP_DIR"
if ! "$PYTHON_BIN" "$MIGRATION_PATH"; then
  echo "[eduflow] token-limit migration 027 failed; continuing deploy."
  exit 0
fi
echo "[eduflow] token-limit migration 027 completed."
