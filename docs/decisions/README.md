# docs/decisions/ — Architecture Decision Records (ADRs)

Registro formal de decisões arquiteturais do projeto.

## 🎯 Objetivo

Documentar **decisões irreversíveis ou caras de reverter** de forma estruturada.

## 📝 Formato ADR

```markdown
# ADR-NNN: [Título da Decisão]

**Status**: Aceita | Proposta | Depreciada | Substituída por ADR-XXX
**Data**: YYYY-MM-DD
**Decisores**: [Quem tomou a decisão]

## Contexto
[Forças em jogo, restrições, requisitos]

## Decisão
[O que foi decidido]

## Consequências
**Positivas**:
- ...

**Negativas**:
- ...

**Riscos**:
- ...

## Alternativas Consideradas
1. [Opção descartada] — [Por que foi rejeitada]
2. ...
```

## 🔍 Quando criar ADR

- Escolha de banco de dados
- Arquitetura de microserviços vs monolito
- Padrões de autenticação
- Estratégia de deployment
- Frameworks principais

## 📂 Nomenclatura

`ADR-NNN-[titulo-kebab-case].md`

Exemplos:
- `ADR-001-escolha-postgresql.md`
- `ADR-002-arquitetura-event-driven.md`

## 🔗 Recursos

- [ADR GitHub](https://adr.github.io/)
- [decisions/](../decisions/) (esta pasta)
- [debates/](../debates/) — Discussões que antecederam a decisão
