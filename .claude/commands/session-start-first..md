---
mode: agent
description: Ritual de primeira sessão em um projeto novo ou recém-clonado. Use apenas na primeira vez.
---

# 🌱 Session Start (First Time) — Ritual de Primeira Sessão

> Use este ritual apenas na **primeira sessão** em um projeto novo ou recém-clonado.
> Para sessões subsequentes, use `session-start.prompt.md`.

---

## ▶️ Execução do Ritual

---

### Passo 1 — Verificar Pré-requisitos

Confirmar ferramentas disponíveis:

```bash
uv --version          # deve existir (PEP 723 runner)
git --version
python3 --version     # ≥ 3.10
```

Se `uv` não estiver instalado:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

### Passo 2 — Verificar Configuração MCP

**Ação do agente**: ler `.vscode/mcp.json` e confirmar que os servidores `memory` e `sequential-thinking` estão configurados e **não comentados**.

```
✅ MCP Config OK — memory ✅ | sequential-thinking ✅
```

Se o `.vscode/mcp.json` ainda não existir (projeto zerado), será criado pelo `scaffold.py` no Passo 4.

> Para verificar se os servidores estão *em execução*: `Command Palette → "MCP: List Servers"` (ação manual do usuário). Se não aparecerem: `Command Palette → "MCP: Refresh Servers"`.

---

### Passo 3 — Verificar se é Projeto Novo ou Clone

**Caso A — Projeto absolutamente novo** (pasta vazia):
- Ir direto para o Passo 4 (scaffold.py)

**Caso B — Clone do template `a-default-project`**:
- Verificar se `scripts/scaffold.py` existe
- Se sim, ir para Passo 4
- Se não, o projeto pode estar desatualizado — reportar ao usuário

**Caso C — Projeto existente sem scaffold**:
- Verificar estrutura manualmente
- Criar `docs/SESSIONS/` se não existir
- Criar `docs/TODO.md` e `docs/INDEX.md` se não existirem
- Pular para Passo 6

---

### Passo 4 — Executar scaffold.py

O `scaffold.py` é o **único** responsável por inicializar projetos. Nunca usar `make init` para lógica de scaffolding (D-21).

```bash
# Interativo (recomendado na primeira sessão)
uv run scripts/scaffold.py

# Ou com flags (modo CI / automação)
uv run scripts/scaffold.py --new \
  --name "nome-do-projeto" \
  --domain "programming" \
  --language "python" \
  --repo "https://github.com/org/repo"
```

**O scaffold criará automaticamente:**
```
[projeto]/
├── .copilot-rules.md           ← link para shared/.copilot-rules.md
├── .copilot-rules-[nome].md    ← regras específicas do projeto (gerado)
├── .github/
│   └── prompts/                ← link para shared/.github/prompts/
├── .vscode/
│   ├── mcp.json                ← servidores MCP por domínio
│   ├── settings.json           ← settings por linguagem
│   └── extensions.json         ← extensões por domínio+linguagem
├── .secrets/                   ← git-ignored
├── docs/
│   ├── INDEX.md
│   └── TODO.md
├── src/
├── tests/
├── Makefile
└── README.md
```

**Validar após scaffold:**
```bash
# Verificar links simbólicos
uv run scripts/scaffold.py --check

# Verificar que .secrets/ está no .gitignore
grep -q ".secrets" .gitignore && echo "✅" || echo "❌ ADICIONAR .secrets ao .gitignore"
```

---

### Passo 5 — Inicializar Git

Se o scaffold não inicializou o git automaticamente:

```bash
git init
git remote add origin [URL]
```

**Primeiro commit** — usar arquivo de mensagem (regra P0):
```bash
cat > /tmp/git-msg.txt << 'EOF'
feat: initialize project with scaffold.py

- Created project structure via scaffold.py v1.0.0
- Domain: [programming|infrastructure|analysis]
- Language: [python|typescript|go|other]
- Generated .copilot-rules-[nome].md
- Configured .vscode/mcp.json, settings.json, extensions.json
- Symlinks to shared copilot files configured
EOF

git add -A
git commit -F /tmp/git-msg.txt
git push -u origin main
```

