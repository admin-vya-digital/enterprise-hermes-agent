---
mode: agent
description: Ritual de início de sessão recorrente. Execute no começo de cada sessão de trabalho.
---

# 🚀 Session Start — Ritual de Início de Sessão

> Execute este ritual **no início de cada sessão** (não da primeira — para primeira sessão use `session-start-first.prompt.md`).

---

## ▶️ Execução do Ritual

Execute os passos abaixo em ordem. Confirme cada etapa antes de avançar.

---

### Passo 1 — Verificar Configuração MCP

**Ação do agente**: ler `.vscode/mcp.json` e confirmar que os servidores abaixo estão configurados e **não comentados**:

| Servidor | Propósito |
|----------|-----------|
| `memory` | Memória persistente entre sessões |
| `sequential-thinking` | Raciocínio estruturado |

Resultado esperado:
```
✅ MCP Config OK — memory ✅ | sequential-thinking ✅
```

Se algum servidor estiver ausente ou comentado no arquivo → reportar e instruir o usuário a descomentar e executar `Command Palette → "MCP: Refresh Servers"`.

> **Nota**: verificar se os servidores estão *em execução* no VS Code requer ação manual do usuário: `Command Palette → "MCP: List Servers"`. O agente verifica apenas a configuração em arquivo.

---

### Passo 2 — Recuperar Contexto da Sessão Anterior

Leia os seguintes arquivos na ordem indicada:

1. `docs/TODO.md` — estado atual de todas as tarefas
2. `docs/INDEX.md` — mapa de arquivos importantes
3. `docs/SESSIONS/[YYYY-MM-DD mais recente]/FINAL_STATUS_*.md` — estado final da última sessão
4. `docs/SESSIONS/[YYYY-MM-DD mais recente]/DAILY_ACTIVITIES_*.md` — atividades detalhadas
5. `.copilot-rules.md` — regras ativas (Camada 1, sempre prevalecem)

**Ao final deste passo, declare:**
```
✅ Contexto recuperado. Última sessão: [data].
Itens pendentes de alta prioridade: [lista dos P0/P1 do TODO.md].
Regras ativas carregadas: .copilot-rules.md [N] linhas, [N] seções.
```

---

### Passo 3 — Carregar Regras Copilot

Confirmar que `.copilot-rules.md` está ativo e suas regras P0 estão na memória:

| Regra | Verificado |
|-------|-----------|
| P0: Nunca heredoc/echo para criar arquivos | ✅ |
| P0: Nunca cat/grep/find/ls via terminal (usar ferramentas nativas) | ✅ |
| P0: 3+ arquivos → Python + JSON para mover | ✅ |
| P0: Git com arquivo de mensagem (≥6 linhas) | ✅ |
| P1: Docs de sessão em `docs/SESSIONS/YYYY-MM-DD/` | ✅ |

Se existir `.copilot-rules-[projeto].md` no projeto ativo, lê-lo também (Camada 3).

---

### Passo 4 — Scan de Segurança

Verificar ausência de credenciais ou arquivos sensíveis fora de `.secrets/`:

Padrões a verificar (excluindo `.git/` e `.secrets/`):
```
*.env, .env*, *.key, *.pem, *.crt, *.p12
*secret*, *password*, *token*, *credentials*, *.log
```

**Resultado esperado**: `🟢 LIMPO — nenhum arquivo sensível fora de .secrets/`

Se encontrar algo: **PARAR e reportar antes de continuar.**

Verificar também:
- `.secrets/` está no `.gitignore` ✅
- Nenhum valor real em `.env.example` (apenas placeholders)

---

### Passo 5 — Verificar Estado do Projeto

```bash
git status          # arquivos modificados não commitados
git log --oneline -5   # últimos 5 commits
```

**Interpretar:**
- Arquivos inesperadamente modificados → investigar antes de continuar
- Branch ativa diferente do esperado → confirmar com usuário
- Muitos commits não pushados → sugerir `git push` antes de iniciar

---

<!--
### Passo 5.5 — Verificar Memórias Relevantes (OPCIONAL — IMP-59)

**ATENÇÃO**: Este passo é opcional e requer que o Mini-Engram Memory System (IMP-59) esteja instalado.

**Verificar disponibilidade**:
```bash
test -f scripts/mem_context.py && echo "✅ Mini-Engram disponível" || echo "⚠ Mini-Engram não instalado"
```

**Se disponível**, executar análise de contexto:
```bash
make memory-context
# OU
python scripts/mem_context.py --auto
```

**Resultado esperado**:
```
💡 Suggested Context for Current Session

Based on: Branch: 060-mini-engram-python, Recent commits: ...

[1] Memory Title (95% relevance)
    Category: project | Updated: 2026-04-20
    Why: Title matches; Tags match; Branch context
    File: .memory/memories/project/2026-04-20__memory.md
```

**Ações**:
1. Revisar as memórias sugeridas (top 3-5)
2. Abrir arquivos relevantes em `.memory/memories/` se necessário
3. Incorporar insights ao planejamento da sessão

Se não houver memórias relevantes (score < 40%): continuar normalmente.

**Resultado**: `✅ Memórias verificadas: [N] relevantes encontradas` ou `⚠ Mini-Engram não disponível (pular)`

-->

---

### Passo 6 — Criar Documentos de Sessão e Carregar Protocolo

