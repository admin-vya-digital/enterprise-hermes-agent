---
mode: agent
description: Ritual de encerramento de sessão. Execute ao finalizar o trabalho do dia.
---

# 🏁 Session End — Ritual de Encerramento de Sessão

> Execute este ritual **ao final de cada sessão** antes de sair do editor.
> Garante rastreabilidade, preserva contexto e mantém o repositório sincronizado.

---

## ▶️ Execução do Ritual

---

### Passo 1 — Consolidar Atividades do Dia

Atualizar `docs/SESSIONS/[YYYY-MM-DD]/DAILY_ACTIVITIES_[YYYY-MM-DD].md` com:

- Todas as tarefas executadas nesta sessão (concluídas e abandonadas)
- Decisões tomadas (com justificativa)
- Problemas encontrados e como foram resolvidos
- Artefatos criados ou modificados (com caminho)

**Formato recomendado para cada atividade:**
```markdown
### ✅ [IMP-XX] — [Título]

**Artefatos criados/modificados**:
| Arquivo | O que mudou |
|---------|-------------|
| `caminho/arquivo.py` | [descrição] |

**Destaques**: [pontos importantes para a próxima sessão]
```

---

### Passo 2 — Atualizar TODO.md

Em `docs/TODO.md`:

1. **Marcar concluídos**: `[ ]` → `[x]` para tudo finalizado nesta sessão
2. **Adicionar pendentes novos**: itens descobertos durante o trabalho
3. **Atualizar prioridades**: reordenar se necessário
4. **Atualizar o cabeçalho**:

```markdown
**Last Updated**: [YYYY-MM-DD] — [IMP-XX] ✅ Concluído
```

---

### Passo 3 — Criar FINAL_STATUS (se encerramento de sprint/milestone)

Se esta sessão encerrar uma fase importante, criar:
`docs/SESSIONS/[YYYY-MM-DD]/FINAL_STATUS_[YYYY-MM-DD].md`

```markdown
# 📊 Final Status — [YYYY-MM-DD]

**Branch**: [nome]
**Sessão**: [início] → [fim]

## IMPs Concluídos Esta Sessão
- ✅ IMP-XX: [descrição]

## Estado Geral dos IMPs
| IMP | Título | Status |
|-----|--------|--------|
| IMP-01 | ... | ✅ Concluído |
| IMP-02 | ... | 🔄 Em progresso |
| IMP-03 | ... | 🔵 Pendente |

## Próximas Ações (P0 para próxima sessão)
1. [ação]

## Decisões Técnicas desta Sessão
- D-XX: [decisão]

## Contexto para Recuperação
[o que a próxima sessão precisa saber para continuar sem fricção]
```

---

### Passo 4 — Verificar Qualidade do Código (se modo PROGRAMMING)

Antes de commitar código:

```bash
# Python
uv run pytest                          # testes passando?
uv run black --check src/             # formatação OK?
uv run flake8 src/                    # lint OK?
uv run mypy src/                      # types OK?

# TypeScript
npm test && npx tsc --noEmit && npm run lint

# Go
go test ./... && go vet ./... && golangci-lint run
```

Se houver falhas: corrigir antes de commitar ou documentar como `TODO` rastreado.

---

### Passo 5 — Verificar Infraestrutura (se modo INFRASTRUCTURE)

Antes de commitar IaC:

```bash
terraform fmt -recursive && terraform validate   # se Terraform
helm lint charts/*/                              # se Helm
ansible-lint playbooks/                          # se Ansible
hadolint Dockerfile                              # se Docker
```

### Passo 6 — Session Security Review & Scan Final

<br />

#### 6.1 — Session Documentation Security Review

**CRÍTICO**: Revisar documentos de sessão antes de commitar para garantir que nenhum dado sensível foi exposto:

