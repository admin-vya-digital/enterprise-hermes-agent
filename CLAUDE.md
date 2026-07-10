# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Visão Geral do Projeto

**Projeto**: `enterprise-hermes-agent`
**Descrição**: Enterprise projeto to use Hermes agent automation
**Domínio**: programming | **Linguagem**: python
**Criado em**: 2026-07-06T12:07:01Z

## Comandos Frequentes

```bash
# Instalar dependências
make install-deps

# Rodar testes
make test

# Lint e formatação
make lint && make format

# Encerrar sessão (valida integridade do projeto)
make session-end

# Limpar arquivos gerados
make clean
```

## Ambiente

- Python 3.12+ gerenciado por `uv`
- Ambiente virtual em `.venv/`
- Dependências em `pyproject.toml`

## Estrutura do Projeto

```
enterprise-hermes-agent/
├── .claude/            # Claude Code: commands e skills
├── .github/            # CI/CD, agentes SpecKit
├── .secrets/           # Credenciais locais (não versionado, chmod 700)
├── .vscode/            # VS Code: settings, MCP, extensions
├── docs/               # Documentação (INDEX, TODO, SESSIONS)
├── scripts/            # Scripts de automação
└── src/                # Código-fonte
```

## Sessões de Trabalho

Documentar atividades em `docs/SESSIONS/YYYY-MM-DD/`:
- `SESSION_RECOVERY_YYYY-MM-DD.md` — contexto inicial
- `DAILY_ACTIVITIES_YYYY-MM-DD.md` — log incremental
- `FINAL_STATUS_YYYY-MM-DD.md` — estado ao encerrar

## Regras de Desenvolvimento

- Nunca commitar arquivos em `.secrets/`
- Seguir Conventional Commits: `feat`, `fix`, `docs`, `chore`, etc.
- Rodar `make lint` antes de cada commit
- Credenciais HTTP sempre via Python + requests (nunca curl com tokens)
- Usar pasta tmp do projeto.
- Não usar temp do Sistema Operacional

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
<!-- SPECKIT END -->
