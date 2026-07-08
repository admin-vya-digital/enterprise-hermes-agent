<!--
Criado em: 08/07/2026 09:40
Modificado em: 08/07/2026 11:30
-->

# 🐛 Bug Report — Recorrência do WS 1006 + falha de `npm install` do TUI em produção

**Status**: ✅ Corrigido (todas as 13 customizações reconciliadas no `hermes-agent-patches.diff`, aguardando build/deploy)
**Severidade**: P1 — chat do Dashboard segue instável em produção mesmo após fix anterior
**Componentes**: `comp/dashboard`, `comp/tui`, `comp/gateway`, `comp/deploy`
**Reportado em**: 08/07/2026
**Referência**: continuação de [BUG_REPORT_WS_1006.md](BUG_REPORT_WS_1006.md) (fix `a1af0fb`, 07/07/2026)

---

## Sintoma

O erro `[session ended (code 1006)]` no chat do Dashboard **continua ocorrendo** mesmo após o fix aplicado e documentado em `BUG_REPORT_WS_1006.md`. Em paralelo, `logs/errors.log` mostra falhas repetidas na inicialização do TUI:

```
Installing TUI dependencies…
npm install failed.
npm install failed.
npm install failed.
... (padrão repetido a cada novo container/sessão)
→ Skipping web UI build (--skip-build); using dist at /app/hermes-agent/hermes_cli/web_dist
  Hermes Web UI → http://0.0.0.0:9119
```

---

## Diagnóstico (investigação de código, sem alteração)

### 1. Origem do `npm install failed.`

`src/hermes_agent/hermes-agent/hermes_cli/main.py`, função `_make_tui_argv` (~linhas 1478-1549):

- Se `HERMES_TUI_DIR` aponta para um diretório com `dist/entry.js` já presente, o launcher usa o **fast path** (bundle pré-compilado) e nunca chama `npm install`.
- Só cai no branch de `npm install` (linha ~1530) quando essa condição falha — ou seja, quando o container **não tem o bundle do TUI pré-construído no lugar esperado**.
- O subprocess roda com `stdout=PIPE, stderr=PIPE` e, em caso de erro, deveria imprimir as últimas 30 linhas de saída — mas o log real mostra "npm install failed." **sem nenhum detalhe de erro**, sugerindo que a saída do npm veio vazia (consistente com falha de resolução de diretório/lockfile, não com erro de rede).

### 2. O Dockerfile já resolve isso — mas só se a imagem certa estiver rodando

`src/hermes_agent/hermes-agent/Dockerfile` (linhas ~176-178, ~253-267):

```dockerfile
RUN cd ui-tui && npm run build
ENV HERMES_TUI_DIR=/opt/hermes/ui-tui
```

O comentário do próprio Dockerfile explica que, sem essa `ENV` apontando para o bundle já construído, o `node_modules` do container nunca converge com o `package-lock.json` do monorepo, e o `npm install` de runtime falha/repete a cada sessão de PTY — inclusive citando corrida entre chats simultâneos (`ENOTEMPTY`) como causa de "chat tab dies with [session ended]".

### 3. Causa raiz mais provável: imagem de produção desatualizada

`src/hermes_agent/docker-compose.yaml` (linhas ~7-10, ~33-36, ~90) usa **imagem fixa do registry**, com o `build:` comentado em todos os serviços:

```yaml
    # build:
    #   context: .
    image: adminvyadigital/hermes-agent-api:latest
```

Ou seja, o compose **nunca reconstrói localmente** — sempre puxa `adminvyadigital/hermes-agent-api:latest`. As correções do fix anterior (`a1af0fb`, `tui_gateway/ws.py` e `tui_gateway/server.py`) só chegam ao container rodando se essa imagem tiver sido **rebuilt e republicada** após o commit.

Confirmado que o código-fonte atual **contém** o fix:
- `tui_gateway/ws.py` — `_WRITE_EXECUTOR` (executor dedicado de escrita) presente.
- `tui_gateway/server.py` — pool de RPC adaptativo por CPU presente.

