---
name: messaging-bridge-troubleshooting
summary: Diagnóstico e correção de bridges de mensageria (WhatsApp/Baileys, Telegram) — modo operacional, .env protegido, travamento de portas, health-check via logs.
description: "Guia completo para diagnosticar e resolver falhas em bridges de mensageria que conectam o Hermes Agent a plataformas de chat. Cobertura: identificação de modo operacional incorreto, edição de .env protegido, liberação de portas, exportação de variáveis de ambiente, e verificação pós-restart."
trigger: "O bridge de mensageria não responde a mensagens externas, rejeita conexões, ou falha ao iniciar. Também cobre o caso em que o bridge está conectado mas o gateway Python rejeita a mensagem com 'Unauthorized user'."
pitfalls:
  - "Modo operacional incorreto: 'self-chat' aceita apenas mensagens do próprio número; trocar para 'chat' (ou 'bot') para aceitar mensagens de usuários autorizados."
  - "Dois filtros em camadas — bridge.allowlist E gateway._is_user_authorized: a allowlist do bridge (bridge.js) pode passar enquanto o gateway Python (run.py:_is_user_authorized) ainda rejeita. Verificar AMBOS os logs antes de concluir que o problema é de configuração."
  - "LID do WhatsApp Business ≠ número de telefone: Baileys identifica contatos como '<id>@lid' (ex: 233852731678761@lid) em vez de '<phone>@s.whatsapp.net' (ex: 551131357275@s.whatsapp.net). O bridge faz mapping via arquivos lid-mapping-*.json na pasta de sessão, mas o adapter Python repassa o LID cru como user_id — então a allowlist do gateway (que tem números de telefone) nunca bate. Soluções: usar WHATSAPP_ALLOWED_USERS=* (libera todos), ou adicionar o LID diretamente na allowlist, ou setar WHATSAPP_DM_POLICY=open (o adapter então não consulta allow_from e o gateway confia no que passou pelo bridge)."
  - "WHATSAPP_DM_POLICY e WHATSAPP_GROUP_POLICY não vêm populated por padrão: o adapter Python lê esses valores de os.getenv(). Sem eles no .env, o default é 'open' (ok), mas se alguém setar 'allowlist' sem prover allow_from, TODOS os DMs viram 'Unauthorized' no gateway."
  - ".env protegido por sistema: usar 'sed' via terminal para editar, não tools de escrita direta (write_file/patch)."
  - "Porta ocupada por processo zumbi: 'pkill -9 -f <process_name>' pode ser necessário quando 'SIGTERM' falha."
  - "Bridge pode não carregar .env automaticamente: exportar variáveis no shell antes de iniciar manualmente (não se aplica quando iniciado via systemd/hermes gateway start). Em multi-tenant, sempre `set -a; source ~/.hermes/profiles/<CLIENT_ID>/.env; set +a` antes do `node bridge.js`; se faltar, o health pode mostrar connected enquanto `WHATSAPP_ALLOWED_USERS`/políticas não existem no ambiente do processo e mensagens ficam silenciosas/rejeitadas."
  - "SOUL.md/persona no gateway não é hot-reload garantido por mensagem: o AIAgent monta e cacheia o system prompt por sessão. Se alterou SOUL.md e precisa efeito imediato no WhatsApp, reinicie apenas o gateway do perfil; não reinicie o bridge se foi só SOUL/persona."
  - "gateway_state.json pode ficar stale: systemctl pode mostrar 'inactive (dead)' enquanto o JSON mostra 'running'. Confiar no systemctl + 'ps -ef | grep hermes_cli' como verdade."
  - "MULTI-TENANT: gateway precisa de HERMES_HOME exportado pro diretório do perfil. Sem isso, gateway procura creds em ~/.hermes/ (legado) e aborta com 'no creds.json at <HERMES_HOME>/platforms/whatsapp/session/'. Sintoma: bridge OK + queueLength subindo + gateway.exit 'WhatsApp enabled but not paired'. Fix: `export HERMES_HOME=/home/<user>/.hermes/profiles/<CLIENT_ID>` antes de subir o gateway. Detalhes completos em `manager-profile-instance` skill (whatsapp-instances)."
  - "MULTI-TENANT: gateway procura creds em `$HERMES_HOME/platforms/whatsapp/session/`, mas bridge usa `--session <path>` arbitrário. Em perfis, criar symlink: `mkdir -p $HERMES_HOME/platforms/whatsapp && ln -sfn <SESSION_DIR> $HERMES_HOME/platforms/whatsapp/session`. Sem o symlink, gateway aborta mesmo com creds.json presente na session do perfil."
  - "PROVIDER DE IA É CONFIG DUPLA (multi-tenant): (a) `config.yaml` em `$HERMES_HOME` precisa ter provider/model. (b) Chave de API (ex: OLLAMA_API_KEY) precisa estar no `.env` de `$HERMES_HOME`. Gateway lê ambos do HERMES_HOME, não do global. Sintoma: gateway sobe sem erro mas responde 'No inference provider configured' e log mostra api_calls=0. Fix: symlinkar config.yaml do global pro perfil E adicionar chave no .env do perfil. Detalhes: whatsapp-instances/instance-number Phase 4.6."
  - "NÚMERO HOME NÃO É FONTE DA VERDADE: usuário pode informar número na Phase 1 e escanear QR com OUTRO. SEMPRE validar pós-scan via creds.json → me.id e me.lid. Caso real: backup tinha 5513988396616, admin escaneou com 551131350743. Referência: whatsapp-instances/references/validate-creds-post-scan.md."
  - "AVISO '/sethome' VAZANDO PARA CLIENTE: se novos contatos recebem '📬 No home channel is set for Whatsapp...' antes da resposta real, o perfil não tem WHATSAPP_HOME_CHANNEL no .env. Em WHATSAPP_MODE=bot, o próprio número conectado não consegue setar isso por self-chat porque mensagens fromMe=true são ignoradas. Fix: preencher WHATSAPP_HOME_CHANNEL=<lid-ou-jid-real> no .env do perfil (preferir me.lid pós-scan; fallback me.id) e reiniciar o gateway."
  - "BRIDGE E GATEWAY SÃO PROCESSOS SEPARADOS: bridge transporta WhatsApp↔HTTP, gateway é o cérebro. Sintoma clássico: bridge healthcheck mostra queueLength subindo mas usuário recebe silêncio. Fix: subir `hermes gateway run` com HERMES_HOME apontado pro perfil. NUNCA considerar provisionamento completo só com bridge conectado."
  - "SELF-MESSAGE EM MODO BOT NÃO REGISTRA: em `WHATSAPP_MODE=bot`, mensagens `fromMe=true` são tratadas como eco da automação e ignoradas pelo bridge antes do gateway. Se o número conectado manda mensagem para si mesmo, é normal não aparecer em `state.db` nem gerar resposta. Para testar self-chat, usar temporariamente `WHATSAPP_MODE=self-chat`, sabendo que DMs externas serão rejeitadas nesse modo."
