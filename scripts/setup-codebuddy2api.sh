#!/usr/bin/env bash
set -e

# Start CodeBuddy2api — an OpenAI-compatible proxy for Tencent CodeBuddy.
# Usage: ./scripts/setup-codebuddy2api.sh [directory]
# Default directory: ./CodeBuddy2api

TARGET_DIR="${1:-./CodeBuddy2api}"

if [ ! -d "$TARGET_DIR" ]; then
  echo "==> Cloning Sliverkiss/CodeBuddy2api into $TARGET_DIR ..."
  git clone https://github.com/Sliverkiss/CodeBuddy2api.git "$TARGET_DIR"
fi

cd "$TARGET_DIR"

echo "==> Creating Python virtual environment ..."
python3 -m venv venv
source venv/bin/activate

echo "==> Installing dependencies ..."
pip install -r requirements.txt

if [ ! -f .env ]; then
  echo "==> Creating .env template ..."
  cat > .env <<'EOF'
# CodeBuddy edition:
#   internal / ioa  = China edition (copilot.tencent.com)
#   public          = International edition (www.codebuddy.ai)
CODEBUDDY_INTERNET_ENVIRONMENT=internal

# Authentication mode: api_key (recommended) or oauth
CODEBUDDY_AUTH_MODE=api_key

# Your CodeBuddy API Key
CODEBUDDY_API_KEY=your_codebuddy_api_key_here

# Optional: explicitly expose specific models, comma-separated
# CODEBUDDY_MODELS=auto-chat,kimi-k3,hy3-high
EOF
  echo ""
  echo "⚠️  Please edit $TARGET_DIR/.env with your CODEBUDDY_API_KEY and edition, then re-run this script."
  exit 0
fi

if grep -qE "your_codebuddy_api_key_here|^CODEBUDDY_API_KEY=$" .env; then
  echo "⚠️  CODEBUDDY_API_KEY in $TARGET_DIR/.env is still a placeholder. Please fill it in and re-run."
  exit 1
fi

echo "==> Starting CodeBuddy2api ..."
python web.py
