# GitHub Badges - Guia de Uso

Este documento contém badges recomendados para adicionar ao README do projeto.

## 🎯 Badges de Conformidade Git/GitHub

### Git Validation Status
Mostra se o workflow de validação Git está passando:

```markdown
![Git Validation](https://github.com/git@github.com:admin-vya-digital/enterprise-hermes-agent.git/workflows/Git%20Validation/badge.svg)
```

### Conventional Commits
Indica que o projeto segue Conventional Commits:

```markdown
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow.svg)](https://conventionalcommits.org)
```

### GitHub Flow
Indica que o projeto segue GitHub Flow:

```markdown
[![GitHub Flow](https://img.shields.io/badge/Workflow-GitHub%20Flow-blue.svg)](https://docs.github.com/en/get-started/quickstart/github-flow)
```

### Branch Protection
Badge customizado indicando nível de proteção:

```markdown
<!-- Nível Mínimo -->
![Branch Protection](https://img.shields.io/badge/Branch%20Protection-Minimum-yellow)

<!-- Nível Recomendado -->
![Branch Protection](https://img.shields.io/badge/Branch%20Protection-Recommended-green)

<!-- Nível Máximo -->
![Branch Protection](https://img.shields.io/badge/Branch%20Protection-Maximum-brightgreen)
```

### Code Owner Reviews
Indica que code owner reviews estão habilitados:

```markdown
![Code Owners](https://img.shields.io/badge/Code%20Owners-Required-blue)
```

### Signed Commits
Indica que commits assinados são obrigatórios:

```markdown
![Signed Commits](https://img.shields.io/badge/Signed%20Commits-Required-green)
```

## 📊 Badges de Status

### Pull Request Size
Guidelines de tamanho de PR:

```markdown
![PR Size](https://img.shields.io/badge/PR%20Size-%E2%89%A4500%20lines-green)
```

### Required Approvals
Número de aprovações necessárias:

```markdown
<!-- 1 aprovação -->
![Approvals](https://img.shields.io/badge/Required%20Approvals-1-blue)

<!-- 2 aprovações -->
![Approvals](https://img.shields.io/badge/Required%20Approvals-2-blue)
```

## 🔧 Badges de Ferramentas

### Pre-commit Hooks
Indica uso de pre-commit hooks:

```markdown
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
```

### GitHub Actions
Status dos workflows:

```markdown
![CI](https://github.com/git@github.com:admin-vya-digital/enterprise-hermes-agent.git/workflows/CI/badge.svg)
![CD](https://github.com/git@github.com:admin-vya-digital/enterprise-hermes-agent.git/workflows/CD/badge.svg)
```

## 📝 Exemplo Completo para README

```markdown
# My Project

[![Git Validation](https://github.com/owner/repo/workflows/Git%20Validation/badge.svg)](https://github.com/owner/repo/actions)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow.svg)](https://conventionalcommits.org)
[![GitHub Flow](https://img.shields.io/badge/Workflow-GitHub%20Flow-blue.svg)](https://docs.github.com/en/get-started/quickstart/github-flow)
![Branch Protection](https://img.shields.io/badge/Branch%20Protection-Recommended-green)
![Code Owners](https://img.shields.io/badge/Code%20Owners-Required-blue)

> Project description

## Features

...
```

## 🎨 Customização

### Cores Disponíveis (shields.io)
- `brightgreen`, `green`, `yellowgreen`, `yellow`, `orange`, `red`
- `blue`, `lightgrey`, `grey`, `darkgrey`, `black`
- Hex: `#ff69b4`

### Exemplo de Badge Customizado

```markdown
![Custom](https://img.shields.io/badge/Custom-Text-color?style=flat-square&logo=github)
```

Parâmetros:
- `style`: `flat`, `flat-square`, `plastic`, `for-the-badge`, `social`
- `logo`: Nome do logo (simpleicons.org)
- `logoColor`: Cor do logo

## 📚 Referências

- [Shields.io](https://shields.io/) - Gerador de badges
- [Simple Icons](https://simpleicons.org/) - Logos disponíveis
- [GitHub Badges](https://github.com/badges/shields) - Documentação completa
