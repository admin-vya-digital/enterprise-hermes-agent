\
# docs/guides/ — Guias e Tutoriais

Documentação how-to e tutoriais passo-a-passo.

## 🎯 Objetivo

Ensinar como realizar tarefas específicas no projeto.

## 📝 Tipos de Guias

### 1. Guias de Setup
- Como configurar ambiente de desenvolvimento
- Como rodar testes localmente
- Como fazer deploy

### 2. Guias de Desenvolvimento
- Como adicionar uma nova feature
- Como escrever testes
- Como fazer code review

### 3. Guias de Troubleshooting
- Problemas comuns e soluções
- Como debugar erros específicos

### 4. Guias de Integração
- Como integrar com serviços externos
- Como usar APIs internas

## 📂 Estrutura sugerida

```
guides/
├── setup/
│   ├── local-development.md
│   └── ci-cd-setup.md
├── development/
│   ├── adding-features.md
│   └── testing-guide.md
└── troubleshooting/
    └── common-issues.md
```

## 📝 Template de Guia

```markdown
# [Nome da Tarefa]

**Objetivo**: [O que você vai aprender]
**Pré-requisitos**: [O que precisa antes]
**Tempo estimado**: X minutos

## Passo 1: [Ação]
[Instruções detalhadas]

\`\`\`bash
# Comandos exemplo
\`\`\`

## Passo 2: [Ação]
...

## Validação
Como verificar que funcionou:
- [ ] Check 1
- [ ] Check 2

## Troubleshooting
**Erro X**: Solução Y
```

## 🔗 Ver também

- [INDEX.md](../INDEX.md) — Índice geral da documentação
- [templates/](../templates/) — Templates reutilizáveis