**Arquivos a revisar**:
- `docs/SESSIONS/[YYYY-MM-DD]/DAILY_ACTIVITIES_[YYYY-MM-DD].md`
- `docs/SESSIONS/[YYYY-MM-DD]/SESSION_RECOVERY_[YYYY-MM-DD].md`
- `docs/SESSIONS/[YYYY-MM-DD]/SESSION_REPORT_[YYYY-MM-DD].md` (se existir)
- `docs/SESSIONS/[YYYY-MM-DD]/FINAL_STATUS_[YYYY-MM-DD].md` (se existir)

**Checklist de segurança para session docs**:

- [ ] ❌ **Credenciais**: Sem senhas, API keys, tokens, certificados
- [ ] ❌ **IPs/URLs**: Sem IPs privados, URLs de produção, endpoints internos
- [ ] ❌ **Dados pessoais**: Sem emails reais, nomes de clientes, CPF/CNPJ
- [ ] ❌ **Estrutura interna**: Sem arquitetura detalhada de infraestrutura crítica
- [ ] ❌ **Vulnerabilidades**: Sem descrição de falhas de segurança não corrigidas
- [ ] ❌ **Paths sensíveis**: Sem caminhos completos de sistemas de produção
- [ ] ✅ **Exemplos sanitizados**: Usar `user@example.com`, `192.0.2.1`, `api.exemplo.local`
- [ ] ✅ **Placeholders**: Usar `<TOKEN>`, `<API_KEY>`, `***` em exemplos
- [ ] ✅ **Paths relativos**: Usar caminhos relativos ao projeto, não absolutos do sistema

**Padrões comuns de exposição acidental**:

| Risco | Exemplo INCORRETO | Exemplo CORRETO |
|-------|------------------|-----------------|
| API Keys | `API_KEY=sk_live_abc123...` | `API_KEY=<REDACTED>` |
| URLs internas | `https://internal-db.company.local` | `https://<INTERNAL_DB>` |
| IPs privados | `ssh admin@10.x.x.x` | `ssh admin@<PRIVATE_IP>` |
| Emails reais | `contato@empresa-real.com` | `user@example.com` |
| Tokens JWT | `Bearer eyJhbGciOi...` | `Bearer <JWT_TOKEN>` |
| Senhas | `DB_PASS=MyS3cr3tP@ss` | `DB_PASS=<REDACTED>` |
| Paths absolutos | `/home/user/.secrets/api.key` | `.secrets/api.key` (relativo) |

**Comandos de auto-verificação**:

```bash
# Buscar padrões suspeitos em session docs (última semana)
find docs/SESSIONS/ -name "*.md" -mtime -7 -exec grep -HEi \
  'password|secret|token|api_key|bearer|private.*key' {} \;

# Verificar se houve exposição de IPs privados
find docs/SESSIONS/ -name "*.md" -mtime -7 -exec grep -HE \
  '(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)' {} \;
```

**Se encontrar exposição**:
1. PARAR imediatamente (não commitar)
2. Sanitizar os arquivos (remover/substituir por placeholders)
3. Verificar se já foi commitado antes → se sim, seguir procedimento de credential rotation
4. Adicionar padrão ao `.gitleaks-session-docs.toml` (após implementar IMP-49 subtarefa 3)

**Resultado esperado**:
```
🟢 Session docs security review: PASSED
   ✅ No credentials found
   ✅ No internal IPs/URLs exposed
   ✅ No personal data leaked
   ✅ All examples sanitized
```

---

<br />

#### 6.2 — Source Code & Staging Area Security Scan

Último check antes do commit (scan de arquivos a serem commitados):

```
Padrões: *.env, .env*, *.key, *.pem, *secret*, *password*, *token*, *.log
Excluir: .git/, .secrets/
```

**Se encontrar algo**: remover do staging, adicionar ao `.gitignore`, corrigir antes de prosseguir.

Verificar também:
- Nenhum `print()` / `console.log()` de debug deixado
- Nenhuma URL de ambiente de produção hardcodada
- Nenhum token/key em variáveis que serão commitadas

---

### Passo 7 — Preparar Commit

**Regra P0**: usar arquivo de mensagem com ≥6 linhas. Nunca `git commit -m "..."`.

