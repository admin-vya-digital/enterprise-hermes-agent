#!/bin/sh
# Exporta cada Docker secret montado em /run/secrets/* como variável de
# ambiente (nome do arquivo = nome da variável) antes de delegar para o
# comando real do container.
set -e

if [ -d /run/secrets ]; then
  for f in /run/secrets/*; do
    [ -f "$f" ] || continue
    export "$(basename "$f")=$(cat "$f")"
  done
fi

# O perfil "dashboard" (criado automaticamente por "hermes dashboard", ao
# contrário dos perfis de agente criados pela vya-workforce-api) nasce com
# sua própria cópia das skills embutidas no hermes-agent, sem os skills
# customizados do Vya. Troca por um symlink para o volume compartilhado
# /app/skills, igual ao que hermes-api/server/provision.py faz para perfis
# de agente — assim o perfil "dashboard" sempre vê o mesmo conjunto de
# skills, mesmo depois de recriar o container.
if [ -n "$HERMES_HOME" ] && [ -d /app/skills ] && [ -d "$HERMES_HOME" ]; then
  if [ -e "$HERMES_HOME/skills" ] && [ ! -L "$HERMES_HOME/skills" ]; then
    rm -rf "$HERMES_HOME/skills"
    ln -s /app/skills "$HERMES_HOME/skills"
  elif [ ! -e "$HERMES_HOME/skills" ]; then
    ln -s /app/skills "$HERMES_HOME/skills"
  fi
fi

exec "$@"
