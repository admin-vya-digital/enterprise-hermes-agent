#!/bin/bash

set -euo pipefail

BRIDGE_LOG="${BRIDGE_LOG:-$HOME/.hermes/whatsapp/bridge.log}"
SESSION_DIR="${SESSION_DIR:-$HOME/.hermes/whatsapp/session}"
PORT="${PORT:-3000}"

print_usage() {
  echo "Usage: $0 [OPTION]"
  echo "  --log        Show last 30 log lines"
  echo "  --health     Check bridge health (mode, connection status)"
  echo "  --port       Check if port $PORT is free"
  echo "  --session    Inspect session dir (creds.json age, size)"
  echo "  --all        Run all checks"
}

check_port() {
  if lsof -i :$PORT > /dev/null; then
    echo "❌ Port $PORT is IN USE"
    lsof -i :$PORT
  else
    echo "✅ Port $PORT is FREE"
  fi
}

check_log() {
  echo "--- Last 30 log lines ---"
  tail -n 30 "$BRIDGE_LOG" || true
}

check_health() {
  echo "--- Health Check Summary ---"
  
  if [ ! -f "$BRIDGE_LOG" ]; then
    echo "❌ Bridge log does not exist at $BRIDGE_LOG"
    return 1
  fi
  
  if grep -q "mode: chat" "$BRIDGE_LOG"; then
    echo "✅ Mode detected: chat"
  elif grep -q "mode: self-chat" "$BRIDGE_LOG"; then
    echo "❌ Mode detected: self-chat (should be 'chat')"
  else
    echo "⚠️  Mode not found in recent logs"
  fi
  
  if grep -q "✅ WhatsApp connected!" "$BRIDGE_LOG"; then
    echo "✅ Bridge reports CONNECTED"
  else
    echo "❌ No '✅ WhatsApp connected!' marker in recent logs"
  fi
  
  if grep -q "self_chat_mode_rejects_non_self" "$BRIDGE_LOG"; then
    echo "❌ Found rejections due to self-chat mode"
  fi
  
  if grep -q "EADDRINUSE" "$BRIDGE_LOG"; then
    echo "❌ Found address-in-use errors"
  fi
}

check_session() {
  echo "--- Session Dir ---"
  if [ -d "$SESSION_DIR" ]; then
    echo "✅ Session dir exists"
    if [ -f "$SESSION_DIR/creds.json" ]; then
      SIZE=$(wc -c < "$SESSION_DIR/creds.json")
      AGE=$(find "$SESSION_DIR/creds.json" -mtime -7 -printf '%TY-%Tm-%Td %TH:%TM\n' 2>/dev/null || echo "unknown")
      echo "  creds.json size: $SIZE bytes, modified: $AGE"
    else
      echo "❌ creds.json MISSING"
    fi
  else
    echo "❌ Session dir does not exist"
  fi
}

main() {
  if [ $# -eq 0 ]; then
    print_usage
    exit 0
  fi
  
  while [ -n "${1:-}" ]; do
    case "$1" in
      --log)    check_log; ;;
      --health) check_health; ;;
      --port)   check_port; ;;
      --session) check_session; ;;
      --all)    check_health; echo; check_port; echo; check_session; ;;
      --help)   print_usage; exit 0; ;;
      *)        echo "Unknown option: $1"; print_usage; exit 1; ;;
    esac
    shift
  done
}

main "$@"
