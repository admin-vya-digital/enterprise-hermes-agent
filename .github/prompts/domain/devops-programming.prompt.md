---
mode: agent
description: Domain Profile — DevOps Programação. Ative declarando "Modo: PROGRAMMING."
---

# 🖥️ Domain Profile — DevOps Programming

> **Como ativar**: no início da sessão declare:
> ```
> Modo: PROGRAMMING. Projeto: [nome]. Linguagem: [python|typescript|go|other].
> ```

---

## 🎯 Contexto do Domínio

Você está no modo **programação**. O trabalho envolve escrever, revisar, depurar ou refatorar código. O foco é na qualidade do software: funcionalidade, testabilidade, legibilidade e manutenção.

Diferente do modo infraestrutura (recursos e ambientes) ou análise (investigação e diagnóstico), aqui o artefato central é **código-fonte** com ciclo de feedback rápido via testes.

---

## 📋 O que o Copilot precisa saber neste modo

Antes de começar qualquer tarefa, colete (via `speckit.clarify` ou declaração direta):

| Informação | Exemplos | Obrigatório? |
|------------|----------|-------------|
| **Linguagem + versão** | Python 3.12, TypeScript 5.3, Go 1.22 | ✅ |
| **Framework principal** | FastAPI, Next.js, Django, Express, Gin | ✅ |
| **Estrutura de testes** | pytest, jest, go test | ✅ |
| **Linter / formatter** | ruff (lint + format), prettier + eslint, gofmt | ✅ |
| **Onde está o código** | `src/`, `app/`, monorepo? | ✅ |
| **Type checking** | mypy, tsc strict, staticcheck | Recomendado |
| **Convenções de import** | absolute, relative, isort profile | Recomendado |
| **Cobertura mínima** | 80%, 90%, sem mínimo | Opcional |
| **Branch de trabalho** | `feat/NNN-nome`, `fix/descricao` | Recomendado |

---

## 🔧 Comportamento Esperado do Copilot

### Ao gerar código
- Seguir estilo do projeto (detectar pelo código existente antes de gerar)
- Incluir type annotations sempre (Python: PEP 484; TS: strict mode)
- Gerar docstrings/JSDoc para funções públicas
- Preferir funções pequenas e testáveis
- Não gerar código que quebre testes existentes sem avisar

### Ao revisar código
- Verificar: lógica, edge cases, performance óbvia, segurança básica (injeção, auth)
- Sugerir refatorações com justificativa, não apenas apontar problemas
- Identificar code smells: funções longas, acoplamento alto, duplicação

### Ao depurar
- Perguntar: "qual é o comportamento esperado vs. o atual?"
- Pedir stack trace completo antes de sugerir solução
- Não supor o erro — verificar com o desenvolvedor

### Ao escrever testes
- Padrão AAA: Arrange → Act → Assert
- Nomear: `test_[funcao]_[cenario]_[resultado_esperado]`
- Mockar dependências externas (DB, APIs, filesystem)
- Incluir casos de borda (None, lista vazia, valores extremos)

---

## ✅ Definition of Done — Programação

Uma tarefa de programação está **concluída** quando:

### Obrigatório
- [ ] Testes passando: `pytest` / `npm test` / `go test ./...` sem falhas
- [ ] Lint sem erros: `ruff check` / `eslint` / `golangci-lint`
- [ ] Formatter aplicado: `ruff format` / `prettier` / `gofmt`
- [ ] Type checking sem erros: `mypy` / `tsc --noEmit` / `staticcheck`
- [ ] Nenhum `TODO` ou `FIXME` não rastreado introduzido
- [ ] Commit com mensagem Conventional Commits

### Recomendado
- [ ] Cobertura de testes mantida ou melhorada
- [ ] Docstrings/JSDoc para funções públicas novas
- [ ] PR description preenchida (contexto, screenshots se UI)
- [ ] Nenhum `console.log` / `print()` de debug deixado
- [ ] Variáveis de ambiente documentadas no `.env.example`

### Para mudanças de API/interface
- [ ] Contratos documentados (OpenAPI, GraphQL schema, README)
- [ ] Versão de breaking change marcada (semver)

---

## 🐍 Stack Python — Referência Rápida

```bash
# Desenvolvimento
uv run pytest                                        # testes
uv run pytest --cov=src --cov-report=term-missing    # coverage
uv run ruff format src/                              # format (substitui black)
uv run ruff check src/                               # lint + imports (substitui flake8 + isort)
uv run mypy src/                                     # type check

# Convenções
# - Máximo 88 chars por linha (black default)
# - isort profile: black
# - Docstrings: Google Style
# - Dataclasses para DTOs/configs
# - Exceptions customizadas com contexto
```

## 🟦 Stack TypeScript — Referência Rápida

```bash
# Desenvolvimento
npm test                             # testes (jest)
npm run lint                         # eslint
npm run format                       # prettier
npx tsc --noEmit                     # type check

# Convenções
# - strict: true no tsconfig
# - imports relativos dentro do módulo
# - `interface` para contratos de objeto; `type` para unions/aliases
```