---

# Messaging Bridge Troubleshooting

**Classe de tarefa**: diagnosticar e corrigir falhas em bridges de mensageria (WhatsApp via Baileys, Telegram, etc.) que conectam o Hermes Agent a plataformas de chat.

## Trigger Conditions

- Bridge não responde a mensagens de usuários externos
- Mensagens são ignoradas com erros como `self_chat_mode_rejects_non_self`
- Processo do bridge falha ao iniciar (EADDRINUSE, timeout)
- Logs mostram conexão bem-sucedida mas sem tráfego bidirecional
- Gateway log mostra `Unauthorized user: <id>@lid` enquanto o bridge log mostra a mensagem chegando — sintoma clássico de mismatch LID/número de telefone

## Phase 1 — Diagnóstico

1. **Confirmar se estamos em setup multi-tenant** (perfil isolado):
   ```bash
   echo "HERMES_HOME=${HERMES_HOME:-(não setado → setup legado)}"
   ls ~/.hermes/profiles/ 2>/dev/null && echo "→ multi-tenant ATIVO"
   ```
   Em setup multi-tenant, os logs ficam em `~/.hermes/profiles/{id}/logs/`, NÃO em `~/.hermes/logs/`. Os caminhos abaixo mostram AMBOS — use o que existir.

2. **Inspecionar logs do bridge** (`~/.hermes/profiles/{id}/logs/bridge.log` OU `~/.hermes/<platform>/bridge.log` em setup legado)
   - Buscar por `mode:`, `allowed users:`, e mensagens de rejeição (`ignored`, `rejected`)
   - Comando: `tail -f ~/.hermes/profiles/{id}/logs/bridge.log`

