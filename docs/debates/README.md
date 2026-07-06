# docs/debates/ — Debates Técnicos e de Produto

Armazena debates estruturados sobre decisões importantes do projeto.

## 🎯 Objetivo

Documentar o **processo de decisão** — não apenas o resultado, mas também:
- Alternativas consideradas
- Prós e contras de cada opção
- Contexto da decisão
- Participantes do debate

## 📝 Formato

Use o template de debate (agent `@template-architect` ou manual):

```markdown
# DEBATE: [Título da Questão]

**Data**: YYYY-MM-DD
**Participantes**: @user1, @user2, AI Agent
**Contexto**: [Por que este debate é necessário?]

## Questão Central
[Pergunta clara que precisa ser respondida]

## Alternativas

### Opção A: [Nome]
**Prós**: ...
**Contras**: ...

### Opção B: [Nome]
**Prós**: ...
**Contras**: ...

## Decisão
[Escolha + Justificativa]

## Ações
- [ ] Implementar X
- [ ] Documentar em decisions/
```

## 🔍 Quando usar

- Mudanças de arquitetura significativas
- Escolha entre tecnologias/frameworks
- Decisões que afetam múltiplos times
- Trade-offs complexos

## 📂 Nomenclatura

`DEBATE_[TOPICO]_YYYY-MM-DD.md`

Exemplos:
- `DEBATE_SPEC_DRIVEN_DEVELOPMENT_2026-04-05.md`
- `DEBATE_ESCOLHA_ORM_2026-03-15.md`

## 🔗 Ver também

- [decisions/](../decisions/) — Registro formal de decisões (ADRs)
- [retrospectives/](../retrospectives/) — Aprendizados pós-sprint
