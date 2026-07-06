# Catálogo de Erros Baileys — WhatsApp Bridge

Coleção de erros observados em bridges WhatsApp/Baileys com causas e soluções.

---

## `self_chat_mode_rejects_non_self`

**Contexto no log**: mensagem recebida é descartada sem qualquer resposta ao remetente.

```
{"event":"ignored","reason":"self_chat_mode_rejects_non_self","chatId":"...","senderId":"..."}
```

**Causa**: O bridge está rodando em `WHATSAPP_MODE=self-chat`, que por definição aceita APENAS mensagens originadas do próprio número do bot.

**Solução**:
1. Alterar `WHATSAPP_MODE=self-chat` → `WHATSAPP_MODE=chat` (ou `bot`) no `.env`
2. Reiniciar o bridge exportando a variável: `export WHATSAPP_MODE=chat`
3. Verificar no log: `🌉 WhatsApp bridge listening on port 3000 (mode: chat)`

**Regra de ouro**: se o objetivo é comunicação bidirecional com usuários externos, `self-chat` está SEMPRE errado.

---

## `Unauthorized user: <id>@lid` no gateway.log (bridge aceita, gateway rejeita)

**Contexto no log**: o `bridge.log` mostra a mensagem chegando e sendo enfileirada, mas `~/.hermes/logs/gateway.log` mostra:

```
WARNING gateway.run: Unauthorized user: 233852731678761@lid (Nome do Contato) on whatsapp
```

A allowlist do bridge (`WHATSAPP_ALLOWED_USERS` em `bridge.js`) PASSOU — o bridge tem mapeamento LID↔phone via `lid-mapping-*.json`. Mas o **adapter Python** (`gateway/platforms/whatsapp.py:1288`) repassa o `senderId` cru (o LID) como `user_id` para o gateway. Aí `_is_user_authorized` em `gateway/run.py:7448` compara o LID contra uma allowlist que tem números de telefone, e nunca bate.

**Diagnóstico**:
1. Confirmar o mismatch:
   ```bash
   cat ~/.hermes/whatsapp/session/creds.json | python3 -c "import json,sys; c=json.load(sys.stdin); print('me.id=', c.get('me',{}).get('id')); print('me.lid=', c.get('me',{}).get('lid'))"
   ```
2. Verificar se existem arquivos de mapping na sessão:
   ```bash
   ls ~/.hermes/whatsapp/session/lid-mapping-<phone>*.json
   ```
   Se `lid-mapping-551131357275.json` existe e contém `"233852731678761"`, o mapping está correto — o bridge vai usar, mas o gateway Python não.
3. Confirmar a política do adapter:
   ```bash
   grep -E "WHATSAPP_(DM|GROUP)_POLICY" ~/.hermes/.env
   ```

**Soluções (em ordem de preferência)**:

(a) **Liberar geral** (se o número do bot deve responder a qualquer um):
```bash
sed -i 's|^WHATSAPP_ALLOWED_USERS=.*|WHATSAPP_ALLOWED_USERS=*|' ~/.hermes/.env
# Adicionar se não existir:
grep -q "^WHATSAPP_DM_POLICY=" ~/.hermes/.env || echo "WHATSAPP_DM_POLICY=open" >> ~/.hermes/.env
grep -q "^WHATSAPP_GROUP_POLICY=" ~/.hermes/.env || echo "WHATSAPP_GROUP_POLICY=open" >> ~/.hermes/.env
```

(b) **Whitelist específica incluindo o LID** (mais restritivo):
```
WHATSAPP_ALLOWED_USERS=5513988396616,551131357275,233852731678761
```

(c) **Forçar adapter a não bloquear** (assume que o bridge já filtra):
```
WHATSAPP_DM_POLICY=open
WHATSAPP_GROUP_POLICY=open
```

Depois de qualquer mudança, reiniciar o gateway:
```bash
hermes gateway restart
# ou, se systemd:
systemctl --user restart hermes-gateway.service
```

E verificar:
```bash
tail -f ~/.hermes/logs/gateway.log | grep -E "whatsapp|Unauthorized"
tail -f ~/.hermes/whatsapp/bridge.log
```

**Pitfall**: muitos contatos WhatsApp Business não têm LID conhecido pelo bot (não há mapping file). Para esses, a única solução sem reiniciar a sessão é (a) ou (b) com o LID exato. O bridge descobre LIDs novos à medida que recebe mensagens, então o mapping cresce organicamente em `~/.hermes/whatsapp/session/`.

---

## `EADDRINUSE` na porta 3000

**Contexto no log**: o bridge falha ao iniciar com mensagem `Error: listen EADDRINUSE: address already in use :::3000`.

**Causa**: Instância anterior do `bridge.js` ainda está rodando e ocupando a porta.

**Solução**:
1. Identificar PID: `lsof -i :3000`
2. Matar forçado: `pkill -9 -f "bridge.js"`
3. Repetir até `lsof -i :3000` retornar vazio
4. Reiniciar o bridge

**Pitfall**: `pkill -f "bridge.js"` sem `-9` (SIGTERM) pode não funcionar se o processo está travado — usar `SIGKILL` como fallback.

---

## `.env` não aplicado ao bridge (modo manual)

**Contexto**: as variáveis no `.env` foram atualizadas, mas o bridge continua rodando com valores antigos. Não se aplica quando o bridge é iniciado via `hermes gateway start` ou systemd.

**Causa**: O script Node.js pode não estar carregando `.env` automaticamente (depende de `dotenv` estar ou não no entrypoint).

**Solução**: Exportar explicitamente no shell ANTES de iniciar:
```
export WHATSAPP_MODE=chat
export WHATSAPP_ALLOWED_USERS=5513988396616,551131357275
node ~/.hermes/hermes-agent/scripts/whatsapp-bridge/bridge.js ...
```

---

## `creds.json` corrompido

**Contexto**: o bridge falha com `SyntaxError: Unexpected token` ao ler `session/creds.json`.

**Causa**: Arquivo de sessão Baileys foi sobrescrito parcialmente ou baixou com encoding errado.

**Solução**:
1. `rm ~/.hermes/whatsapp/session/creds.json`
2. Reiniciar o bridge — ele irá gerar nova sessão e disparar o QR code para re-autenticação

---

## `gateway_state.json` stale vs systemctl

**Contexto**: `systemctl --user status hermes-gateway.service` mostra `inactive (dead)` mas o arquivo `~/.hermes/gateway_state.json` tem `"gateway_state":"running"` e um PID antigo.

**Causa**: O arquivo é atualizado pelo processo Python em runtime; se o processo for morto sem cleanup limpo (SIGKILL, OOM kill), o arquivo fica com dados velhos.

**Solução**:
1. Confiar no `systemctl` + `ps -ef | grep hermes_cli` como verdade
2. Limpar o arquivo stale: `rm ~/.hermes/gateway_state.json` (será recriado no próximo start)
3. Iniciar via `systemctl --user start hermes-gateway.service` ou `hermes gateway start`

**Pitfall**: NÃO confiar no JSON para diagnóstico — sempre cruzar com `ps` e `systemctl`.

---

## Health-check de sucesso

Após correção e restart, o log deve exibir:

```
🌉 WhatsApp bridge listening on port 3000 (mode: chat)
✅ WhatsApp connected!
```

E o health-check HTTP retorna:
```bash
curl -s http://localhost:3000/health
# {"status":"connected","queueLength":0,"uptime":<segundos>}
```

Se essas linhas aparecerem, o número do bot estiver listado em `Allowed users`, e o `gateway.log` não registrar novos `Unauthorized user:`, o bridge está operacional e respondendo.
