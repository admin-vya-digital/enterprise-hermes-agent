# Configuração de Branch Protection - GitHub

Este guia explica como configurar proteções de branch no GitHub para garantir qualidade e segurança do código.

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Configuração Passo a Passo](#configuração-passo-a-passo)
- [Níveis de Proteção](#níveis-de-proteção)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Visão Geral

Branch protection previne:
- ❌ Push direto no `main`
- ❌ Force push destrutivo
- ❌ Merge sem review
- ❌ Merge com CI failing
- ❌ Perda acidental de código

---

## ⚙️ Configuração Passo a Passo

### 1. Acessar Settings

1. No GitHub, vá para o repositório
2. Clique em **Settings** (ícone de engrenagem)
3. No menu lateral, clique em **Branches** (em "Code and automation")

### 2. Adicionar Branch Protection Rule

1. Clique em **Add rule** ou **Add branch protection rule**
2. Em "Branch name pattern", digite: `main`
3. Configure as proteções conforme seções abaixo

### 3. Configurações Recomendadas

#### ✅ Protect matching branches

Marque **TODAS** estas opções:

##### Require a pull request before merging

- [x] **Require a pull request before merging**
  - [x] Require approvals: **1** (mínimo)
    - Para times maiores: 2+ approvals
    - Para mudanças críticas: configure CODEOWNERS
  - [x] Dismiss stale pull request approvals when new commits are pushed
  - [x] Require review from Code Owners
  - [ ] Restrict who can dismiss pull request reviews *(opcional)*
  - [ ] Allow specified actors to bypass required pull requests *(apenas em casos especiais)*
  - [ ] Require approval of the most recent reviewable push

##### Require status checks to pass before merging

- [x] **Require status checks to pass before merging**
  - [x] Require branches to be up to date before merging
  - Selecione os checks obrigatórios:
    - [x] CI / Build
    - [x] CI / Test
    - [x] CI / Lint
    - [x] CI / Security Scan *(se configurado)*
    - [x] codecov/patch *(se usando Codecov)*
    - [x] codecov/project *(se usando Codecov)*

##### Require conversation resolution before merging

- [x] **Require conversation resolution before merging**
  - Força resolver todos os comentários do review antes do merge

##### Require signed commits

- [x] **Require signed commits** *(recomendado para alta segurança)*
  - Exige GPG signatures em todos os commits
  - ⚠️ Requer configuração prévia dos desenvolvedores

##### Require linear history

- [x] **Require linear history** *(opcional)*
  - Previne merge commits
  - Força rebase ou squash
  - ⚠️ Pode ser restritivo para alguns workflows

##### Require deployments to succeed before merging

- [ ] **Require deployments to succeed** *(opcional)*
  - Para ambientes com preview/staging automático

##### Lock branch

- [ ] **Lock branch**
  - Apenas para branches de arquivo/histórico
  - NÃO use no `main` ativo

##### Do not allow bypassing the above settings

- [x] **Do not allow bypassing the above settings** *(altamente recomendado)*
  - Aplica regras para TODOS, incluindo admins
  - ⚠️ Desmarque apenas se admins precisam de override em emergências

##### Allow force pushes

- [ ] **Allow force pushes** ❌ **NUNCA marque para `main`**
  - Permitir force push no `main` pode causar perda de dados

##### Allow deletions

- [ ] **Allow deletions** ❌ **NUNCA marque para `main`**
  - Previne deleção acidental da branch principal

---

## 📊 Níveis de Proteção

### 🟢 Nível 1: Mínimo (Projetos Pequenos)

```yaml
# Configuração mínima
✅ Require pull request
✅ Require 1 approval
✅ Require status checks
✅ Require up-to-date branch
❌ Block force push
❌ Block branch deletion
```

**Para**:
- Projetos pessoais
- Equipes de 1-3 pessoas
- Prototipagem rápida

### 🟡 Nível 2: Recomendado (Projetos Profissionais)

```yaml
# Configuração recomendada
✅ Require pull request
✅ Require 1-2 approvals
✅ Dismiss stale approvals
✅ Require Code Owners review
✅ Require status checks (CI/CD)
✅ Require up-to-date branch
✅ Require conversation resolution
❌ Block force push
❌ Block branch deletion
✅ Do not allow bypassing
```

**Para**:
- Projetos em produção
- Equipes de 3-10 pessoas
- Desenvolvimento ativo

### 🔴 Nível 3: Máximo (Sistemas Críticos)

```yaml
# Configuração máxima
✅ Require pull request
✅ Require 2+ approvals
✅ Dismiss stale approvals
✅ Require Code Owners review
✅ Require status checks (CI/CD + Security)
✅ Require up-to-date branch
✅ Require conversation resolution
✅ Require signed commits
✅ Require linear history (opcional)
✅ Require deployments to succeed
❌ Block force push
❌ Block branch deletion
✅ Do not allow bypassing
```

**Para**:
- Sistemas financeiros
- Infraestrutura crítica
- Compliance (SOC2, PCI-DSS)
- Dados sensíveis

---

## 🔧 Status Checks Recomendados

Configure no CI/CD para passar antes do merge:

### Build e Testes

```yaml
# .github/workflows/ci.yml
name: CI
on: [pull_request]
jobs:
  build:
    name: Build
  test:
    name: Test
  lint:
    name: Lint
  typecheck:
    name: Type Check
```

### Segurança

```yaml
# .github/workflows/security.yml
name: Security
on: [pull_request]
jobs:
  dependency-check:
    name: Dependency Scan
  secret-scan:
    name: Secret Scan
  sast:
    name: Static Analysis
```

### Code Quality

```yaml
# .github/workflows/quality.yml
name: Quality
on: [pull_request]
jobs:
  coverage:
    name: Code Coverage
  complexity:
    name: Complexity Check
```

---

## 🚀 Configuração via GitHub API

Para automatizar configuração:

```bash
# Script para configurar branch protection
gh api repos/{owner}/{repo}/branches/main/protection \
  -X PUT \
  -F required_pull_request_reviews[required_approving_review_count]=1 \
  -F required_pull_request_reviews[dismiss_stale_reviews]=true \
  -F required_status_checks[strict]=true \
  -F required_status_checks[contexts][]=CI \
  -F required_status_checks[contexts][]=Test \
  -F enforce_admins=true \
  -F restrictions=null
```

Ou usar Terraform:

```hcl
resource "github_branch_protection" "main" {
  repository_id = github_repository.repo.node_id
  pattern       = "main"

  required_pull_request_reviews {
    required_approving_review_count = 1
    dismiss_stale_reviews           = true
    require_code_owner_reviews      = true
  }

  required_status_checks {
    strict   = true
    contexts = ["CI", "Test", "Lint"]
  }

  enforce_admins = true
}
```

---

## 🛠️ Troubleshooting

### Problema: "Cannot merge - branch is out of date"

**Causa**: "Require branches to be up to date" está ativo

**Solução**:
```bash
git fetch origin
git rebase origin/main
git push --force-with-lease
```

### Problema: "Admin override needed"

**Causa**: "Do not allow bypassing" está ativo

**Soluções**:
1. Seguir processo normal (recomendado)
2. Temporariamente desabilitar regra (emergência apenas)
3. Configurar bypass para role específico

### Problema: "Status check never completes"

**Causa**: CI/CD workflow não configurado ou com erro

**Solução**:
1. Verificar `.github/workflows/`
2. Checar logs do GitHub Actions
3. Remover check obrigatório se workflow foi deletado

### Problema: "Force push needed but blocked"

**Causa**: Branch protection bloqueia force push

**Solução**:
```bash
# Não force push no main!
# Alternativa: criar nova branch
git checkout -b fix/revert-changes
git cherry-pick <commit>
# Abrir novo PR
```

---

## 📋 Checklist de Configuração

Após configurar, verificar:

- [ ] Branch `main` está listada nas proteções
- [ ] Pull request obrigatório configurado
- [ ] Número mínimo de approvals definido
- [ ] Status checks selecionados e funcionando
- [ ] CODEOWNERS arquivo presente (se usando)
- [ ] Force push bloqueado
- [ ] Deleção de branch bloqueada
- [ ] Admins não podem bypass (ou bypass documentado)
- [ ] Time treinado sobre novo processo
- [ ] Documentação atualizada (CONTRIBUTING.md)

---

## 🔄 Manutenção

### Revisão Trimestral

A cada 3 meses, verificar:

- [ ] Status checks ainda são relevantes?
- [ ] Número de reviewers adequado?
- [ ] CODEOWNERS atualizado?
- [ ] Processo está funcionando bem?
- [ ] Desenvolvedores conseguem trabalhar?
- [ ] Emergências foram tratadas adequadamente?

### Métricas para Monitorar

- Tempo médio de merge de PR
- Taxa de rejeiçãode PRs
- Número de bugs em produção
- Satisfação do time com processo

---

## 📚 Referências

- [GitHub Branch Protection](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [Status Checks](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/about-status-checks)
- [CODEOWNERS](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)
- [GitHub Flow](https://docs.github.com/en/get-started/quickstart/github-flow)

---

**Última atualização**: 2026-07-06
**Responsável**: Tech Lead / DevOps Team
