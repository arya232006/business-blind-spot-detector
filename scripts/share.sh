#!/usr/bin/env bash
# Share the backend running on THIS machine with anyone on the internet, for as long as this script runs.
#
#   scripts/share.sh            # needs: cloudflared  (brew install cloudflared) - free, no account required
#
# What it does
#   1. starts the FastAPI backend on localhost:$PORT in PUBLIC_MODE (destructive endpoints disabled, open CORS)
#   2. opens a Cloudflare quick tunnel -> a public https://<random>.trycloudflare.com URL
#   3. optionally publishes that URL to a public GitHub Gist so the hosted frontend finds it automatically
#      (set BBSD_GIST_ID=<gist id> and have `gh` logged in; the gist file must be called backend.json)
#   4. Ctrl+C stops everything and marks the backend offline in the gist.
#
# SECURITY: the API has no login. While this runs, anyone with the URL can read, upload and analyse data stored in the
# local database and use CPU on this machine. Share only demo data; use a separate DATABASE_URL if you care.
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-8000}"
PY="${PYTHON:-.venv/bin/python}"
LOG_DIR="${LOG_DIR:-logs}"
mkdir -p "$LOG_DIR"

command -v cloudflared >/dev/null 2>&1 || { echo "cloudflared not found. Install it:  brew install cloudflared"; exit 1; }
[ -x "$PY" ] || { echo "Python venv not found at $PY (see README: Installation)"; exit 1; }

pids=()
publish() {  # $1 = url or empty
  [ -n "${BBSD_GIST_ID:-}" ] || return 0
  local f; f="$(mktemp)"; printf '{"url": "%s"}\n' "$1" > "$f"
  gh gist edit "$BBSD_GIST_ID" -f backend.json "$f" >/dev/null 2>&1 && echo "  registry gist updated" || echo "  (could not update the gist - check 'gh auth status')"
  rm -f "$f"
}
cleanup() { echo; echo "Stopping…"; publish ""; for p in "${pids[@]:-}"; do kill "$p" 2>/dev/null || true; done; exit 0; }
trap cleanup INT TERM

echo "Starting backend on :$PORT (PUBLIC_MODE)…"
PUBLIC_MODE=true CORS_ORIGINS="*" "$PY" -m uvicorn backend.main:app --host 127.0.0.1 --port "$PORT" > "$LOG_DIR/backend.log" 2>&1 &
pids+=($!)
for _ in $(seq 1 60); do curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && break; sleep 1; done
curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null || { echo "Backend did not start - see $LOG_DIR/backend.log"; cleanup; }

echo "Opening tunnel…"
cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$PORT" > "$LOG_DIR/tunnel.log" 2>&1 &
pids+=($!)
URL=""
for _ in $(seq 1 45); do
  URL="$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG_DIR/tunnel.log" | head -1 || true)"
  [ -n "$URL" ] && break; sleep 1
done
[ -n "$URL" ] || { echo "No tunnel URL - see $LOG_DIR/tunnel.log"; cleanup; }
curl -fsS "$URL/health" >/dev/null 2>&1 || sleep 4   # DNS for a fresh tunnel can take a few seconds

echo
echo "✅ Backend is public:  $URL"
echo "   API docs:           $URL/docs"
publish "$URL"
[ -n "${BBSD_GIST_ID:-}" ] || echo "   (no BBSD_GIST_ID set: enter this URL under ⚙ Backend settings in the web app)"
echo "Press Ctrl+C to stop sharing."
wait
