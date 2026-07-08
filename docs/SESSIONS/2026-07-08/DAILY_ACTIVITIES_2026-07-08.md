<!--
Criado em: 08/07/2026 11:10
Modificado em: 08/07/2026 11:10
-->

# 📅 Daily Activities — 2026-07-08

---

### Novo bug report: recorrência do WS 1006 + falha de `npm install` do TUI (IMP-WS1006-B)

**09:40 — ✅ Completo**

**Objetivo**: investigar por que o erro `[session ended (code 1006)]` persistia mesmo após o fix
anterior (`a1af0fb`), e por que `logs/errors.log` mostrava `npm install failed.` repetido na
inicialização da TUI.

**Contexto**: usuário reportou recorrência do bug já documentado em
`docs/bugs/BUG_REPORT_WS_1006.md`.

**Passos executados**:
1. Investigação via subagente Explore: localizado `_make_tui_argv` em `hermes_cli/main.py`,
   confirmado que o Dockerfile vendorizado já builda o `ui-tui` e aponta `HERMES_TUI_DIR` para o
   bundle pré-compilado.
2. Identificado que `docker-compose.yaml` usa imagem fixa do registry
   (`adminvyadigital/hermes-agent-api:latest`) com `build:` comentado — o compose nunca reconstrói
   localmente.
3. Confirmado que o fix do WS 1006 (`a1af0fb`) está presente no código-fonte vendorizado
   (`tui_gateway/ws.py`, `server.py`).

**Resultado**: hipótese mais provável registrada — a imagem publicada em produção provavelmente
antecede o commit do fix. Ação recomendada: confirmar data de build da imagem vs. data do commit, e
reconstruir/republicar.

**Arquivos criados**:
- `docs/bugs/BUG_REPORT_WS_1006_RECORRENCIA.md`

**Status**: ✅ Completo (investigação e documentação)

---

### Troca da fonte do hermes-agent no Dockerfile: vendorização → clone do GitHub (IMP-DOCKERFILE-SRC)

**09:50 — ✅ Completo**

**Objetivo**: parar de copiar `src/hermes_agent/hermes-agent/` (pasta vendorizada, 65M) no build da
imagem e passar a clonar o código direto do repositório upstream `NousResearch/hermes-agent`,
garantindo código atualizado e íntegro a cada build.

**Contexto**: usuário pediu para trazer o conteúdo atualizado do GitHub do hermes-agent e fazer as
customizações necessárias no Dockerfile.

**Passos executados**:
1. Comparado Dockerfile vendorizado vs. upstream atual via `gh api` — confirmadas diferenças
   (features novas: `PYTHONDONTWRITEBYTECODE`, extra `[matrix]`, layout de COPY diferente).
2. Alterado `src/hermes_agent/Dockerfile`: `COPY hermes-agent/ hermes-agent/` →
   `git clone` + `git checkout` pinado por **SHA de commit imutável** (não só a tag — uma tag pode
   ser recriada apontando para outro commit).
3. `ARG HERMES_AGENT_REPO/REF/SHA` movidos para o topo do arquivo (ARGs globais antes do primeiro
   `FROM`), redeclarados dentro do stage.
4. Testado `docker build --check` (sintaxe válida) e testes manuais de `git clone` + `checkout` +
   verificação de SHA contra o repositório real.
5. Revisão de segurança automática (background) sinalizou 2 pontos: pinning por SHA (aplicado) e
   fail-open do `git apply --reject` (mantido — decisão explícita do usuário, ver Decisões).

**Decisões técnicas**:
- Pin por SHA de commit, não só por tag (mitiga supply-chain risk de tag recriada).
- Patch best-effort com `--reject` em vez de falhar o build: usuário escolheu explicitamente essa
  opção via pergunta direta, ciente do trade-off (customizações podem ficar ausentes até
  reconciliação manual, mas o build não quebra).

**Arquivos modificados/criados**:
- `src/hermes_agent/Dockerfile` (reescrita da seção de obtenção do código-fonte)
- `scripts/update_hermes_agent_version.py` (novo — checa última release no GitHub e atualiza os
  ARGs do Dockerfile; testado dry-run e escrita real; encontrado e corrigido bug real durante o
  teste: comparação `content == new_content` dava falso positivo de "já atualizado" quando o valor
  novo coincidia com o antigo — corrigido com `re.subn` para checar match de fato)

**Status**: ✅ Completo

---

### Limpeza da pasta vendorizada `src/hermes_agent/hermes-agent/`

**10:00 — ✅ Completo**

**Objetivo**: remover a pasta vendorizada (65M, ~2500 arquivos) já que o build não depende mais
dela.

**Contexto**: consequência direta da troca de fonte do Dockerfile. Antes de apagar, preservei os
únicos arquivos com customização que não estava capturada em `hermes-agent-patches.diff` (o fix do
WS 1006, aplicado direto nos arquivos vendorizados).

**Passos executados**:
1. Copiadas cópias de referência de `tui_gateway/ws.py` e `server.py` para
   `docs/bugs/ws_1006_fix_reference/` (com README explicando que não são diff aplicável, só
   referência de leitura).
2. `git rm -r src/hermes_agent/hermes-agent/`.

**Arquivos criados**:
- `docs/bugs/ws_1006_fix_reference/tui_gateway_ws.py`
- `docs/bugs/ws_1006_fix_reference/tui_gateway_server.py`
- `docs/bugs/ws_1006_fix_reference/README.md`

**Arquivos removidos**: `src/hermes_agent/hermes-agent/` (árvore inteira, ~2500 arquivos)

