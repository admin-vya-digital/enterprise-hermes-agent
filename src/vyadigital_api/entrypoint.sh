#!/bin/sh
# Exporta cada Docker secret montado em /run/secrets/* como variável de
# ambiente (nome do arquivo = nome da variável) antes de delegar para o
# comando real do container. Mesmo padrão usado em src/docker_hermes.
set -e

if [ -d /run/secrets ]; then
  for f in /run/secrets/*; do
    [ -f "$f" ] || continue
    export "$(basename "$f")=$(cat "$f")"
  done
fi

exec "$@"