Criar os arquivos de sessão do dia (se ainda não existirem):

**Caminho**: `docs/SESSIONS/[YYYY-MM-DD]/`

Arquivos a criar:
1. `SESSION_RECOVERY_[YYYY-MM-DD].md` — resumo do contexto recuperado
2. `DAILY_ACTIVITIES_[YYYY-MM-DD].md` — log de atividades (será preenchido durante a sessão)

**Template SESSION_RECOVERY**:
```markdown
# 🔄 Session Recovery — [YYYY-MM-DD]

**Sessão anterior**: [data]
**Branch**: [branch ativa]
**Status dos IMPs**: [lista resumida]

## Contexto Recuperado
[resumo do que foi feito anteriormente]

## Itens P0 para Esta Sessão
[lista do TODO.md]
```

**Protocolo de Documentação Incremental**:

Durante a sessão, o agente deve **atualizar incrementalmente** `DAILY_ACTIVITIES_[YYYY-MM-DD].md` seguindo o formato estruturado definido em [`docs/SESSION_DOCS_STYLE_GUIDE.md`](../../docs/SESSION_DOCS_STYLE_GUIDE.md).

**Regras de documentação durante a sessão**:

1. **Quando documentar**: Após completar atividades significativas (>= 10 linhas de código, decisões técnicas, criação/modificação de documentação estrutural)

2. **Formato obrigatório**: Usar template canônico com separador `---` e campos estruturados:
   ```markdown
   ---

   ### [Título da Atividade] ([TODO-ID])

   **HH:MM — [STATUS]**

   **Objetivo**: [O que foi feito]
   **Contexto**: [Por que foi necessário]
   **Passos executados**:
   1. [Passo 1 com ferramenta usada]
   2. [Passo 2 com comando executado]

   **Resultado**: [Outcome — sucesso/bloqueio/aprendizado]
   **Arquivos modificados/criados**:
   - path/to/file.py (+N/-N)

   **Commits**:
   - `abc1234` — tipo(escopo): descrição

   **Status**: [✅ Completo | 🔵 Em progresso | ❌ Bloqueado | ⏸️ On hold]

   ---
   ```

3. **Atualização**: Usar `replace_string_in_file` em modo **append** (adicionar blocos ao final do arquivo)

4. **Não documentar**: Typos (< 5 linhas), chores, mudanças cosméticas

5. **Segurança**: NUNCA incluir credenciais, tokens, senhas, ou dados sensíveis nos blocos

**Carregar style guide**:
- Ler [`docs/SESSION_DOCS_STYLE_GUIDE.md`](../../docs/SESSION_DOCS_STYLE_GUIDE.md) após criar os arquivos de sessão
- Confirmar compreensão dos campos obrigatórios vs opcionais
- Confirmar compreensão dos anti-padrões (DO/DON'T)

**Resultado esperado**:
```
✅ Documentos de sessão criados
✅ SESSION_DOCS_STYLE_GUIDE.md carregado — protocolo ativo
```

---

### Passo 7 — Declarar Domínio e Objetivo

Peça ao usuário (ou aguarde declaração):

```
Qual o modo de trabalho desta sessão?

Modo: [PROGRAMMING | INFRASTRUCTURE | ANALYSIS]
Projeto: [nome do projeto]
Objetivo: [1 frase descrevendo o foco da sessão]
```

Com base na resposta, carregar o Domain Profile correspondente:
- `PROGRAMMING` → `.github/prompts/domain/devops-programming.prompt.md`
- `INFRASTRUCTURE` → `.github/prompts/domain/devops-infrastructure.prompt.md`
- `ANALYSIS` → `.github/prompts/domain/devops-analysis.prompt.md`

---

### Passo 8 — Atualizar Índice e TODO

Atualizar `docs/TODO.md`:
- Verificar se há itens "in-progress" da sessão anterior sem conclusão registrada
- Adicionar itens novos identificados durante a recuperação de contexto

---

## ✅ Checklist Final de Início de Sessão

Antes de começar o trabalho efetivo, confirmar:

- [ ] MCP configurado em `.vscode/mcp.json` (memory ✅ + sequential-thinking ✅)
- [ ] Contexto da sessão anterior recuperado e declarado
- [ ] `.copilot-rules.md` lido e regras P0 ativas
- [ ] Scan de segurança: 🟢 LIMPO
- [ ] `git status` verificado — sem surpresas
- [ ] `SESSION_RECOVERY_[data].md` criado
- [ ] `DAILY_ACTIVITIES_[data].md` criado
- [ ] Domínio declarado + Domain Profile carregado
- [ ] Objetivo da sessão declarado em 1 frase

---

## ⚠️ Anti-Patterns de Início de Sessão

| ❌ Proibido | ✅ Correto |
|------------|-----------|
| Começar a escrever código sem recuperar contexto | Sempre ler TODO.md primeiro |
| Supor qual era o estado do projeto | Ler FINAL_STATUS da última sessão |
| Pular o scan de segurança | Scan obrigatório a cada sessão |
| Trabalhar sem declarar o domínio | Declarar modo antes do primeiro commit |
| Criar arquivos sem verificar se já existem | Checar com file_search antes de criar |

---

*Session Start Prompt v1.0 | IMP-02 | 2026-03-01*