**Status**: ✅ Completo

---

### Reconciliação completa do `hermes-agent-patches.diff` (14 arquivos)

**10:20 — 11:10 — ✅ Completo**

**Objetivo**: fazer com que **todas** as customizações locais em `hermes-agent-patches.diff`
apliquem limpo contra o código atual do upstream (pinado em
`HERMES_AGENT_SHA=9de9c25f620ff7f1ce0fd5457d596052d5159596`), incluindo o fix do WS 1006 que não
estava capturado no diff.

**Contexto**: o Dockerfile agora clona do GitHub e aplica esse diff com `git apply --reject`
(best-effort); qualquer hunk que não bater fica ausente da imagem até reconciliação manual. O
upstream evolui rápido (releases quase semanais), então vários hunks estavam desatualizados.

**Passos executados**:
1. **Descoberta de contaminação de teste**: um clone de teste reaproveitado entre execuções mascarou
   o estado real dos rejects (arquivos que pareciam falhar já tinham sido modificados por uma
   aplicação anterior). Refeito do zero com clone limpo — resultado real: só 6 arquivos (+ 1 arquivo
   movido) precisavam de reconciliação genuína, não 9.
2. **`tui_gateway/ws.py` / `server.py`** (fix WS 1006): re-portada a lógica (`_WRITE_EXECUTOR`
   dedicado; pool de RPC adaptativo por `os.cpu_count()`) para dentro da estrutura atual do
   upstream, que ganhou recursos novos e não relacionados desde a snapshot original (coalescing de
   tokens de streaming, desativação de Nagle, descoberta de MCP em background).
3. **`gateway/platforms/whatsapp.py`** → não existe mais; upstream migrou para
   `plugins/platforms/whatsapp/adapter.py` (sistema de plugins). Customização (override de
   `bridge_port` via env var) reportada usando o helper `env_int()` já existente no novo local.
4. **`scripts/whatsapp-bridge/bridge.js`**: dos 4 hunks antigos, 3 já não faziam sentido — o
   upstream implementou sozinho uma solução mais completa (modo `bot` + `FORWARD_OWNER_MESSAGES` +
   `classifyOwnerMessageGate` + campo `fromMe`) do que o hack de modo `mixed` do patch antigo. Só o
   hunk de escrever o QR code em `{profile}/qr/qr-connect.txt` (para o dashboard servir) ainda era
   um gap genuíno — esse foi portado.
5. **`agent/agent_runtime_helpers.py`, `agent/tool_executor.py`, `hermes_cli/tips.py`,
   `hermes_state.py`, `tools/memory_tool.py`, `tools/session_search_tool.py`**: ajustes pontuais
   (parâmetros `contact_user_id`/`user_id` para isolamento de memória/sessão por contato) contra
   parâmetros/métodos novos que o upstream inseriu no meio do código.
6. Validação: patch completo (13 arquivos, depois 14) testado com `git apply --reject` contra clone
   limpo do SHA fixado — **zero rejects, todos "Applied ... cleanly"**. Todos os `.py` passam em
   `py_compile`; `bridge.js` passa em `node --check`.

**Resultado**: `hermes-agent-patches.diff` agora reflete fielmente as customizações do projeto
contra a versão atual do upstream.

**Arquivos modificados**:
- `src/hermes_agent/hermes-agent-patches.diff` (11 blocos antigos removidos/substituídos + 3 novos
  blocos, total 14 arquivos)
- `src/hermes_agent/Dockerfile` (comentário atualizado)
- `docs/bugs/BUG_REPORT_WS_1006_RECORRENCIA.md` (status → ✅ Corrigido, detalhamento da
  reconciliação)

**Status**: ✅ Completo

---

### Novo bug report: 500 não tratado em `GET /auth/login?provider=basic` (IMP-AUTH-500)

**11:00 — ✅ Completo**

**Objetivo**: investigar exceção `NotImplementedError: BasicAuthProvider is password-only` vista em
`logs/errors.log` do container dashboard (TUI continuou funcionando normalmente durante o
incidente).

**Contexto**: usuário reportou o erro após verificar o log; pediu documentação + correção.

**Passos executados**:
1. Localizada rota `auth_login` em `hermes_cli/dashboard_auth/routes.py` — guarda
   `if not getattr(p, "supports_session", True): raise 404` deveria bloquear provedores sem suporte
   a OAuth, mas `BasicAuthProvider` nunca declarava `supports_session = False`.
2. Confirmado que é bug isolado (não sistêmico): o provedor `drain` já tem `supports_session = False`
   corretamente; `self_hosted` implementa OAuth de verdade e não precisa da flag.
3. Aplicado fix de 1 linha em `plugins/dashboard_auth/basic/__init__.py`.
4. Validado com `git apply --check` isolado, depois como parte do patch completo (14 arquivos,
   zero rejects). `py_compile` OK.

**Resultado**: `GET /auth/login?provider=basic` passa a retornar 404 limpo em vez de 500.

**Decisões técnicas**: não alterada a rota `auth_login` para capturar `NotImplementedError`
genericamente (cinto de segurança adicional) — fora do escopo do sintoma observado; registrado como
possível melhoria futura no bug report.

**Arquivos criados**:
- `docs/bugs/BUG_REPORT_DASHBOARD_AUTH_LOGIN_500.md`

**Arquivos modificados**:
- `src/hermes_agent/hermes-agent-patches.diff` (14º bloco adicionado)

**Status**: ✅ Completo

---