## 🐹 Stack Go — Referência Rápida

```bash
go test ./...                        # testes
golangci-lint run                    # lint
gofmt -w .                          # format
go vet ./...                        # análise estática
```

---

## 🔀 Cruzamento com Outros Domínios (D-09)

Quando a tarefa cruza domínios, declare o primário e anote o secundário:

```
Modo: PROGRAMMING (primário).
Contexto secundário: o script usa boto3 para provisionar recursos AWS.
Regras de segurança de credenciais do modo INFRASTRUCTURE se aplicam:
- Nunca hardcodar keys; usar os.environ ou AWS profiles.
- Adicionar ao .env.example e .secrets/.gitignore.
```

---

## 📁 Estrutura de Arquivos Esperada

```
src/
├── core/
│   ├── models/         ← entidades de domínio
│   ├── interfaces/     ← contratos / ports
│   └── services/       ← lógica de negócio
├── data/
│   ├── repositories/   ← acesso a dados
│   └── factories/      ← criação de objetos
├── presentation/       ← views / handlers / controllers
└── infrastructure/     ← config, logging, segurança
tests/
├── unit/
├── integration/
└── e2e/
```

---

## ⚠️ Anti-Patterns — Nunca Fazer

| ❌ Proibido | ✅ Correto |
|------------|-----------|
| Lógica de negócio em controllers/views | Mover para services |
| Imports circulares | Refatorar para dependency injection |
| Variáveis de ambiente hardcodadas | `os.environ.get()` com `.env.example` |
| Testes que dependem de ordem de execução | Fixtures independentes |
| `except Exception: pass` | Capturar exceção específica e logar |
| Classes com 10+ métodos públicos | Extrair responsabilidades |
| Funções com 50+ linhas | Extrair sub-funções |

---

## 🗓️ Ritual de Sessão

### Início
```
Modo: PROGRAMMING. Projeto: [nome]. Linguagem: [stack].
Branch ativa: [feat/NNN-nome].
Objetivo desta sessão: [1 frase].
```

### Durante
- Commits frequentes (por sub-tarefa completa)
- Rodar testes antes de cada commit
- Atualizar `docs/TODAY_ACTIVITIES.md` com progresso

### Encerramento
- Rodar suite completa de testes
- Verificar lint + type check
- `git push` para branch
- Atualizar `docs/TODO.md` (marcar concluídos, adicionar pendentes)

---

---

## 🔍 Modo Review — Code Review Estruturado

> Ative com: `Modo: PROGRAMMING + REVIEW. PR/Branch: [identificação].`

### Processo
1. Entender o contexto do PR: qual problema resolve, qual é o design adotado
2. Leitura completa antes de comentar (não comentar linha por linha sem visão do todo)
3. Classificar cada comentário com nível de severidade:

| Nível | Descrição | Bloqueia merge? |
|-------|-----------|----------------|
| `[BLOCKER]` | Bug, falha de segurança, regressão, quebra de contrato | ✅ Sim |
| `[SUGGESTION]` | Melhoria de legibilidade, refatoração benéfica, alternativa de design | ❌ Não |
| `[NIT]` | Estilo menor, preferência pessoal, formatação automática | ❌ Não |
| `[QUESTION]` | Clarificação necessária antes de decidir sobre bloqueio | ⏳ Aguardar |

### Checklist de Code Review

- [ ] **Lógica**: o código faz o que a tarefa/issue descreve?
- [ ] **Edge cases**: entradas vazias, None, listas com 0/1/N elementos, overflow?
- [ ] **Testes**: cobertura dos cenários novos; nenhum teste removido sem justificativa
- [ ] **Segurança**: injeções, autorização por recurso, dados sensíveis em logs?
- [ ] **Performance**: O(N²) desnecessário, N+1 queries, bloqueio em thread principal?
- [ ] **Legibilidade**: nomes claros, funções < 50 linhas, sem hardcode mágico?
- [ ] **Compatibilidade**: breaking change sem versionamento?

### Formato de Comentário

```
[BLOCKER] src/auth/handler.py:42
A verificação de autorização acontece após a leitura do recurso.
Qualquer usuário autenticado pode ler dados de outro usuário.
Correção: mover `check_ownership(user_id, resource_id)` para antes da query.
```

---

## 🔗 Referências

- [.copilot-rules.md](../../../.copilot-rules.md) — Regras base da Camada 1 (sempre prevalecem)
- [docs/copilot/DOMAIN-PROFILES-STRATEGY.md](../../../docs/copilot/DOMAIN-PROFILES-STRATEGY.md)
- `.copilot-rules-[projeto].md` — Regras específicas do projeto ativo

---

*Domain Profile v1.1 | Atualizado em 2026-03-05 | IMP-05 + IMP-14 (A.7)*