Como o sintoma 1006 persiste apesar disso, a hipótese mais provável é que **a imagem publicada no registry ainda é anterior ao commit `a1af0fb`** e/ou não inclui o `ui-tui` pré-compilado corretamente associado a `HERMES_TUI_DIR` — o que reintroduziria tanto o `npm install` de runtime falhando quanto o comportamento de fechamento abrupto da conexão.

### 4. Ambiente verificado

- Node fixado no Dockerfile: `node:22-bookworm-slim` (pinado por SHA).
- Node local: `v22.18.0` — compatível.
- `ui-tui/node_modules` não existe no checkout local (esperado, é gerado no build da imagem) — não foi possível inspecionar o conteúdo da imagem publicada nesta investigação (requer acesso ao registry/produção).

---

## Atualização 08/07/2026 10:20 — troca de fonte no Dockerfile (`src/hermes_agent/Dockerfile`)

Trocamos `COPY hermes-agent/ hermes-agent/` por `git clone` + `checkout tags/v2026.7.7.2` do
upstream `NousResearch/hermes-agent`, aplicando `hermes-agent-patches.diff` por cima (best-effort,
`git apply --reject`). Testado localmente contra a tag: **7 dos 11 arquivos do diff têm hunks
rejeitados ou falham por completo** (`gateway/platforms/whatsapp.py` nem existe mais nesse caminho
na tag atual) — o upstream evoluiu significativamente desde que o diff foi gerado.

Confirmado também que o fix de WS 1006 (`tui_gateway/ws.py` / `server.py`, commit `a1af0fb`) **não
está** no `hermes-agent-patches.diff` — foi aplicado direto nos arquivos vendorizados, fora do
mecanismo de patch. Com a troca para clone remoto, esse fix **deixa de existir na imagem** até ser
reconciliado manualmente contra o código atual do upstream (os PRs que ele porta, #42956 e #42983,
seguem abertos/não mergeados).

**Ação pendente antes do próximo build de produção**: re-derivar o fix de `tui_gateway` como um
diff válido contra `v2026.7.7.2` (ou tag mais recente) e adicioná-lo ao
`hermes-agent-patches.diff`, além de reconciliar os 7 arquivos com rejects. Enquanto isso não for
feito, builds a partir do Dockerfile atualizado **reintroduzem o WS 1006**.

## Atualização 08/07/2026 10:55 — fix de `tui_gateway` reconciliado

O código do fix (executor dedicado `_WRITE_EXECUTOR` em `ws.py`; pool de RPC adaptativo por CPU em
`server.py`) foi re-portado manualmente da cópia de referência preservada em
[docs/bugs/ws_1006_fix_reference/](ws_1006_fix_reference/) para dentro da estrutura atual do
upstream (o arquivo tinha evoluído com recursos novos e não relacionados — coalescing de tokens de
streaming, desativação de Nagle, descoberta de MCP em background — que não existiam na snapshot
antiga onde o fix foi originalmente aplicado). A lógica em si (offload do `fut.result()` bloqueante
para fora da thread do worker de RPC; tamanho do pool de RPC baseado em `os.cpu_count()`) foi
preservada, só a "casca" ao redor mudou.

**Validado**: o diff resultante foi testado com `git apply --check` contra um clone limpo de
`HERMES_AGENT_SHA=9de9c25f620ff7f1ce0fd5457d596052d5159596` — aplica limpo
(`Applied patch tui_gateway/ws.py cleanly` / `... server.py cleanly`), sem rejects. Ambos os
arquivos resultantes passam em `python3 -m py_compile`. Adicionado ao final de
`src/hermes_agent/hermes-agent-patches.diff`.

## Atualização 08/07/2026 11:30 — todas as customizações reconciliadas

Os outros 9 arquivos do `hermes-agent-patches.diff` também foram reconciliados manualmente contra
`HERMES_AGENT_SHA=9de9c25f620ff7f1ce0fd5457d596052d5159596`:

- `agent/agent_init.py`, `cron/scheduler.py`, `gateway/slash_access.py` — já aplicavam limpos (a
  investigação anterior estava contaminada por um clone de teste reaproveitado entre execuções;
  refeito do zero com clone limpo).