3. **Inspecionar logs do gateway** (`~/.hermes/profiles/{id}/logs/gateway.log` OU `~/.hermes/logs/gateway.log` em setup legado)
   - Buscar por `Unauthorized user:` — esse padrão é o bloqueio no lado PYTHON, não no bridge
   - Se aparecer, a allowlist do bridge passou; o problema é na allowlist do gateway
   - Comando: `tail -f ~/.hermes/profiles/{id}/logs/gateway.log | grep -E 'Unauthorized|whatsapp'`

4. **Verificar modo operacional** no `.env`
   - `WHATSAPP_MODE=self-chat` → aceita APENAS mensagens do próprio número
   - `WHATSAPP_MODE=chat` ou `bot` → aceita mensagens dos `WHATSAPP_ALLOWED_USERS`

5. **Confirmar lista de usuários autorizados**
   - Verificar se todos os números necessários estão em `WHATSAPP_ALLOWED_USERS`, separados por vírgula
   - **Se o log mostra `Unauthorized user: <id>@lid`**: o contato está usando o LID do WhatsApp Business, NÃO o número de telefone. Verificar se existe arquivo `lid-mapping-<phone>.json` na session. Se não existir, OU adicionar o LID direto na allowlist OU setar `WHATSAPP_ALLOWED_USERS=*` (libera todos).

6. **Confirmar políticas do adapter Python**
   - `WHATSAPP_DM_POLICY` e `WHATSAPP_GROUP_POLICY` controlam o filtro no `gateway/platforms/whatsapp.py`
   - Default é `open` (libera tudo); se setado como `allowlist` sem `allow_from`/`group_allow_from`, todos os DMs viram "Unauthorized"

7. **Checar ocupação de porta**
   - `lsof -i :<port>` para identificar PID bloqueando a porta

8. **Sintoma "mandei mensagem e não obtive resposta" — diagnostic checklist:**
   - Bridge tem `queueLength > 0` mas ninguém drena? → Gateway Python NÃO está rodando. `ps aux | grep "hermes gateway run"`. Subir conforme skill `hermes-multi-tenant-orchestrator` Phase D.
   - Gateway roda mas log mostra `No inference provider configured` ou `api_calls=0`? → Faltou symlink de `config.yaml` pro `$HERMES_HOME`. Ver skill orchestrator Phase D.2.
   - Gateway log mostra `WhatsApp enabled but not paired`? → Faltou symlink da session em `$HERMES_HOME/platforms/whatsapp/session`. Ver pitfall multi-tenant abaixo.
   - Usuário testou mandando mensagem do número conectado para ele mesmo e não há inbound no gateway/state.db? → verificar `WHATSAPP_MODE`. Em `bot`, `fromMe=true` é ignorado como eco; isso é esperado. Confirmar também o LID do número conectado via `session/lid-mapping-<phone>.json` e `<lid>_reverse.json` antes de concluir que faltou resposta.

## Phase 2 — Correção

5. **Editar `.env` via shell** (arquivo protegido)
   ```bash
   # Em setup multi-tenant, editar o .env DO PERFIL (não o global)
   sed -i 's/WHATSAPP_MODE=self-chat/WHATSAPP_MODE=bot/g' ~/.hermes/profiles/<CLIENT_ID>/.env
   sed -i 's/WHATSAPP_ALLOWED_USERS=.*/WHATSAPP_ALLOWED_USERS=*/g' ~/.hermes/profiles/<CLIENT_ID>/.env
   # IMPORTANTE: após editar .env do perfil, reiniciar BRIDGE e GATEWAY (ambos leem .env no startup)
   ```

