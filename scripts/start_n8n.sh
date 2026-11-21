#!/usr/bin/env bash
# Starts n8n with SignalStudio's settings read from .env (no keys typed or copied by hand).
# Needs Node.js (https://nodejs.org, LTS). Usage:  bash scripts/start_n8n.sh
set -euo pipefail
cd "$(dirname "$0")/.."
get() { grep -E "^$1=" .env | head -1 | cut -d= -f2-; }
export SIGNALSTUDIO_API="${SIGNALSTUDIO_API:-http://localhost:8000}"
export SIGNALSTUDIO_TOKEN="$(get API_TOKEN)"
export TELEGRAM_BOT_TOKEN="$(get TELEGRAM_BOT_TOKEN)"
export TELEGRAM_CHAT_ID="$(get TELEGRAM_CHAT_ID)"
export N8N_BLOCK_ENV_ACCESS_IN_NODE=false   # lets the workflows read the values above via $env
export GENERIC_TIMEZONE=Asia/Kolkata
export TZ=Asia/Kolkata
# Optional: a public https tunnel URL so Telegram Approve/Reject buttons work from your phone
if [ -n "${PUBLIC_N8N_URL:-}" ]; then export WEBHOOK_URL="$PUBLIC_N8N_URL"; fi
echo "n8n → http://localhost:5678   (SignalStudio API: $SIGNALSTUDIO_API)"
exec npx --yes n8n
