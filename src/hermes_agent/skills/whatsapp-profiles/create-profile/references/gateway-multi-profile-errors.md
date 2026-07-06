# Gateway Multi-Profile — Erros e Falsos Diagnósticos

> Referência condensada de erros reais vividos no provisionamento e manutenção de perfis multi-tenant (WhatsApp/Baileys + gateway Python). Cada bloco mostra: sintoma → diagnóstico errado fácil → causa raiz → fix mínimo.
> Última atualização: 2026-06-26, após consolidação dos aprendizados do perfil `<CLIENT_ID>`.

---

## Separação de responsabilidades das skills

Use esta referência como apoio diagnóstico, mas execute a operação pela skill correta:

| Situação | Skill operacional |
|---|---|
| Criar um perfil novo do zero | `create-profile` |
| Alterar/reiniciar/re-sincronizar um perfil existente | `edit-profile` |
| Apagar completamente um perfil | `delete-profile` |
| Apagar histórico Hermes de um contato específico sem deslogar WhatsApp | `reset-profile-history` |

Regra prática: `create-profile` é wizard de criação. Se o perfil já existe, não use `create-profile` como procedimento principal; use `edit-profile` ou `reset-profile-history` conforme o alvo.

---

## Erro 1 — "Bridge conectado, mas ninguém responde"

### Sintoma

- Bridge healthcheck: `{"status":"connected","queueLength":1}` ou queueLength subindo.
- Gateway Python não está rodando ou não está drenando a fila.
- Usuário manda mensagem no WhatsApp e não recebe resposta.

### Diagnóstico errado fácil

> "Bridge está conectado, então deve ser problema de allowlist, @lid ou modelo."

### Causa raiz

Bridge Node.js e Gateway Python são processos separados. Bridge só transporta mensagens WhatsApp↔HTTP. Gateway é o cérebro Hermes. Sem gateway vivo, mensagens entram na fila do bridge e ninguém processa.

### Fix mínimo

```bash
PROFILE="$HOME/.hermes/profiles/<CLIENT_ID>"
set -a; source "$PROFILE/.env"; set +a
export HERMES_HOME="$PROFILE"
export VIRTUAL_ENV="$HOME/.hermes/hermes-agent/venv"
export PATH="$VIRTUAL_ENV/bin:$PATH"
nohup hermes gateway run --replace > "$PROFILE/logs/gateway.log" 2>&1 &
echo $! > "$PROFILE/gateway.pid"
```

### Verificação

```bash
PORT=$(grep -oP '^BRIDGE_PORT=\K.*' "$PROFILE/.env")
curl -s "http://localhost:$PORT/health"
ps -p "$(cat "$PROFILE/gateway.pid")" -o pid=,cmd=
grep -E "✓ whatsapp connected|response ready|Sending response" "$PROFILE/logs/gateway.log" | tail -10
```

---

## Erro 2 — "WhatsApp enabled but not paired" mesmo com creds no perfil

### Sintoma

```text
WARNING gateway.platforms.whatsapp: WhatsApp is enabled but not paired
  (no creds.json at /home/<USER>/.hermes/platforms/whatsapp/session/creds.json)
ERROR gateway.run: Gateway exiting cleanly: whatsapp: WhatsApp enabled but not paired
```

### Diagnóstico errado fácil

> "O creds.json sumiu. Vou pedir QR novo."

### Causa raiz

O gateway resolve paths usando `HERMES_HOME`. Se `HERMES_HOME` não aponta para o perfil, ele procura no `~/.hermes/` global. Em multi-tenant, o creds real fica em:

```text
~/.hermes/profiles/<CLIENT_ID>/session/creds.json
```

Além disso, mesmo com `HERMES_HOME` correto, o gateway espera o creds em:

```text
$HERMES_HOME/platforms/whatsapp/session/creds.json
```

### Fix mínimo

```bash
PROFILE="$HOME/.hermes/profiles/<CLIENT_ID>"
export HERMES_HOME="$PROFILE"
mkdir -p "$HERMES_HOME/platforms/whatsapp"
ln -sfn "$PROFILE/session" "$HERMES_HOME/platforms/whatsapp/session"
ls -la "$HERMES_HOME/platforms/whatsapp/session/creds.json"
```

Depois suba o gateway com `HERMES_HOME=$PROFILE`.

---

## Erro 3 — "HOME_NUMBER no .env está certo, mas home channel não funciona"

### Sintoma

- Perfil tem `HOME_NUMBER=<phone>` no `.env` e/ou em `produto.md`.
- Gateway ainda reclama de falta de home channel ou envia onboarding `/sethome` para novos contatos.
- Notificações internas não chegam ao dono/admin esperado.

### Diagnóstico errado fácil

> "HOME_NUMBER é o canal home funcional do gateway. Se ele está preenchido, deveria rotear."

