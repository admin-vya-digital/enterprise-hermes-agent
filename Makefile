# Makefile — Enterprise Hermes Agent
# Gerado por scaffold.py em 2026-07-06T12:07:01Z

.PHONY: help init dev build test lint format clean

## Mostra esta ajuda
help:
	@grep -E '^## ' Makefile | sed 's/## //'

## [DEPRECATED] — use: uv run scripts/scaffold.py
init:
	@echo ""
	@echo " ⚠️  Para criar/configurar o projeto, use diretamente:"
	@echo "      uv run scripts/scaffold.py"
	@echo "      python scripts/scaffold.py"
	@echo ""

## Instala dependências
install-deps:
	@echo "Instalando dependências..."

## Inicia servidor de desenvolvimento
dev:
	@echo "Iniciando desenvolvimento..."

## Build de produção
build:
	@echo "Buildando..."

## Executa testes
test:
	@echo "Executando testes..."

## Lint do código
lint:
	@echo "Linting..."

## Formata código
format:
	@echo "Formatando..."

## Remove arquivos gerados
clean:
	@rm -rf dist/ build/ __pycache__/ .pytest_cache/ *.egg-info/ .coverage htmlcov/
## Carrega variáveis MCP do .secrets/.env e orienta a abrir o VS Code
mcp:
	@bash scripts/load-mcp.sh