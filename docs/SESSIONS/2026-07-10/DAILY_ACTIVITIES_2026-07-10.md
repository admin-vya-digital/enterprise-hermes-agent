<!--
Criado em: 10/07/2026 21:35
Modificado em: 10/07/2026 21:35
-->

# Atividades — 10/07/2026

---

### Merge do PR #6 — routers completos do proxy docker-api

**19:00 — ✅ Completo**

**Objetivo**: Integrar ao `main` os routers completos do proxy `hermes-interaction-api` (PR #6, autor jordaoaq).

**Contexto**: O proxy só repassava `/health` e `/agents` para a `vya-workforce-api`; as demais rotas de agente davam 404.

**Passos executados**:
1. Revisão do diff (17 arquivos, +499/−1, tudo em `src/vyadigital_api/`; sem segredos hardcoded)
2. Merge squash via `gh pr merge 6 --squash`
3. `git pull --ff-only` no clone local
4. Build de teste da imagem (`vyadigital-api:pr6-test`) e validação: app importa, 10 routers registrados sob `/api/v1`, 20 paths no OpenAPI, `python-multipart` instalado

**Resultado**: Código no `main` e pronto para novo build Docker.

**Commits**:
- `b1a7b31` — feat(docker-api): completa proxy com routers de skills, knowledge, calendar, followup, contacts, memory, whatsapp e observability (#6)

**Status**: ✅ Completo

---

### Correção do login bloqueado no dashboard após rebuild ([#7](https://github.com/admin-vya-digital/enterprise-hermes-agent/issues/7))

**21:30 — ✅ Completo**

**Objetivo**: Restaurar o login no dashboard (`vya-workforce-dashboard`) e tornar a correção persistente a rebuilds.

**Contexto**: Após reiniciar o container, o dashboard exibia "Sign-in unavailable". O hermes-agent atualizado (clonado do GitHub no build) tornou os plugins opt-in (`plugins.enabled`), e o plugin `dashboard_auth/basic` deixou de carregar — os secrets `HERMES_DASHBOARD_BASIC_AUTH_*` estavam corretos.

**Passos executados**:
1. Diagnóstico: registry de auth providers vazio; plugin bundled presente mas não habilitado
2. Hotfix no container: `hermes plugins enable dashboard_auth/basic` + restart — login restaurado (gravado no volume `/app/profiles`, persiste)
3. Correção persistente: habilitação idempotente no `src/hermes_agent/entrypoint.sh` quando `HERMES_DASHBOARD_BASIC_AUTH_USERNAME` presente
4. Bug reports: issues [#7](https://github.com/admin-vya-digital/enterprise-hermes-agent/issues/7) (auth do dashboard) e [#8](https://github.com/admin-vya-digital/enterprise-hermes-agent/issues/8) (Dependency Graph desabilitado quebra o check "Review Dependencies" em todos os PRs)

**Decisões técnicas**: enable incondicional e idempotente no entrypoint (exit 0 quando já habilitado), usando caminho explícito do venv (`hermes` não está no PATH do container).

**Arquivos modificados/criados**:
- src/hermes_agent/entrypoint.sh (+13/−0)

**Commits**:
- `03ad69a` — fix(hermes-agent): habilita dashboard_auth/basic no entrypoint de forma idempotente

**Status**: ✅ Completo

---