### Causa raiz

`HOME_NUMBER` é metadado de governança/auditoria. O gateway não usa essa variável para roteamento.

O canal home funcional do WhatsApp é:

```bash
WHATSAPP_HOME_CHANNEL=<lid-ou-jid-normalizado>
WHATSAPP_HOME_CHANNEL_NAME=<nome-amigavel>
WHATSAPP_HOME_CHANNEL_THREAD_ID=
```

`/sethome` é uma forma in-chat de gravar esse destino, mas não é a única. No fluxo Root multi-tenant, após validar `session/creds.json`, o Root pode preencher `WHATSAPP_HOME_CHANNEL` diretamente no `.env` do perfil quando conhece o LID/JID correto.

### Fix mínimo

1. Validar `session/creds.json` pós-scan.
2. Derivar o LID real preferindo `creds.me.lid`, normalizado de `954...:17@lid` para `954...@lid`.
3. Usar `creds.me.id` normalizado como fallback.
4. Manter `HOME_NUMBER=<telefone>` como metadado.
5. Gravar `WHATSAPP_HOME_CHANNEL=<lid-ou-jid>` no `.env` do perfil.
6. Reiniciar somente o gateway do perfil por PID para recarregar env.

### Caso real

No `<CLIENT_ID>`, o canal funcional ficou:

```bash
WHATSAPP_HOME_CHANNEL=<LID_EXEMPLO_3>@lid
WHATSAPP_HOME_CHANNEL_NAME=<CLIENT_ID>
WHATSAPP_HOME_CHANNEL_THREAD_ID=
HOME_NUMBER=<NUMERO_HOME_EXEMPLO>
```

---

## Erro 4 — "Número informado e número escaneado divergem"

### Sintoma

- Admin informa um número na coleta inicial.
- QR é escaneado com outro número.
- `.env`, `produto.md` ou documentação ficam com número errado se o wizard confiar no que foi dito ou em backup antigo.

### Diagnóstico errado fácil

> "O admin disse X; vou gravar X."

### Causa raiz

Admin pode informar número A e escanear com número B. Backups `.env` antigos também são armadilha. O único dado confiável pós-scan é `session/creds.json` gerado pelo Baileys.

### Fix mínimo

```bash
python3 - <<'PY'
import json, pathlib, re
profile = pathlib.Path.home() / '.hermes/profiles/<CLIENT_ID>'
creds = json.loads((profile / 'session/creds.json').read_text())
me = creds.get('me') or {}
phone = re.sub(r':.*@', '@', me.get('id') or '')
lid = re.sub(r':.*@', '@', me.get('lid') or '')
print('phone:', phone)
print('lid:  ', lid)
print('name: ', me.get('name'))
PY
```

Se o phone divergir do número informado, pare e pergunte ao admin antes de gravar `HOME_NUMBER`/documentação.

### Caso real

Backup antigo indicava `<NUMERO_ALT_EXEMPLO>`. O QR foi escaneado com `<NUMERO_HOME_EXEMPLO>`. Pós-scan revelou:

```text
phone=<NUMERO_HOME_EXEMPLO>:17@s.whatsapp.net
lid=<LID_EXEMPLO_3>:17@lid
```

---

## Erro 5 — "QR ficou stale"

### Sintoma

- Bridge está rodando há minutos sem scan.
- Usuário escaneia PNG antigo salvo em `/tmp/qr.png` ou no perfil.
- WhatsApp diz QR inválido ou nada acontece.

### Causa raiz

Baileys rotaciona o QR periodicamente enquanto ninguém autentica. PNG salvo pode apontar para uma string antiga.

### Fix mínimo

Regenerar o PNG a partir do QR atual, se o bridge estiver persistindo `/tmp/qr.txt` via patch temporário:

```bash
python3 - <<'PY'
import pathlib, qrcode
client = '<CLIENT_ID>'
data = pathlib.Path('/tmp/qr.txt').read_text().strip()
img = qrcode.make(data)
img.save('/tmp/qr.png')
img.save(str(pathlib.Path.home() / f'.hermes/profiles/{client}/qr/qr-connect.png'))
PY
```

Se não houver `/tmp/qr.txt`, usar o QR atual do `bridge.log`/stdout ou reiniciar o bridge daquele perfil para gerar novo QR. Reverter qualquer patch temporário no `bridge.js` depois do pareamento.

---

## Erro 6 — "Gateway responde No inference provider configured"

### Sintoma

```text
WARNING gateway.run: Primary provider auth failed: No inference provider configured.
ERROR gateway.run: response ready: api_calls=0
```

Bot sobe, recebe mensagem, mas não chama o modelo.

### Causa raiz

Gateway precisa de dois arquivos no `$HERMES_HOME` do perfil:

