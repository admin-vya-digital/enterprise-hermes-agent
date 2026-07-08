# 📚 Índice — Enterprise Hermes Agent

**Projeto**: `enterprise-hermes-agent`
**Criado em**: 2026-07-06T12:07:01Z
**Last Updated**: 2026-07-08T11:10:00Z
**Last Session**: 2026-07-08 — Dockerfile passa a clonar hermes-agent do GitHub; reconciliação completa dos patches; fix do 500 em /auth/login

---

## Documentação Principal

| Arquivo | Descrição |
|---------|-----------|
| [README.md](../README.md) | Documentação pública |
| [TODO.md](TODO.md) | Tarefas pendentes |
| [TODAY_ACTIVITIES.md](TODAY_ACTIVITIES.md) | Atividades do dia |

## Sessões de Trabalho

```
SESSIONS/
└── YYYY-MM-DD/
    ├── SESSION_RECOVERY_YYYY-MM-DD.md
    ├── DAILY_ACTIVITIES_YYYY-MM-DD.md
    ├── SESSION_REPORT_YYYY-MM-DD.md
    └── FINAL_STATUS_YYYY-MM-DD.md
```

### 2026-07-07

| Arquivo | Descrição |
|---------|-----------|
| [bugs/BUG_REPORT_WS_1006.md](bugs/BUG_REPORT_WS_1006.md) | Bug report: chat do Dashboard encerrava com `session ended (code 1006)` |
| [SESSIONS/2026-07-07/DAILY_ACTIVITIES_2026-07-07.md](SESSIONS/2026-07-07/DAILY_ACTIVITIES_2026-07-07.md) | Log de atividades da sessão |

### 2026-07-08

| Arquivo | Descrição |
|---------|-----------|
| [bugs/BUG_REPORT_WS_1006_RECORRENCIA.md](bugs/BUG_REPORT_WS_1006_RECORRENCIA.md) | Recorrência do WS 1006 + troca do Dockerfile para clonar hermes-agent do GitHub + reconciliação completa do patch |
| [bugs/BUG_REPORT_DASHBOARD_AUTH_LOGIN_500.md](bugs/BUG_REPORT_DASHBOARD_AUTH_LOGIN_500.md) | Bug report: 500 não tratado em `GET /auth/login?provider=basic` |
| [bugs/ws_1006_fix_reference/](bugs/ws_1006_fix_reference/) | Cópias de referência do fix WS 1006 preservadas antes da remoção da pasta vendorizada |
| [SESSIONS/2026-07-08/DAILY_ACTIVITIES_2026-07-08.md](SESSIONS/2026-07-08/DAILY_ACTIVITIES_2026-07-08.md) | Log de atividades da sessão |

---

*Gerado por scaffold.py em 2026-07-06T12:07:01Z*
