<!--
Criado em: 07/07/2026 09:42
Modificado em: 07/07/2026 09:42
-->

# 📅 Atividades Diárias — 07/07/2026

---

### Debug do erro `[session ended (code 1006)]` no Chat do Dashboard Hermes

**09:42 — ✅ Completo**

**Objetivo**: Encontrar e corrigir a causa do erro `session ended (code 1006)` exibido no chat embutido do Dashboard Hermes.

**Contexto**: Usuários reportaram que a sessão de chat do dashboard (`hermes.vya.digital/chat`) encerrava abruptamente com o código de fechamento WebSocket 1006 (fechamento anormal, gerado pelo navegador).

**Passos executados**:
1. Exploração do código-fonte vendorizado do `hermes-agent` (subagente `Explore`) para mapear o fluxo do WebSocket do chat (`ChatPage.tsx` → `web_server.py` → `pty_bridge.py` → `tui_gateway/ws.py`).
2. Localização da mensagem "session ended (code N)" em `ChatPage.tsx` — fallback genérico do `ws.onclose` para códigos não customizados.
3. Análise de `logs/errors.log`, encontrando `ws write failed ... TimeoutError` recorrente ~10.2s após cada `pty accepted`, batendo com `_WS_WRITE_TIMEOUT_S = 10.0` em `tui_gateway/ws.py`.
4. Identificação da causa raiz: `WSTransport.write()` bloqueava a thread do pool de RPC (padrão, hardcoded em 4 workers) por até 10s aguardando confirmação do event loop; sob concorrência (múltiplas sessões de chat + leitura contínua do PTY), o pool saturava, o timeout estourava e a conexão fechava sem frame de close limpo → 1006 no navegador.
5. Busca no repositório upstream `NousResearch/hermes-agent` (`gh search prs/issues`) por correções já propostas para o mesmo sintoma — localizados PR #42983 (executor dedicado de escrita) e PR #42956 (pool de RPC adaptativo por CPU), ambos abertos e não mergeados.
6. Portagem dos diffs (`gh pr diff`) para a cópia vendorizada em `src/hermes_agent/hermes-agent/tui_gateway/{server,ws}.py`.
7. Validação funcional isolada: teste com `FakeWS` simulando event loop travado por 15s confirmou que `write()` agora retorna em ~1.5ms em vez de bloquear a thread chamadora por até 10s.
8. Confirmação de `_DEFAULT_RPC_POOL_WORKERS = 24` (antes 4, fixo) nesta máquina (12 vCPUs).
9. Build e push da imagem `adminvyadigital/hermes-agent-api:latest` realizados pelo usuário fora do escopo desta sessão.

**Resultado**: Causa raiz identificada e corrigida via portagem de correções upstream ainda não mergeadas. Validação funcional local bem-sucedida. Pendente: redeploy dos containers (`docker compose up -d`) e validação em produção com múltiplas abas de chat simultâneas.

**Decisões técnicas**:
- Optou-se por portar as correções já existentes no upstream (mantendo paridade futura com merge upstream) em vez de escrever uma solução própria do zero.
- Mantida a semântica de "keep-alive on timeout" do PR #42983 (não fechar a sessão em timeout de escrita, apenas logar aviso) em vez de aumentar o timeout de 10s para um valor maior, seguindo a decisão documentada no próprio PR upstream.

**Arquivos modificados/criados**:
- `src/hermes_agent/hermes-agent/tui_gateway/server.py` (+2/-2)
- `src/hermes_agent/hermes-agent/tui_gateway/ws.py` (+~90/-~20)
- `docs/SESSIONS/2026-07-07/BUG_REPORT_WS_1006.md` (novo)
- `docs/SESSIONS/2026-07-07/DAILY_ACTIVITIES_2026-07-07.md` (novo)

**Commits**:
- (pendente nesta sessão)

**Status**: ✅ Completo (correção de código); 🔵 Em progresso (validação pós-deploy)

---
