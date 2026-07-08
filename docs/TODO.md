# 📝 TODO — Enterprise Hermes Agent

**Last Updated**: 2026-07-08T11:10:00Z — Reconciliação completa do hermes-agent-patches.diff ✅ Concluído
**Status**: 🟢 Em andamento

---

## 🟠 Em Progresso

- [ ] Rebuildar e republicar a imagem `adminvyadigital/hermes-agent-api:latest` a partir do
      Dockerfile atualizado (clone do GitHub + patches reconciliados) e validar em produção que o
      WS 1006 não recorre com múltiplas abas de chat simultâneas
- [ ] Confirmar se `docker-compose.yaml` deve destravar o `build:` (hoje comentado, sempre puxa
      imagem fixa do registry) para evitar divergência silenciosa entre repo e imagem publicada

## 🔵 Pendente

- [ ] Configurar estrutura inicial do projeto
- [ ] Adicionar testes unitários
- [ ] Documentar APIs
- [ ] Avaliar se vale capturar `NotImplementedError` genericamente na rota `auth_login`
      (`hermes_cli/dashboard_auth/routes.py`) como cinto de segurança adicional — ver
      [docs/bugs/BUG_REPORT_DASHBOARD_AUTH_LOGIN_500.md](bugs/BUG_REPORT_DASHBOARD_AUTH_LOGIN_500.md)

## ✅ Concluído

- [x] Scaffold inicial gerado (2026-07-06T12:07:01Z)
- [x] Bug fix: chat do Dashboard encerrava com `[session ended (code 1006)]` — ver [docs/bugs/BUG_REPORT_WS_1006.md](bugs/BUG_REPORT_WS_1006.md) (2026-07-07)
- [x] Dockerfile passa a clonar `hermes-agent` direto do GitHub (pinado por SHA de commit imutável) em vez de copiar pasta vendorizada — ver [docs/bugs/BUG_REPORT_WS_1006_RECORRENCIA.md](bugs/BUG_REPORT_WS_1006_RECORRENCIA.md) (2026-07-08)
- [x] Script `scripts/update_hermes_agent_version.py` criado para checar última release do GitHub e atualizar o Dockerfile (2026-07-08)
- [x] Pasta vendorizada `src/hermes_agent/hermes-agent/` removida (65M, ~2500 arquivos) — build não depende mais dela (2026-07-08)
- [x] Todas as 14 customizações do `hermes-agent-patches.diff` reconciliadas contra o código atual do upstream — zero rejects (2026-07-08)
- [x] Bug fix: 500 não tratado em `GET /auth/login?provider=basic` — ver [docs/bugs/BUG_REPORT_DASHBOARD_AUTH_LOGIN_500.md](bugs/BUG_REPORT_DASHBOARD_AUTH_LOGIN_500.md) (2026-07-08)