```bash
# Verificar o que vai ser commitado
git status
git diff --staged          # revisar mudanças staged

# Preparar mensagem de commit
cat > /tmp/git-msg.txt << 'EOF'
[tipo]: [descrição curta em inglês ou português]

[IMP-XX] [Título da implementação]

Artefatos criados/modificados:
- caminho/arquivo1.py: [o que mudou]
- caminho/arquivo2.md: [o que mudou]

Decisões: [se houver]
Pendente: [o que ficou para próxima sessão]
EOF

# Revisar a mensagem antes de commitar
cat /tmp/git-msg.txt
```

**Tipos de commit** (Conventional Commits):
| Tipo | Quando usar |
|------|-------------|
| `feat:` | Nova funcionalidade |
| `fix:` | Correção de bug |
| `docs:` | Apenas documentação |
| `refactor:` | Refatoração sem mudança de comportamento |
| `chore:` | Tarefas de manutenção (deps, config) |
| `test:` | Adição ou correção de testes |

---

### Passo 8 — Commitar e Fazer Push

```bash
# Adicionar e commitar
git add -A
git commit -F /tmp/git-msg.txt

# Verificar o commit
git log --oneline -3

# Push (D-17: git push é parte obrigatória do encerramento)
git push origin [branch]

# Confirmar push bem-sucedido
git status   # deve mostrar "Your branch is up to date with 'origin/[branch]'"
```

**Se o push falhar:**
```bash
git pull --rebase origin [branch]   # resolver conflitos se houver
git push origin [branch]
```

---

### Passo 9 — Atualizar INDEX.md (se novos arquivos foram criados)

Se novos arquivos importantes foram criados nesta sessão, atualizar `docs/INDEX.md`:

```markdown
## [Seção relevante]
- [`caminho/arquivo.ext`](../caminho/arquivo.ext) — [descrição de 1 linha]
```

---

### Passo 10 — Limpar Diretório Temporário

Remover arquivos temporários gerados durante a sessão:

```bash
# Verificar o que será removido (dry run)
./scripts/cleanup-tmp.sh --dry-run

# Limpar tmp/ (preserva tmp/README.md)
./scripts/cleanup-tmp.sh --verbose
```

**O script remove**:
- Todos os arquivos em `tmp/` exceto `README.md`
- Todos os subdiretórios em `tmp/`

**Quando NÃO limpar**:
- Se há arquivos temporários que serão usados na próxima sessão imediata
- Nesse caso, documente em `FINAL_STATUS` quais arquivos e por quê

---

<!--
### Passo 10.5 — Salvar Aprendizados em Memória (OPCIONAL — IMP-59)

**ATENÇÃO**: Este passo é opcional e requer que o Mini-Engram Memory System (IMP-59) esteja instalado.

**Verificar disponibilidade**:
```bash
test -f scripts/mem_save.py && echo "✅ Mini-Engram disponível" || echo "⚠ Mini-Engram não instalado"
```

**Critérios para salvar em memória** (salvar SE pelo menos um dos critérios for verdadeiro):

1. ✅ **Decisão arquitetural importante** foi tomada nesta sessão
2. ✅ **Padrão de código/configuração** foi estabelecido e deve ser reutilizado
3. ✅ **Problema difícil foi resolvido** e a solução pode economizar tempo no futuro
4. ✅ **Processo de equipe** foi documentado ou melhorado
5. ✅ **Descoberta técnica relevante** que impacta o projeto

**NÃO salvar** (já está em session docs):
- ❌ Tarefas rotineiras (bug fixes triviais, typos)
- ❌ Configurações específicas de uma única sessão
- ❌ Detalhes já cobertos em DAILY_ACTIVITIES (session history já persiste isso)