---

### Passo 6 — Carregar Regras Copilot

Ler e confirmar carregamento:
1. `.copilot-rules.md` (Camada 1 — sempre prevalece)
2. `.copilot-rules-[projeto].md` se existir (Camada 3 — específico do projeto)

**Regras P0 que devem estar ativas:**

| Regra | Status |
|-------|--------|
| Nunca heredoc/echo para criar arquivos | ✅ Ativo |
| Nunca cat/grep/find/ls via terminal | ✅ Ativo |
| Git com arquivo de mensagem ≥6 linhas | ✅ Ativo |
| Docs de sessão em `docs/SESSIONS/YYYY-MM-DD/` | ✅ Ativo |

---

### Passo 7 — Scan de Segurança Inicial

Verificar que nenhum arquivo sensível foi incluído no scaffold ou no clone:

```
Padrões: *.env, .env*, *.key, *.pem, *secret*, *password*, *token*, *.log
Excluir: .git/, .secrets/
```

**Resultado esperado**: `🟢 LIMPO`

Verificar também:
- `.gitignore` contém `.secrets/`, `*.env`, `*.key`, `.DS_Store`, `__pycache__/`

---

### Passo 8 — Criar Documentação Inicial de Sessão

Criar pasta e arquivos da primeira sessão:

```
docs/SESSIONS/[YYYY-MM-DD]/
├── SESSION_RECOVERY_[YYYY-MM-DD].md   ← "Primeira sessão — projeto inicializado"
└── DAILY_ACTIVITIES_[YYYY-MM-DD].md   ← log do que foi feito
```

Atualizar `docs/TODO.md` com os primeiros itens de trabalho identificados.

---

### Passo 9 — Declarar Domínio e Objetivo

```
Modo: [PROGRAMMING | INFRASTRUCTURE | ANALYSIS]
Projeto: [nome]
Linguagem/Cloud: [stack]
Objetivo desta primeira sessão: [1 frase]
```

Carregar Domain Profile correspondente:
- `PROGRAMMING` → `.github/prompts/domain/devops-programming.prompt.md`
- `INFRASTRUCTURE` → `.github/prompts/domain/devops-infrastructure.prompt.md`
- `ANALYSIS` → `.github/prompts/domain/devops-analysis.prompt.md`

---

## ✅ Checklist de Primeira Sessão

- [ ] Pré-requisitos: `uv`, `git`, `python3 ≥3.10` presentes
- [ ] MCP verificado (ou será criado pelo scaffold)
- [ ] `scaffold.py` executado com sucesso
- [ ] Estrutura de diretórios criada
- [ ] `.secrets/` no `.gitignore`
- [ ] Symlinks verificados: `uv run scripts/scaffold.py --check`
- [ ] Git inicializado + remote configurado
- [ ] Primeiro commit realizado com arquivo de mensagem
- [ ] `git push -u origin main` executado
- [ ] `.copilot-rules.md` e `.copilot-rules-[projeto].md` lidos
- [ ] Scan de segurança: 🟢 LIMPO
- [ ] `docs/SESSIONS/[data]/` criada com SESSION_RECOVERY + DAILY_ACTIVITIES
- [ ] `docs/TODO.md` com primeiros itens
- [ ] Domínio declarado + Domain Profile carregado

---

## ⚠️ Diferenças em relação à sessão recorrente

| Aspecto | Primeira Sessão | Sessões Seguintes |
|---------|----------------|-------------------|
| scaffold.py | Executar `--new` | Não necessário |
| Git init | Executar | Já existe |
| Recuperar contexto | Não há sessão anterior | Ler FINAL_STATUS anterior |
| `.copilot-rules-[projeto].md` | Gerado pelo scaffold | Já existe |
| MCP | Pode precisar criar `mcp.json` | Já existe |

---

*Session Start First Prompt v1.0 | IMP-03 | 2026-03-01*
