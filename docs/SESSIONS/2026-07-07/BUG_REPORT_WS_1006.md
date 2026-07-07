<!--
Criado em: 07/07/2026 09:42
Modificado em: 07/07/2026 09:42
-->

# 🐛 Bug Report — Chat do Dashboard encerra com `[session ended (code 1006)]`

**Status**: ✅ Corrigido (aguardando validação em produção pós-deploy)
**Severidade**: P2 — impacta a usabilidade do chat embutido do Dashboard Hermes
**Componentes**: `comp/dashboard`, `comp/tui`, `comp/gateway`
**Reportado em**: 07/07/2026
**Referência upstream**: [NousResearch/hermes-agent#42983](https://github.com/NousResearch/hermes-agent/pull/42983), [NousResearch/hermes-agent#42956](https://github.com/NousResearch/hermes-agent/pull/42956)

---

## Sintoma

Ao usar a aba `/chat` do Dashboard Hermes (`hermes.vya.digital`), a sessão de terminal embutido (xterm.js) encerra abruptamente exibindo:

```
[session ended (code 1006)]
```

O código 1006 é um código de fechamento **anormal** gerado pelo próprio navegador (RFC 6455) — indica que a conexão WebSocket caiu sem um frame de close válido ter sido recebido do servidor.

---

## Ambiente

- Deploy via `docker-compose.yaml` (Traefik como proxy reverso, não nginx)
- Imagem: `adminvyadigital/hermes-agent-api:latest`
- Serviços afetados: `dashboard` (porta 9119) e `gateway`
- `hermes-agent` vendorizado em `src/hermes_agent/hermes-agent/`

---

## Fluxo afetado

```
xterm.js (ChatPage.tsx)
  → WebSocket /api/pty?token=<session>  (terminal, PTY)
  → WebSocket /api/ws                    (JSON-RPC, sidebar/eventos)
  → FastAPI (hermes_cli/web_server.py)
  → tui_gateway/ws.py (WSTransport)
  → node ui-tui/dist/entry.js (via PTY)
```

---

## Diagnóstico

### 1. Onde a mensagem aparece

`web/src/pages/ChatPage.tsx` (handler `ws.onclose`) — é o **fallback genérico** exibido quando o código de fechamento recebido não é nenhum dos códigos customizados que o servidor emite de propósito (`4401` auth, `4403` host/origin, `4404` chat desabilitado, `4408` peer não permitido, `1011` erro já reportado via ANSI). Como `1006` não é nenhum desses, cai no fallback — ou seja, **o servidor não estava fechando a conexão de forma limpa**.

### 2. Evidência nos logs

`logs/errors.log` mostrou o padrão:

```
19:50:35 INFO  hermes_cli.web_server: pty accepted peer=<IP_INTERNO_DOCKER> mode=gated cred=ticket
19:50:46 WARNING tui_gateway.ws: ws write failed peer=<IP_INTERNO_DOCKER>:53576 error_type=TimeoutError
19:52:06 INFO  hermes_cli.web_server: pty accepted peer=<IP_INTERNO_DOCKER> mode=gated cred=ticket
19:52:16 WARNING tui_gateway.ws: ws write failed peer=<IP_INTERNO_DOCKER>:34456 error_type=TimeoutError
```

O `TimeoutError` ocorre consistentemente **~10.1–10.2s** após cada `pty accepted` — coincidindo exatamente com a constante `_WS_WRITE_TIMEOUT_S = 10.0` em `tui_gateway/ws.py`.

### 3. Causa raiz

O canal JSON-RPC (`/api/ws`) despachava cada mensagem via `asyncio.to_thread` usando o **pool de threads padrão do processo**, e o canal PTY (`/api/pty`) também consumia esse mesmo pool a cada leitura (`loop.run_in_executor(None, bridge.read, 0.2)`, a cada 0.2s por sessão de chat aberta).

Antes da correção, `WSTransport.write()` bloqueava a **própria thread do pool de RPC** por até 10s (`fut.result(timeout=10)`) esperando o event loop confirmar o envio do frame. Com múltiplas sessões de chat simultâneas, o pool saturava, o event loop demorava mais que 10s para confirmar a escrita, o timeout estourava, o transporte era marcado como fechado (`_closed = True`), e a conexão era encerrada **sem enviar um frame de close válido** ao navegador — que reporta isso como `1006`.

Dois fatores agravantes:
1. **Pool de RPC hardcoded em 4 workers** (`tui_gateway/server.py`), independente da quantidade de CPUs disponíveis.
2. **Nenhum isolamento** entre o trabalho de I/O (aguardar confirmação de escrita) e o trabalho de despacho de RPC — ambos competiam pelo mesmo pool.

---

## Correção aplicada

Portadas duas correções já propostas (mas ainda não mergeadas) no repositório upstream `NousResearch/hermes-agent`:

### 1. `tui_gateway/server.py` — pool de RPC adaptativo por CPU
_(baseado em [PR #42956](https://github.com/NousResearch/hermes-agent/pull/42956))_

- Antes: `_rpc_pool_workers` fixo em `4` (a menos que `HERMES_TUI_RPC_POOL_WORKERS` estivesse setado).
- Depois: `_DEFAULT_RPC_POOL_WORKERS = max(8, min(32, cpu_count * 2))` — nesta máquina resultou em **24 workers** em vez de 4.
- A variável de ambiente `HERMES_TUI_RPC_POOL_WORKERS` continua funcionando como override.

### 2. `tui_gateway/ws.py` — executor dedicado para confirmação de escrita
_(baseado em [PR #42983](https://github.com/NousResearch/hermes-agent/pull/42983))_

- Antes: `WSTransport.write()` chamado por uma thread do pool de RPC bloqueava essa thread com `fut.result(timeout=10)`.
- Depois: a espera pela confirmação de escrita foi movida para um `ThreadPoolExecutor` dedicado de 2 threads (`_WRITE_EXECUTOR`), separado do pool de RPC. `write()` agora **retorna imediatamente** (o worker de RPC nunca fica bloqueado por I/O).
- Semântica de timeout preservada: se o event loop não confirmar o envio em 10s, é registrado um aviso (`ws write slow ...`) mas a conexão **permanece viva** — o frame já foi agendado e será entregue assim que o loop "respirar". Isso evita tanto o travamento do pool de RPC quanto o fechamento prematuro da sessão.

### Validação

Teste funcional isolado (thread + event loop simulando travamento de 15s):

```
thread alive after join(2)? False    elapsed reported: 0.0015s
PASS: write() retornou imediatamente, sem bloquear a thread chamadora
```

Antes da correção, essa mesma chamada bloquearia a thread por até 10s.

`_DEFAULT_RPC_POOL_WORKERS` verificado em runtime: `24` (nesta máquina, 12 vCPUs).

---

## Arquivos alterados

- `src/hermes_agent/hermes-agent/tui_gateway/server.py`
- `src/hermes_agent/hermes-agent/tui_gateway/ws.py`

## Deploy

Build e push da imagem `adminvyadigital/hermes-agent-api:latest` já realizados fora desta sessão. Pendente: recriar os containers `dashboard` e `gateway` (`docker compose up -d`) para que a nova imagem entre em produção, e validar em `hermes.vya.digital` com múltiplas abas de chat abertas simultaneamente.

## Referências

- Upstream issues relacionadas: [#42938](https://github.com/NousResearch/hermes-agent/issues/42938), [#42942](https://github.com/NousResearch/hermes-agent/issues/42942)
- Upstream feature relacionada (não aplicada): [#46354](https://github.com/NousResearch/hermes-agent/issues/46354) — auto-restore de sessão TUI após fechamento de WebSocket (1006/1012)