- `agent/agent_runtime_helpers.py`, `agent/tool_executor.py` — hunk de 1 linha (`contact_user_id=`)
  reaplicado no mesmo call site, código ao redor inalterado.
- `hermes_cli/tips.py` — troca de uma string na lista `TIPS`, reaplicada como estava.
- `hermes_state.py` — 5 dos 7 hunks já batiam; os 2 que faltavam (assinatura de
  `list_sessions_rich` e docstring de `search_messages`) foram reconciliados contra os novos
  parâmetros que o upstream adicionou no meio (`search_query`, `compacted`).
- `tools/memory_tool.py` — o `__init__`/`_get_memory_dir` ganhou vizinhos novos
  (`_MAX_CONSOLIDATION_FAILURES_PER_TURN`, `reset_consolidation_failures`); reconciliado preservando
  o código novo.
- `tools/session_search_tool.py` — 7 dos 10 hunks já batiam; os 3 que faltavam foram reconciliados
  linha a linha contra o código atual.
- `gateway/platforms/whatsapp.py` **não existe mais** — o upstream moveu o adapter para
  `plugins/platforms/whatsapp/adapter.py` (sistema de plugins novo). A customização (override de
  `bridge_port` via env var) foi reportada para o novo local usando o helper `env_int()` que já
  existe ali, em vez do `isdigit()` manual do patch antigo.
- `scripts/whatsapp-bridge/bridge.js` — dos 4 hunks antigos, **3 já não fazem sentido**: o upstream
  evoluiu esse arquivo sozinho e já implementa o que o patch tentava adicionar (modo `bot` +
  `WHATSAPP_FORWARD_OWNER_MESSAGES` + gate de allowlist via `classifyOwnerMessageGate`, campo
  `fromMe` no evento) de forma mais completa que o nosso hack de modo `mixed`. Só o hunk 1 (escrever
  o QR code em `{profile}/qr/qr-connect.txt` para o dashboard servir) ainda era um gap genuíno e foi
  reportado.

**Validado**: patch completo (13 arquivos) testado com `git apply --reject` contra um clone limpo
do SHA fixado — **zero rejects, todos "Applied ... cleanly"**. Todos os arquivos Python resultantes
passam em `py_compile`; `bridge.js` passa em `node --check`.

## Próximos passos recomendados

1. **Confirmar a data de build da imagem em produção** vs. data do commit `a1af0fb` (07/07/2026) — comparar `docker inspect adminvyadigital/hermes-agent-api:latest` (labels/criação) com o histórico de commits. *(Requer acesso a produção; não executado aqui por exigir credenciais.)*
2. **Rebuildar e republicar a imagem** a partir do `Dockerfile` atual, garantindo que o build stage `npm run build` do `ui-tui` execute com sucesso e que `HERMES_TUI_DIR=/opt/hermes/ui-tui` aponte para o bundle resultante.
3. Após republicar, **recriar os containers** (`docker compose up -d --pull always`) e validar:
   - Ausência de `npm install failed.` no `logs/errors.log` na subida.
   - Múltiplas abas de chat simultâneas no Dashboard sem `[session ended (code 1006)]`.
4. Considerar destravar o `build:` no `docker-compose.yaml` (ou adicionar step de CI) para que o pipeline de deploy sempre reconstrua a imagem a partir do código vendorizado atual, evitando divergência silenciosa entre repo e imagem publicada — esse gap parece ser a causa raiz comum aos dois sintomas.

## Arquivos relevantes (apenas leitura nesta investigação)

- `src/hermes_agent/hermes-agent/hermes_cli/main.py` (`_make_tui_argv`)
- `src/hermes_agent/hermes-agent/Dockerfile`
- `src/hermes_agent/docker-compose.yaml`
- `src/hermes_agent/hermes-agent/tui_gateway/ws.py`
- `src/hermes_agent/hermes-agent/tui_gateway/server.py`
- `logs/errors.log`

## Referências

- Bug anterior: [BUG_REPORT_WS_1006.md](BUG_REPORT_WS_1006.md)
- Commit do fix anterior: `a1af0fb` — fix(tui-gateway): corrige encerramento de chat com WS 1006 no Dashboard
