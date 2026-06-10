#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT_DIR/deploy"
STAMP="${1:-$(date +%Y%m%d-%H%M%S)}"
ZIP_PATH="$OUT_DIR/eduflow-backend-$STAMP.zip"

mkdir -p "$OUT_DIR"
rm -f "$ZIP_PATH"

cd "$ROOT_DIR"

zip -qr "$ZIP_PATH" \
  application.py \
  Procfile \
  requirements.txt \
  backend \
  .ebextensions \
  .platform \
  -x \
  "backend/.env" \
  "backend/.env.*" \
  "backend/.venv/*" \
  "backend/venv/*" \
  "backend/uploads/*" \
  "backend/**/__pycache__/*" \
  "backend/**/*.pyc"

echo "$ZIP_PATH"
