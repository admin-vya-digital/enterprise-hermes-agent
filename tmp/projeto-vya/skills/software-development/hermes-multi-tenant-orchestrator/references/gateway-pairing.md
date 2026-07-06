# Gateway Pairing & Provider Configuration

> Session 2026-06-26 com Jordão, primeiro perfil `jordao-teste`.
> Captura receita end-to-end (bridge + gateway + provider) e 3 bugs reais encontrados.

## Receita: provisionar perfil que RESPONDE mensagens de verdade

Subir só o bridge = mensagem entra na fila mas ninguém drena. Você PRECISA de bridge + gateway + provider configurado. Sequência mínima que funcionou:

```bash
# 0. Já ter o bridge rodando (Phase C do wizard-flow)

# 1. Symlinks obrigatórios pro gateway encontrar o que precisa
HERMES_HOME=~/.hermes/profiles/jordao-teste
SESSION_DIR=~/.hermes/profiles/jordao-teste/session

mkdir -p $HERMES_HOME/platforms/whatsapp
ln -sfn $SESSION_DIR $HERMES_HOME/platforms/whatsapp/session    # creds

ln -sfn ~/.hermes/config.yaml $HERMES_HOME/config.yaml          # provider global

# 2. Subir gateway em background (NUNCA nohup & em foreground do terminal)
set -a && source ~/.hermes/profiles/jordao-teste/.env && set +a
export HERMES_HOME=$HERMES_HOME
export VIRTUAL_ENV=~/.hermes/hermes-agent/venv
export PATH=$VIRTUAL_ENV/bin:$PATH
hermes gateway run --replace > ~/.hermes/profiles/jordao-teste/logs/gateway.log 2>&1 &

# 3. Esperar 8s e validar
sleep 8
grep -E "whatsapp connected|Cron ticker" ~/.hermes/profiles/jordao-teste/logs/gateway.log
# Deve mostrar AMBAS as linhas. Se não mostrar, ver "Diagnóstico" abaixo.

# 4. Smoke test do provider isolado
echo "oi" | timeout 30 hermes chat --model minimax-m3
# Deve responder QUALQUER COISA ≠ erro. Se der erro de provider, ver config.yaml.
```

## Diagnóstico dos 3 bugs que apareceram em produção

### Bug 1 — Gateway não sobe: "WhatsApp enabled but not paired"

**Sintoma:**
```
WARNING gateway.platforms.whatsapp: WhatsApp is enabled but not paired 
  (no creds.json at /home/praxislatina/.hermes/profiles/jordao-teste/platforms/whatsapp/session/creds.json)
ERROR gateway.run: Gateway hit a non-retryable startup conflict
```

**Causa:** Gateway procura creds em `$HERMES_HOME/platforms/whatsapp/session/` mas o bridge salva creds em qualquer path passado via `--session`. Em perfis, os dois caminhos divergem por padrão.

**Fix:** symlink
```bash
mkdir -p $HERMES_HOME/platforms/whatsapp
ln -sfn $SESSION_DIR $HERMES_HOME/platforms/whatsapp/session
```

### Bug 2 — Gateway sobe, conecta WhatsApp, mas responde em modo degradado

**Sintoma no log do gateway:**
```
WARNING: Primary provider auth failed: No inference provider configured
INFO: response ready: ... api_calls=0 response=199 chars
```
Mensagem chega pro usuário MAS é fallback genérico (não foi gerada por IA).

**Causa:** Gateway lê `config.yaml` em `$HERMES_HOME`, não em `~/.hermes/`. Mesmo com `OLLAMA_API_KEY` no `.env` global, gateway não vê porque não tem config.yaml no diretório do perfil.

**Fix:** symlink
```bash
ln -sfn ~/.hermes/config.yaml $HERMES_HOME/config.yaml
```
E reiniciar o gateway (`pkill -TERM -f "hermes gateway run"`, esperar 3s, re-start).

### Bug 3 — Bridge fica em `queueLength=1` eterno

**Sintoma:**
- Bridge health: `{"status":"connected","queueLength":1,...}`
- Gateway: não está rodando (`ps aux | grep "hermes gateway run"` vazio)
- Usuário mandou msg mas nunca recebeu resposta

**Causa:** Wizard subiu só o bridge e parou. Gateway não foi levantado.

**Fix:** Bug 1 + Bug 2 = gateway funcionando. Após restart, `queueLength` cai pra 0 e mensagem é processada.

## Por que `hermes doctor`/systemd unit existente não basta

O unit `~/.config/systemd/user/hermes-gateway.service` foi feito pro modelo legado:
- `WorkingDirectory=/home/<user>/.hermes` (não o perfil)
- `HERMES_HOME=/home/<user>/.hermes` (não o perfil)
- Comando: `hermes gateway run --replace`

Se você só der `systemctl --user start hermes-gateway.service`, ele vai subir com `HERMES_HOME=~/.hermes/` (legado), procurar creds em `~/.hermes/platforms/whatsapp/session/`, não encontrar nada, e cair nos bugs 1+2.

**Workaround:** ou edita o unit pra aceitar env vars por perfil, ou inicia o gateway manualmente com `HERMES_HOME` exportado (receita acima). A segunda opção é mais simples e dá pra automatizar com `terminal(background=true, notify_on_complete=false)`.

## Como testar fim-a-fim sem telefone extra

`curl -X POST http://localhost:3000/send` injeta mensagem OUTBOUND (bot → alguém), mas o gateway só loga INBOUND. Logo: **curl não testa o pipeline.** Você PRECISA de outro celular mandando WhatsApp real pro bot.

Se você não tem segundo celular:
1. Use o WhatsApp Web do outro número
2. Ou simule via a CLI do Baileys injetando mensagem (não documentado, frágil)
3. Ou peça pro usuário fazer o teste manualmente

## Arquivos que precisam coexistir num perfil funcional

```
~/.hermes/profiles/jordao-teste/
├── .env                          # vars do perfil
├── config.yaml -> ~/.hermes/config.yaml   # symlink pro global
├── produto.md                    # contexto de negócio
├── platforms/
│   └── whatsapp/
│       └── session -> ../session # symlink pra creds
├── session/
│   └── creds.json                # real, criado pelo QR scan
└── logs/
    ├── bridge.log                # log do bridge Node
    └── gateway.log               # log do gateway Python
```

Sem `config.yaml` e sem `platforms/whatsapp/session` como symlinks, o gateway não funciona. Wizard Phase D.1 e D.2 cuidam disso — não pule.

## Comando de restart consolidado

Sempre que mudar `.env` do perfil, restart **só do gateway** (bridge não precisa):

```bash
pkill -TERM -f "hermes gateway run"
sleep 3
ps aux | grep "hermes gateway run" | grep -v grep && echo "AINDA VIVO" || echo "MORTO"

set -a && source ~/.hermes/profiles/{id}/.env && set +a
export HERMES_HOME=~/.hermes/profiles/{id}
export VIRTUAL_ENV=~/.hermes/hermes-agent/venv
export PATH=$VIRTUAL_ENV/bin:$PATH
hermes gateway run --replace > ~/.hermes/profiles/{id}/logs/gateway.log 2>&1 &
```

Use `kill -TERM` (não `-9`) — gateway tem cleanup handler que suspende sessão corretamente.