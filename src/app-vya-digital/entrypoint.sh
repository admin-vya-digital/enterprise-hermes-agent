#!/bin/sh
# Exporta cada Docker secret montado em /run/secrets/* como variável de
# ambiente (nome do arquivo = nome da variável) antes de delegar para o
# comando real do container. Mesmo padrão usado em
# src/hermes_agent/entrypoint.sh e src/vyadigital_api/entrypoint.sh — sem
# isso, VYA_API_KEY (Docker secret) nunca vira a env var que
# lib/vya_api_client.py lê.
set -e

if [ -d /run/secrets ]; then
  for f in /run/secrets/*; do
    [ -f "$f" ] || continue
    export "$(basename "$f")=$(cat "$f")"
  done
fi

exec "$@"
