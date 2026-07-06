# Contribuindo para enterprise-hermes-agent

Obrigado por considerar contribuir para este projeto! Este documento define as diretrizes e melhores práticas para contribuições.

## 📋 Índice

- [Código de Conduta](#código-de-conduta)
- [Como Contribuir](#como-contribuir)
- [Workflow Git](#workflow-git)
- [Padrões de Código](#padrões-de-código)
- [Processo de Review](#processo-de-review)
- [Proteção de Branches](#proteção-de-branches)

---

## 🤝 Código de Conduta

Este projeto adere a um código de conduta profissional. Ao participar, você concorda em manter um ambiente respeitoso e colaborativo.

---

## 🚀 Como Contribuir

### Reportar Bugs

Use o template de issue para bugs:
- Descrição clara do problema
- Passos para reproduzir
- Comportamento esperado vs atual
- Ambiente (OS, versão, etc.)

### Propor Features

Use o template de issue para features:
- Contexto e motivação
- Descrição da solução proposta
- Alternativas consideradas

### Submeter Pull Requests

Siga o [Workflow Git](#workflow-git) abaixo.

---

## 🌿 Workflow Git

### Política de Branches

**Branch Principal (`main`)**:
- ✅ Sempre estável e pronta para deploy
- ✅ Protegida contra push direto
- ✅ Protegida contra force push
- ✅ Requer PR aprovado + CI passing
- ❌ **NUNCA** fazer push direto
- ❌ **NUNCA** fazer force push
- ❌ **NUNCA** fazer rebase do histórico público

### Estratégia de Branching

Seguimos **GitHub Flow** com branches curtas e integrações frequentes:

```
main (protegida)
  │
  ├─ feature/NNN-descricao-curta    ← trabalho de feature
  ├─ fix/descricao-bug               ← correção de bug
  ├─ chore/descricao-tarefa          ← manutenção/refactor
  └─ hotfix/descricao-critica        ← correção urgente
```

### Convenção de Nomes de Branch

| Tipo | Padrão | Exemplo |
|------|--------|---------|
| Feature | `feature/NNN-descricao` | `feature/042-user-authentication` |
| Bug fix | `fix/descricao` | `fix/memory-leak-in-parser` |
| Hotfix | `hotfix/descricao` | `hotfix/security-patch` |
| Chore | `chore/descricao` | `chore/update-dependencies` |

**Regras**:
- Descritivo e conciso (max 50 caracteres)
- Lowercase com hífens
- Sem caracteres especiais
- Issue number quando aplicável

### Ciclo de Vida de uma Branch

```bash
# 1. Criar branch a partir do main atualizado
git checkout main
git pull origin main
git checkout -b feature/123-nova-feature

# 2. Trabalhar em commits pequenos e focados
git commit -m "feat(scope): descrição clara"

# 3. Manter branch atualizada com main
git fetch origin
git rebase origin/main  # OU git merge origin/main

# 4. Push para remoto
git push origin feature/123-nova-feature

# 5. Abrir Pull Request (ver seção abaixo)

# 6. Após merge, deletar branch
git branch -d feature/123-nova-feature
git push origin --delete feature/123-nova-feature
```

### Branches de Vida Curta

**❌ Evitar**:
- Branches com mais de 5 dias sem merge
- Branches com centenas de commits
- Branches "de integração" informais
- Múltiplas pessoas comitando na mesma branch

**✅ Preferir**:
- Branches pequenas (1-3 dias)
- Escopo único e bem definido
- Sincronização frequente com `main`
- Merge rápido após aprovação

---

## 📝 Pull Requests

### Template de PR

Use o template automático que inclui:
- [ ] Descrição clara da mudança
- [ ] Link para issue relacionada
- [ ] Tipo de mudança (feature/fix/chore/breaking)
- [ ] Checklist de validação
- [ ] Screenshots (se UI)
- [ ] Plano de rollback (se crítico)

### Regras de PR

**Obrigatórios ANTES do merge**:
- ✅ CI/CD passou (todos os checks verdes)
- ✅ Pelo menos 1 aprovação de reviewer
- ✅ Branch atualizada com `main`
- ✅ Sem conflitos pendentes
- ✅ Testes adicionados/atualizados
- ✅ Documentação atualizada (se necessário)

### Estratégias de Merge

**Squash Merge** (padrão):
- Consolida commits em um único no `main`
- Histórico limpo e linear
- Use para: features normais, fixes

**Merge Commit**:
- Preserva histórico da branch
- Use para: grandes features, integrações complexas

**Rebase and Merge**:
- ⚠️ Usar com cuidado
- Requer disciplina alta
- Use para: branches pessoais simples

### Tamanho do PR

| Tamanho | Linhas | Recomendação |
|---------|--------|--------------|
| XS | < 50 | ✅ Ideal |
| S | 50-200 | ✅ Bom |
| M | 200-500 | ⚠️ Aceitável |
| L | 500-1000 | ❌ Quebrar em PRs menores |
| XL | > 1000 | ❌ Refatorar abordagem |

---

## 🔒 Proteção de Branches

### Configuração do `main`

**Proteções ativas**:
- ✅ Bloquear push direto
- ✅ Bloquear force push
- ✅ Bloquear deleção da branch
- ✅ Exigir PR antes de merge
- ✅ Exigir status checks (CI/CD)
- ✅ Exigir branch atualizada
- ✅ Exigir review aprovado (1+ reviewer)
- ✅ Exigir assinatura de commits (se configurado)

### Antes de Mudanças Críticas

Para mudanças que afetam infraestrutura, dados ou sistema crítico:

1. **Tag de pre-release**:
   ```bash
   git tag -a v1.2.3-rc.1 -m "Release candidate"
   git push origin v1.2.3-rc.1
   ```

2. **Backup de dados** (se aplicável):
   - Snapshot do banco
   - Backup de configurações
   - Export de dados críticos

3. **Plano de rollback documentado**:
   - Passos para reverter
   - Responsáveis
   - Contatos de emergência

4. **Comunicação ao time**:
   - Janela de mudança
   - Impacto esperado
   - Procedimento de teste

---

## 🎨 Padrões de Código

### Commits Convencionais

Seguimos [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body (opcional)>

<footer (opcional)>
```

**Tipos permitidos**:
- `feat`: Nova feature
- `fix`: Correção de bug
- `docs`: Documentação
- `style`: Formatação (não afeta lógica)
- `refactor`: Refatoração de código
- `perf`: Melhoria de performance
- `test`: Adicionar/corrigir testes
- `chore`: Manutenção (deps, config, etc.)
- `ci`: Mudanças em CI/CD
- `build`: Mudanças no sistema de build

**Breaking changes**:
```bash
feat(api)!: alterar formato de resposta JSON

BREAKING CHANGE: campo 'user_id' renomeado para 'userId'
```

### Code Style

- Seguir linter configurado (ESLint, Pylint, etc.)
- Formatação automática (Prettier, Black, etc.)
- Tipos estáticos quando aplicável
- Testes para novas features
- Documentação inline quando necessário

---

## 👥 Processo de Review

### Como Revisor

**Avaliar**:
- ✅ Lógica está correta?
- ✅ Código está legível e manutenível?
- ✅ Testes cobrem casos importantes?
- ✅ Documentação está atualizada?
- ✅ Performance é aceitável?
- ✅ Segurança não foi comprometida?
- ✅ Não quebra funcionalidades existentes?

**Ao aprovar**:
- Usar "Approve" apenas se REALMENTE aprovado
- Deixar comentários construtivos
- Sugerir melhorias, não exigir perfeição

**Ao solicitar mudanças**:
- Ser específico e construtivo
- Explicar o "porquê"
- Sugerir alternativas

### Como Autor do PR

**Boas práticas**:
- Responder a todos os comentários
- Fazer mudanças solicitadas ou justificar
- Re-request review após mudanças
- Agradecer feedback construtivo
- Não fazer force push após review iniciado

---

## 🔄 Recuperabilidade

### Tags e Releases

Criar tags para marcos importantes:

```bash
# Release estável
git tag -a v1.0.0 -m "Release 1.0.0"
git push origin v1.0.0

# Pre-release
git tag -a v1.1.0-beta.1 -m "Beta 1.1.0"
git push origin v1.1.0-beta.1
```

### Rollback

Em caso de problema após merge:

**Opção 1 - Revert commit**:
```bash
git revert <commit-hash>
git push origin main
```

**Opção 2 - Hotfix reverso**:
```bash
git checkout -b hotfix/revert-feature-x
# Fazer mudanças para desfazer feature
git commit -m "fix: revert feature X devido a bug Y"
# Abrir PR emergencial
```

---

## 🚫 O Que NÃO Fazer

### Proibido

- ❌ Push direto no `main`
- ❌ Force push no `main`
- ❌ Rebase de branches públicas/compartilhadas
- ❌ Merge sem aprovação
- ❌ Merge com CI failing
- ❌ Branches de meses sem integração
- ❌ Commits com credenciais/secrets
- ❌ Mega-PRs com milhares de linhas

### Desencorajado

- ⚠️ Commits muito grandes
- ⚠️ Mensagens vagas ("fix", "update", "changes")
- ⚠️ Misturar múltiplos tipos de mudança em um PR
- ⚠️ Não testar localmente antes de push
- ⚠️ Ignorar feedback de review

---

## 📚 Recursos Adicionais

- [Conventional Commits](https://www.conventionalcommits.org/)
- [GitHub Flow](https://docs.github.com/en/get-started/quickstart/github-flow)
- [Trunk-Based Development](https://trunkbaseddevelopment.com/)
- [Code Review Best Practices](https://google.github.io/eng-practices/review/)

---

## 🆘 Dúvidas?

- Abra uma issue com label `question`
- Entre em contato com mantenedores
- Consulte a documentação em `docs/`

---

**Última atualização**: 2026-07-06