6. **Matar processos zumbis** — SEMPRE por PID/porta, NUNCA por nome (em multi-tenant):
   ```bash
   # Bridge (SIGKILL, Node.js não responde a SIGTERM bem)
   lsof -t -i :<PORTA> | xargs -r kill -9
   # OU: kill -9 $(cat ~/.hermes/profiles/<CLIENT_ID>/bridge.pid)

   # Gateway (SIGTERM primeiro, SIGKILL depois)
   kill -TERM $(cat ~/.hermes/profiles/<CLIENT_ID>/gateway.pid)
   sleep 3
   [ ainda vivo? ] && kill -9 $(cat ~/.hermes/profiles/<CLIENT_ID>/gateway.pid)
   # NUNCA: pkill -f "hermes gateway run" — mata gateways de TODOS os perfis
   # NUNCA: pkill -f bridge.js — mata bridges de TODOS os perfis
   ```

7. **Exportar variáveis e reiniciar o bridge** (setup legado/manual)
   ```bash
   export WHATSAPP_MODE=bot
   export WHATSAPP_ALLOWED_USERS=*
   # Em multi-tenant: o source do .env do perfil já carrega isso
   node ~/.hermes/hermes-agent/scripts/whatsapp-bridge/bridge.js \
     --port 3000 \
     --session ~/.hermes/profiles/<CLIENT_ID>/session \
     --mode bot \
     > ~/.hermes/profiles/<CLIENT_ID>/logs/bridge.log 2>&1 &
   ```

## Phase 3 — Verificação

8. **Monitorar logs** — esperar: `侨 WhatsApp bridge listening on port 3000 (mode: chat)` e `✅ WhatsApp connected!`

9. **Enviar mensagem de teste** de número autorizado

10. **Confirmar echo no log** — buscar por `message_received` com `chatId` e `senderId` corretos

## Reference Cases

- **self_chat_mode_rejects_non_self**: trocar `WHATSAPP_MODE` de `self-chat` para `bot`
- **`Unauthorized user: <id>@lid` no gateway.log (bridge OK)**: LID do WhatsApp Business. Bridge allowlist passou (porque usa lid-mapping-*.json), mas gateway não — porque o adapter Python repassa o LID cru e a allowlist do gateway tem números de telefone. Fixes: (a) `WHATSAPP_ALLOWED_USERS=*` (mais permissivo), (b) adicionar o LID na allowlist junto com o telefone, (c) garantir `WHATSAPP_DM_POLICY=open` no `.env` para o adapter não bloquear antes do gateway.
- **Bridge aceita mas gateway rejeita TODOS os DMs**: `WHATSAPP_DM_POLICY=allowlist` foi setado sem `allow_from`. Setar para `open` ou prover a lista.
- **EADDRINUSE na porta 3000**: `lsof -t -i :3000 | xargs -r kill -9` + depois `lsof -i :3000` para confirmar
- **.env não lido pelo bridge** (modo manual): exportar variáveis no shell
- **"No inference provider configured" / api_calls=0**: provider não configurado no HERMES_HOME. Verificar (a) `config.yaml` do perfil com `provider:` válido, (b) chave de API no `.env` do perfil. Detalhes: whatsapp-instances/instance-number Phase 4.6.
- **"No home channel is set for Whatsapp"**: home channel não foi setado via `/sethome`. Isso é **manual** — admin precisa mandar `/sethome` pelo WhatsApp dele. Root não automatiza.
- **queueLength sobe sem cair / usuário recebe silêncio**: gateway NÃO está rodando. Sintoma bridge OK + sem resposta. `ps aux | grep "hermes gateway run"`. Subir conforme whatsapp-instances/instance-number Phase 4.5.

## Linked References

- `references/whatsapp-baileys-errors.md`: Catálogo de erros Baileys com causas e soluções.
- `scripts/bridge-healthcheck.sh`: Script de verificação rápida do bridge.
