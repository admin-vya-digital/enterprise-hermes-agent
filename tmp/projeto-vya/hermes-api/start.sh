#!/usr/bin/env bash
# start.sh — Inicia o vya-workforce-api usando o venv do Hermes.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${VYA_HERMES_DIR:-$SCRIPT_DIR/../hermes-agent}/venv"
SERVER_DIR="$SCRIPT_DIR/server"
PORT="${VYA_PORT:-8700}"

if [ -z "$VYA_API_KEY" ]; then
  echo "ERRO: variável VYA_API_KEY não definida."
  echo "  export VYA_API_KEY=<sua-chave>"
  exit 1
fi

if [ ! -d "$VENV" ]; then
  echo "ERRO: venv do Hermes não encontrado em $VENV"
  exit 1
fi

# Instalar deps próprias do projeto no venv do Hermes (idempotente)
DEPS_FILE="$SCRIPT_DIR/requirements.txt"
if [ -f "$DEPS_FILE" ]; then
  echo "→ Verificando dependências..."
  "$VENV/bin/pip" install -q -r "$DEPS_FILE"
fi

echo "→ Iniciando vya-workforce-api na porta $PORT"
cd "$SERVER_DIR"
exec "$VENV/bin/uvicorn" app:app --host 0.0.0.0 --port "$PORT" --reload
