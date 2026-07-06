# docs/retrospectives/ — Retrospectivas e Lições Aprendidas

Documentação de aprendizados de sprints, incidentes e projetos.

## 🎯 Objetivo

Capturar **lições aprendidas** para melhorar continuamente.

## 📝 Tipos de Retrospectivas

### 1. Retrospectiva de Sprint
Aprendizados do ciclo de desenvolvimento (semanal/quinzenal)

### 2. Post-Mortem de Incidente
Análise de falhas em produção

### 3. Retrospectiva de Projeto
Review ao final de projeto/feature grande

## 📝 Template: Retrospectiva de Sprint

```markdown
# Retrospectiva Sprint NN — YYYY-MM-DD

**Período**: DD/MM a DD/MM
**Participantes**: [Time]

## ✅ O que funcionou bem
- ...

## ⚠️ O que pode melhorar
- ...

## 💡 Insights e Aprendizados
- ...

## 🎯 Ações para próxima sprint
- [ ] Ação 1
- [ ] Ação 2

## 📊 Métricas
- Velocity: X pontos
- Bugs encontrados: Y
- Deploy frequency: Z
```

## 📝 Template: Post-Mortem

```markdown
# Post-Mortem: [Descrição do Incidente]

**Data do incidente**: YYYY-MM-DD HH:MM
**Duração**: X horas
**Severidade**: Critical | High | Medium
**Impacto**: [Quantos usuários afetados]

## Timeline
- HH:MM - Detecção
- HH:MM - Resposta iniciada
- HH:MM - Causa identificada
- HH:MM - Mitigação aplicada
- HH:MM - Resolução completa

## Causa Raiz
[5 Whys ou análise detalhada]

## Ações Corretivas
- [ ] Curto prazo (hoje)
- [ ] Médio prazo (esta semana)
- [ ] Longo prazo (preventivo)

## Lições Aprendidas
1. ...
2. ...
```

## 📂 Nomenclatura

- Sprints: `RETRO_SPRINT_NN_YYYY-MM-DD.md`
- Post-mortems: `POSTMORTEM_[INCIDENTE]_YYYY-MM-DD.md`
- Projetos: `RETRO_[NOME_PROJETO]_YYYY-MM-DD.md`

## 🔗 Ver também

- [debates/](../debates/) — Decisões técnicas
- [SESSIONS/](../SESSIONS/) — Atividades diárias