- `config.yaml` com `provider:` e `model:` válidos.
- `.env` com a chave de API do provider, por exemplo `OLLAMA_API_KEY=...`.

Em multi-tenant, `config.yaml` normalmente é symlink do global; `.env` normalmente tem cópia da chave. Se a chave global muda, o perfil não atualiza sozinho.

### Fix mínimo

```bash
PROFILE="$HOME/.hermes/profiles/<CLIENT_ID>"
ln -sfn "$HOME/.hermes/config.yaml" "$PROFILE/config.yaml"

for key in OLLAMA_API_KEY OPENROUTER_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY; do
  if grep -q "^$key=" "$HOME/.hermes/.env"; then
    val=$(grep "^$key=" "$HOME/.hermes/.env" | cut -d= -f2-)
    if grep -q "^$key=" "$PROFILE/.env"; then
      sed -i "s|^$key=.*|$key=$val|" "$PROFILE/.env"
    else
      printf '\n%s=%s\n' "$key" "$val" >> "$PROFILE/.env"
    fi
  fi
done
```

Depois reiniciar o gateway do perfil por PID e validar que não aparece mais `No inference provider configured` no log.

---

## Erro 7 — "Slash commands vazam para cliente comum"

### Sintoma

Cliente comum consegue chamar comandos como `/help`, `/restart`, `/model`, `/tools`, `/skills`, `/cron`, ou recebe ajuda operacional do Hermes.

### Diagnóstico errado fácil

> "Basta configurar user_allowed_commands: [] e pronto."

### Causa raiz

Neste ambiente, a política desejada é admin-only. A config global restringe comandos, mas `/help` só ficou bloqueável depois do patch no core `gateway/slash_access.py`, deixando apenas `/whoami` como always-allowed.

### Fix mínimo

Garantir em `~/.hermes/config.yaml`:

```yaml
gateway:
  platforms:
    whatsapp:
      extra:
        allow_admin_from:
          - "<ROOT_ADMIN_LID>@lid"
        user_allowed_commands: []
        group_allow_admin_from:
          - "<ROOT_ADMIN_LID>@lid"
        group_user_allowed_commands: []
```

E confirmar no core:

```python
_ALWAYS_ALLOWED_FOR_USERS = frozenset({
    "whoami",
})
```

---

## Erro 8 — "Tool calls/previews aparecem no WhatsApp"

### Sintoma

Cliente vê mensagens como:

```text
send_message: "to whatsapp: ..."
vision_analyze: "..."
skill_view: ...
```

### Diagnóstico errado fácil

> "É só pedir no SOUL para não mostrar ferramentas."

### Causa raiz

O vazamento principal é configuração de apresentação do gateway, não apenas prompt. Para cliente final no WhatsApp, progresso de ferramentas deve ficar desligado.

### Fix mínimo

Garantir em `~/.hermes/config.yaml`:

```yaml
display:
  platforms:
    whatsapp:
      tool_progress: "off"
      tool_preview_length: 0
      show_reasoning: false
      busy_ack_detail: false
```

Adicionar também guardrail no `SOUL.md` do perfil: nunca mencionar nomes de ferramentas, chamadas, argumentos, previews ou logs internos ao usuário final.

---

## Referência rápida: tree correta de um perfil provisionado

```text
~/.hermes/profiles/<CLIENT_ID>/
├── .env                                  # WHATSAPP_*, BRIDGE_PORT, GATEWAY_PORT, HOME_NUMBER, provider keys
├── config.yaml -> ~/.hermes/config.yaml  # provider/model global
├── SOUL.md                               # persona/comportamento do tenant
├── produto.md                            # contexto de negócio
├── session/                              # creds Baileys/WhatsApp
├── platforms/whatsapp/session -> ../../session
├── logs/bridge.log
├── logs/gateway.log
├── bridge.pid
└── gateway.pid
```

---

## TL;DR operacional

1. Bridge conectado não basta; gateway precisa estar vivo e drenando fila.
2. Gateway sempre sobe com `HERMES_HOME` apontando para o perfil.
3. Gateway espera creds em `$HERMES_HOME/platforms/whatsapp/session/creds.json`; use symlink para `session/`.
4. `HOME_NUMBER` é metadado; `WHATSAPP_HOME_CHANNEL` é o roteamento funcional do home channel.
5. Validar `creds.json` pós-scan antes de confiar em número informado ou backup antigo.
6. Provider exige `config.yaml` + chave no `.env` do perfil.
7. Slash commands são admin-only; `/whoami` é o único always-allowed para usuário comum.
8. WhatsApp cliente final deve ter `display.platforms.whatsapp.tool_progress: "off"`.
9. Nunca usar `pkill -f` em ambiente multi-tenant; matar por PID/porta do perfil.
10. Para perfil existente, use `edit-profile`, `delete-profile` ou `reset-profile-history`; `create-profile` é só criação nova.