**Como decidir entre session docs vs memory**:
| Tipo de informação | Session Docs | Mini-Engram |
|-------------------|--------------|-------------|
| "O que fiz hoje?" | ✅ DAILY_ACTIVITIES | ❌ |
| "Por que decidi usar Redis?" | 🟡 DAILY_ACTIVITIES | ✅ Project Memory |
| "Como configurar SSH SPA?" | ✅ SESSION_REPORT | ✅ Team Memory (se processo) |
| "Bug fix do SQLite FTS5" | ✅ DAILY_ACTIVITIES | 🟡 Só se padrão reutilizável |

**Se houver memórias para salvar**, executar:
```bash
make memory-save
# OU
python scripts/mem_save.py
```

**Exemplo interativo**:
```
💾 Saving new memory to Mini-Engram

Title: Redis para Rate Limiting de API
Content (markdown):
---
Decisão: usar Redis para rate limiting no API Gateway.

Rationale:
- Performance: <1ms de latência para contadores
- Atomicidade: INCR garante race-free counting
- TTL nativo: expiração automática de janelas

Implementação:
```python
limiter = redis.StrictRedis()
key = f"ratelimit:{user_id}:{window}"
limiter.incr(key)
limiter.expire(key, 3600)  # 1h window
```
---

Category (project/team/sessions): project
Tags (comma-separated): redis,api,rate-limiting,performance
```

**Resultado**: `✅ Memory saved: .memory/memories/project/2026-04-20__redis-rate-limiting.md`

**Resultado esperado**:
- Se salvou: `✅ [N] memória(s) salva(s) no Mini-Engram`
- Se não havia memórias relevantes: `⏭ Nenhuma memória nova para salvar (session docs já cobrem)`
- Se Mini-Engram não disponível: `⏭ Mini-Engram não instalado (pular)`

-->

---

## ✅ Checklist de Encerramento

### Documentação
- [ ] `DAILY_ACTIVITIES_[data].md` completo com todos os artefatos
- [ ] `docs/TODO.md` atualizado (concluídos marcados, novos adicionados)
- [ ] `FINAL_STATUS_[data].md` criado (se encerramento de fase)
- [ ] `docs/INDEX.md` atualizado (se novos arquivos criados)

### Limpeza
- [ ] `./scripts/cleanup-tmp.sh` executado (ou motivo documentado para não executar)

### Qualidade
- [ ] Testes passando (se código foi modificado)
- [ ] Lint/formatter aplicado (se código foi modificado)
- [ ] IaC validado (se infra foi modificada)
- [ ] **Session docs security review: 🟢 PASSED** (sem credenciais, IPs, dados sensíveis)
- [ ] Scan de segurança final (source code): 🟢 LIMPO

### Git
- [ ] `git status` revisado — nada inesperado no staging
- [ ] Arquivo de mensagem preparado em `/tmp/git-msg.txt`
- [ ] `git commit -F /tmp/git-msg.txt` executado com sucesso
- [ ] `git push` executado com sucesso
- [ ] `git status` pós-push: "up to date"

---

## 🔄 Contexto para Próxima Sessão

Ao encerrar, deixar registrado em `FINAL_STATUS` ou `DAILY_ACTIVITIES`:

1. **Onde parou**: arquivo + linha se possível
2. **Próximo passo imediato**: o que fazer ao abrir na próxima sessão
3. **Decisões pendentes**: o que precisa de confirmação do usuário
4. **Riscos/bloqueios**: o que pode impedir progresso
5. **Comandos úteis**: se há setup não óbvio para retomar

---

## ⚠️ Anti-Patterns de Encerramento

| ❌ Proibido | ✅ Correto |
|------------|-----------|
| `git commit -m "wip"` | Mensagem descritiva com arquivo ≥6 linhas |
| Fechar sem fazer push | Push é obrigatório (D-17) |
| TODO.md desatualizado | Sempre atualizar antes de fechar |
| Código com testes falhando commitado | Corrigir ou documentar como known issue |
| Secrets/tokens no commit | Scan obrigatório antes de `git add` |
| "Vou lembrar o contexto" | Sempre escrever em FINAL_STATUS |

---

*Session End Prompt v1.0 | IMP-04 | 2026-03-01*
