#!/usr/bin/env bash
# find-free-port.sh — encontra a primeira porta TCP livre a partir de uma porta inicial
# Uso: ./find-free-port.sh [start_port]   (default: 3000)
# Imprime a porta livre encontrada em stdout e sai com 0. Sai com 1 se nada livre até 3099.

set -euo pipefail

START="${1:-3000}"
MAX=3099
PORT="$START"

while [ "$PORT" -le "$MAX" ]; do
  if ! lsof -i ":$PORT" >/dev/null 2>&1; then
    echo "$PORT"
    exit 0
  fi
  PORT=$((PORT + 1))
done

echo "Nenhuma porta livre entre $START e $MAX" >&2
exit 1