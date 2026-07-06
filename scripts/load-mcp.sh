#!/usr/bin/env bash
# load-mcp.sh — Carrega variáveis de ambiente para MCP Servers
# Domínio: programming
# Gerado por scaffold.py — NÃO commitar este script com tokens reais
#
# Uso:
#   bash scripts/load-mcp.sh
#   make mcp
set -euo pipefail

SECRETS_ENV=".secrets/.env"

if [[ ! -f "$SECRETS_ENV" ]]; then
  echo "⚠️  .secrets/.env não encontrado."
  echo "   Crie o arquivo com os tokens necessários:"
  echo ""
  echo "   # .secrets/.env"
  echo "   GITHUB_PERSONAL_ACCESS_TOKEN=your-value-here"
  echo ""
  exit 1
fi

# Carrega sem poluir o histórico do shell
set -a; source "$SECRETS_ENV"; set +a

# Valida variáveis obrigatórias
MISSING=()
  [[ -z "${GITHUB_PERSONAL_ACCESS_TOKEN:-}" ]] && MISSING+=("GITHUB_PERSONAL_ACCESS_TOKEN")

if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo "❌ Variáveis obrigatórias ausentes em $SECRETS_ENV:"
  printf '   %s\n' "${MISSING[@]}"
  exit 1
fi

# Verifica dependências de runtime
for cmd in npx node; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "❌ Dependência ausente: $cmd"
    echo "   Instale o Node.js: https://nodejs.org/"
    exit 1
  fi
done

echo "✅ Ambiente MCP carregado com sucesso."
echo ""
echo "   Abra o VS Code com:"
echo "   code ."
