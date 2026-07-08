<!--
Criado em: 08/07/2026 09:59
Modificado em: 08/07/2026 09:59
-->

# Cópias de referência — fix WS 1006 (pré-remoção da pasta vendorizada)

Cópias exatas de `tui_gateway/ws.py` e `tui_gateway/server.py` como estavam em
`src/hermes_agent/hermes-agent/` no commit `a1af0fb` (fix do WS 1006, ver
[BUG_REPORT_WS_1006.md](../BUG_REPORT_WS_1006.md)), preservadas **antes** de
`src/hermes_agent/hermes-agent/` ser removida (o Dockerfile passou a clonar o
código direto do upstream — ver [BUG_REPORT_WS_1006_RECORRENCIA.md](../BUG_REPORT_WS_1006_RECORRENCIA.md)).

**Estes arquivos NÃO são um diff aplicável.** A base sobre a qual foram
patchados (snapshot vendorizado em 07/07/2026) já diverge significativamente
do upstream atual (ex: `ws.py` upstream tem 466 linhas contra 348 aqui —
o upstream ganhou recursos novos, como coalescing de tokens de streaming,
que não existiam nesta snapshot). Um `git apply`/`diff -u` direto contra o
código atual **não bate** linha a linha.

**Uso pretendido**: referência de leitura para re-portar manualmente a lógica
do fix (executor dedicado de escrita `_WRITE_EXECUTOR` em `ws.py`, pool de RPC
adaptativo por CPU em `server.py`) para dentro da versão atual do upstream, e
então registrar o resultado como um novo diff em `hermes-agent-patches.diff`.
Até essa reconciliação acontecer, o fix **não está presente** no código
baixado pelo Dockerfile (que agora clona do GitHub — ver
`src/hermes_agent/Dockerfile`).
