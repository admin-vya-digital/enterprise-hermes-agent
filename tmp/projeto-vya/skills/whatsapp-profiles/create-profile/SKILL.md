---
name: create-profile
summary: Criar uma nova instância/perfil WhatsApp-Baileys do zero no Hermes Agent multi-tenant (QR code → sessão → home channel → gateway Python → provider). Cobre somente configuração inicial de perfil novo.
description: "Use quando o Root Admin pedir para criar/provisionar um novo perfil. Procedimento de configuração inicial: cria pastas isoladas, aloca portas, gera .env, valida QR/creds, configura WHATSAPP_HOME_CHANNEL, inicia bridge Baileys, sobe gateway Python, configura provider e cria produto.md. Não usar como procedimento principal para perfil já existente; nesses casos use edit-profile, delete-profile ou reset-profile-history."

note_on_naming: |
  Este skill foi originalmente registrado como `manager-profile-instance` e depois `instance-number`.
  O nome canônico no registry é `create-profile`.
trigger: "O usuário (Hermes Root / admin) pede para criar um novo cliente, provisionar um novo perfil ou adicionar uma nova instância de bot isolada. Para perfil já existente, não usar esta skill como procedimento principal: usar edit-profile para alteração/restart/re-sync, delete-profile para remoção, reset-profile-history para histórico de contato, e as referências desta skill apenas como material diagnóstico quando necessário."
pitfalls:
  - "NUNCA usar 'pkill -f bridge.js' ou 'pkill -9 node', pois isso matará os agentes de TODOS os clientes rodando no container. Sempre matar processos vinculados especificamente à porta do cliente ou ao PID salvo na pasta do perfil."
  - "NUNCA editar o arquivo global ~/.hermes/.env para configurar perfis. Cada cliente deve ter seu arquivo isolado em ~/.hermes/profiles/<CLIENT_ID>/.env. O global pode ser tocado para re-sync em massa (ver references/provider-key-resync.md)."
  - "@lid do WhatsApp Business: O Baileys identifica contatos como '<id>@lid' e NÃO como '<phone>@s.whatsapp.net'. A configuração WHATSAPP_ALLOWED_USERS=* no .env de CADA cliente garante que o gateway não bloqueie a mensagem prematuramente, delegando a validação para a lógica interna."
  - "HOME_NUMBER é METADADO DE GOVERNANÇA — gravado no .env/produto.md para histórico, mas NÃO é a env var que o gateway lê. O canal home real do gateway é WHATSAPP_HOME_CHANNEL. No provisionamento, após validar creds.json, preencher WHATSAPP_HOME_CHANNEL com o LID/JID real do número conectado para evitar o aviso de UX 'No home channel is set' em todo primeiro contato. /sethome é apenas a forma in-chat de gravar esse env; Root pode gravar WHATSAPP_HOME_CHANNEL diretamente no .env do perfil quando já conhece o chat_id/LID correto."
  - "SLASH COMMANDS SÃO ADMIN-ONLY POR CONFIG + PATCH: o Root admin WhatsApp é o LID do operador (`<ROOT_ADMIN_LID>`), informado por ele — NÃO é um valor fixo, pergunte/confirme, nunca reutilize o LID de outro perfil. Todo provisionamento deve garantir em `~/.hermes/config.yaml` (global, symlinkado pelos perfis) `gateway.platforms.whatsapp.extra.allow_admin_from` e `group_allow_admin_from` contendo esse LID, com `user_allowed_commands: []` e `group_user_allowed_commands: []`. Além disso, `gateway/slash_access.py` é patchado para deixar apenas `/whoami` em `_ALWAYS_ALLOWED_FOR_USERS`; `/help` é admin-only."
  - "BRIDGE ≠ GATEWAY: o bridge Node.js (porta <PORTA>) só TRANSPORTA mensagens WhatsApp↔HTTP. O cérebro é o gateway Python (`hermes gateway run`). Sem o gateway rodando, mensagens entram na fila do bridge (`queueLength` sobe), mas NINGUÉM responde. Erro real: bridge conectado, gateway desligado, usuário mandou mensagem e recebeu silêncio. SEMPRE subir o gateway como parte do wizard — Phase 4.5 não é opcional."
  - "GATEWAY EXIGE HERMES_HOME APONTADO PARA O PERFIL: o gateway Python resolve o path de creds e config via env var `HERMES_HOME`. Sem ela definida, o gateway procura em `~/.hermes/` (modelo antigo, sem profiles) e aborta com `no creds.json at <HERMES_HOME>/platforms/whatsapp/session/`. ANTES de subir o gateway, exportar `HERMES_HOME=/home/<user>/.hermes/profiles/<CLIENT_ID>` (mais o `VIRTUAL_ENV` e PATH do venv)."
  - "GATEWAY PROCURA CREDS EM PATH DIFERENTE DO BRIDGE: o bridge usa `--session <SESSION_DIR>` arbitrário, mas o gateway espera `$HERMES_HOME/platforms/whatsapp/session/creds.json`. Para reconciliar sem mover arquivos, criar symlink: `mkdir -p <HERMES_HOME>/platforms/whatsapp && ln -sfn <SESSION_DIR> <HERMES_HOME>/platforms/whatsapp/session`. Validar com `ls -la <HERMES_HOME>/platforms/whatsapp/session/creds.json` antes de subir o gateway."
  - "HOME_NUMBER DO USUÁRIO NÃO É FONTE DA VERDADE: o admin pode informar um número na Phase 1 e escanear o QR com OUTRO. SEMPRE validar pós-scan lendo `session/creds.json` → `me.id` (phone) e `me.lid`. Se divergir do HOME_NUMBER informado, PARAR e perguntar antes de gravar no .env. Inferir de backups `.env` antigos é armadilha clássica (caso <CLIENT_ID>: backup tinha <NUMERO_ALT_EXEMPLO>, usuário escaneou com <NUMERO_HOME_EXEMPLO> — só descoberto pós-scan)."
  - "QR RENEVA A CADA ~60s SE NINGUÉM ESCANEAR: o Baileys rotaciona o QR continuamente até alguém autenticar. Se o usuário demora a escanear, o `/tmp/qr.png` ou PNG no perfil fica stale. Solução: regenerar PNG a partir de `/tmp/qr.txt` toda vez que o usuário pedir."
  - "PROVIDER DE IA EXIGE DOIS PASSOS: (a) `config.yaml` do perfil precisa ter `provider:` e `model:` válidos — fácil via symlink `profiles/<CLIENT_ID>/config.yaml -> ~/.hermes/config.yaml`. (b) Chave de API (ex: `OLLAMA_API_KEY`) precisa estar no `.env` do PERFIL porque gateway lê de `$HERMES_HOME/.env`, não do global. Sem o passo (b), gateway sobe sem erro mas responde 'No inference provider configured'."
  - "QR PNG: gerar via patch temporário no bridge.js (writeFileSync('/tmp/qr.txt', qr) dentro do if(qr){}) e REVERTER após pareamento. O bridge usa qrcode-terminal que só imprime ASCII, sem PNG nativo."
  - "Não usar `systemctl --user start hermes-gateway.service` para perfis multi-tenant: o unit assume `HERMES_HOME=~/.hermes` (modelo antigo) e vai falhar. Cada perfil tem seu gateway manual."
  - "BRIDGE_PORT NO GATEWAY: o gateway lê a porta do bridge nesta ordem de precedência: (1) env var BRIDGE_PORT do .env do perfil — lido automaticamente quando o gateway é iniciado com 'source .env'. (2) chave 'bridge_port' em gateway.platforms.whatsapp.extra do config.yaml. (3) default 3000. NUNCA é necessário copiar config.yaml por causa da porta — manter sempre como symlink global e garantir BRIDGE_PORT no .env do perfil. Patch aplicado em gateway/platforms/whatsapp.py."
---

# Instance Number — Provisionamento Multi-Agentes

**Classe de tarefa**: Criar e isolar um número de celular real como uma nova instância WhatsApp (Perfil/Cliente) do Hermes Agent, garantindo que não haja colisão de portas ou de arquivos de sessão com outros clientes rodando no mesmo container.

## Phase 0 — Pré-requisitos (rodar ANTES do wizard)

Antes de provisionar, validar que o ambiente está OK. Se algum desses falhar, **parar e investigar**:

```bash
# 1. Node.js disponível?
node --version   # esperado: v18+

# 2. Bridge.js existe?
ls -la ~/.hermes/hermes-agent/scripts/whatsapp-bridge/bridge.js

# 3. Venv do Hermes existe?
ls -la ~/.hermes/hermes-agent/venv/bin/hermes

# 4. ~/.hermes/ acessível (não está em disco cheio)?
df -h ~/.hermes

# 5. Pelo menos N portas livres (N = perfis já existentes + 2: bridge+gateway)
for port in $(seq 3000 5 3010) $(seq 8800 5 8810); do
  lsof -i :$port 2>/dev/null && echo "$port OCUPADA" || echo "$port livre"
done

# 6. Profiles existentes (pra saber a próxima porta)
ls ~/.hermes/profiles/ 2>/dev/null

# 7. config.yaml global tem provider válido?
grep -E "^  provider:" ~/.hermes/config.yaml

# 8. .env global tem pelo menos uma chave de API?
grep -E "^(OLLAMA_API_KEY|OPENROUTER_API_KEY|OPENAI_API_KEY)=" ~/.hermes/.env
```

Se tudo OK, seguir pra Phase 1.

## Phase 1 — Coleta de Dados e Isolamento (Wizard)

**REGRA: nada de valores fixos.** Todos os identificadores abaixo mudam por perfil/ambiente
e são informados pelo **operador** no momento da criação. NUNCA assuma um número, LID ou ID
de um perfil anterior. Pergunte explicitamente e confirme antes de gravar.

Solicite ao operador:
1. **Nome/ID do Cliente** (`<CLIENT_ID>`, ex: `cliente_alpha`)
2. **Número a ser conectado** (o WhatsApp que será pareado via QR para ESTE bot)
3. **Número Home / futuro admin do perfil** (`HOME_NUMBER` — o dono que poderá editar
   `produto.md`; pode ser igual ou diferente do número conectado)
4. **Porta do Bridge** (porta livre no container, ex: `3001`. Valide com `lsof -i :<PORTA>`)
5. **LID do Root admin para slash commands** (`<ROOT_ADMIN_LID>`) — quem poderá rodar
   comandos administrativos no WhatsApp. É um valor do **operador/deploy**, não do cliente;
   se o `config.yaml` global já tiver `allow_admin_from` preenchido, confirme se continua
   válido em vez de assumir. Se não souber, pergunte ao operador (ou derive do `creds.json`
   do próprio operador). **Nunca chumbe um LID de outro perfil.**

Lembre que o número informado pode divergir do que for de fato escaneado — **sempre valide
pós-scan** lendo `session/creds.json` (Phase 3e) antes de gravar qualquer número no `.env`.

Após coletar os dados, crie a estrutura de diretórios isolada:

```bash
# Criar diretórios do perfil e de sessão do Baileys
mkdir -p ~/.hermes/profiles/<CLIENT_ID>/session ~/.hermes/profiles/<CLIENT_ID>/logs

# Criar o arquivo de contexto de negócios vazio (template base)
# Use write_file ou o template em templates/produto.md.template
```

## Phase 2 — Configuração do Ambiente (.env Isolado)

Crie o arquivo de ambiente exclusivo do cliente. Isso garante o tratamento correto de grupos, DMs e da armadilha do `@lid`.

```bash
cat <<EOF > ~/.hermes/profiles/<CLIENT_ID>/.env
PROFILE_ID=<CLIENT_ID>
BRIDGE_PORT=<PORTA>
GATEWAY_PORT=<PORTA_GATEWAY>
HOME_NUMBER=<NUMERO_HOME_FORNECIDO>
SESSION_DIR=/home/<USER>/.hermes/profiles/<CLIENT_ID>/session
BRIDGE_LOG=/home/<USER>/.hermes/profiles/<CLIENT_ID>/logs/bridge.log
GATEWAY_LOG=/home/<USER>/.hermes/profiles/<CLIENT_ID>/logs/gateway.log
WHATSAPP_ENABLED=true
WHATSAPP_MODE=bot
WHATSAPP_ALLOWED_USERS=*
WHATSAPP_DM_POLICY=open
WHATSAPP_GROUP_POLICY=open
# Em GRUPOS, responder só quando o bot for @mencionado (ou reply ao bot / comando /).
# DMs SEMPRE respondem — esta flag não as afeta. Default seguro para perfis em grupos.
WHATSAPP_REQUIRE_MENTION=true
EOF
chmod 600 ~/.hermes/profiles/<CLIENT_ID>/.env
```

> **Resposta em grupo (Phase 4.4d).** `WHATSAPP_REQUIRE_MENTION` é lido pelo core em
> `gateway/platforms/whatsapp.py::_should_process_message`. Com `true`, mensagens de
> grupo só são processadas quando: mencionam o bot (`mentionedJid`), são reply a uma
> mensagem do bot, começam com `/`, ou o chat está em `WHATSAPP_FREE_RESPONSE_CHATS`.
> DMs nunca são filtradas. **Não** definir `require_mention` no `config.yaml` global
> (afetaria todos os perfis) — o controle é por perfil via esta env var. É só
> configuração; nenhum patch de core é necessário (já implementado, espelha o Telegram).
> Em grupo, cada participante tem **sessão própria** (`group_sessions_per_user`), então o
> isolamento entre contatos (Phase 4.4c) também se aplica dentro do grupo.

## Phase 3 — Iniciar Bridge e Capturar QR (Primeira Execução)

A primeira execução exige TTY interativo para exibir o QR Code no terminal.

**3a. Patch temporário no bridge.js** (para gerar PNG do QR):

```bash
# Aplica patch que persiste a string do QR em /tmp/qr.txt
# (sem isso, o bridge só imprime ASCII no stdout)
python3 << 'PYEOF'
import re
path = '/home/<USER>/.hermes/hermes-agent/scripts/whatsapp-bridge/bridge.js'
with open(path) as f: content = f.read()
patched = content.replace(
    "console.log('\\nWaiting for scan...\\n');\n    }",
    "console.log('\\nWaiting for scan...\\n');\n      try { writeFileSync('/tmp/qr.txt', qr); } catch (e) {}\n    }",
    1
)
if patched == content:
    raise SystemExit("Patch não casou — bridge.js pode ter mudado")
with open(path, 'w') as f: f.write(patched)
print("Patch aplicado")
PYEOF
```

**3b. Subir bridge em background:**

```bash
# Garantir que a porta está livre
lsof -t -i :<PORTA> | xargs -r kill -9
sleep 2

# Subir bridge carregando o .env do perfil
set -a; source ~/.hermes/profiles/<CLIENT_ID>/.env; set +a
cd /home/<USER>/.hermes/hermes-agent/scripts/whatsapp-bridge
# Usar terminal(background=true, notify_on_complete=false)
nohup node bridge.js --port "$BRIDGE_PORT" --session "$SESSION_DIR" --mode "$WHATSAPP_MODE" > "$BRIDGE_LOG" 2>&1 &
echo $! > ~/.hermes/profiles/<CLIENT_ID>/bridge.pid
```

**3c. Aguardar QR e gerar PNG:**

```bash
# Esperar QR aparecer (loop com timeout)
for i in $(seq 1 15); do
  [ -s /tmp/qr.txt ] && break
  sleep 1
done

# Gerar PNG
python3 -c "
import qrcode
img = qrcode.make(open('/tmp/qr.txt').read().strip())
img.save('/tmp/qr.png')
img.save('/home/<USER>/.hermes/profiles/<CLIENT_ID>/qr/qr-connect.png')
"
```

**3d. Apresentar QR para o usuário** (em DOIS formatos — PNG path + ASCII colado).

**3e. Validar creds.json pós-scan (NÃO PULAR):**

```bash
# Ler creds.json real e comparar com o que o admin disse
python3 << PYEOF
import json
with open('$HOME/.hermes/profiles/<CLIENT_ID>/session/creds.json') as f:
    creds = json.load(f)
me = creds.get('me', {})
print(f"phone: {me.get('id')}")
print(f"lid:   {me.get('lid')}")
print(f"name:  {me.get('name')}")
PYEOF
```

Se o `phone` (sem o sufixo `:17@s.whatsapp.net`) for DIFERENTE do HOME_NUMBER que o admin disse na Phase 1, **PARAR e perguntar** qual é o correto antes de gravar no .env.

**3f. Configurar WHATSAPP_HOME_CHANNEL para não vazar onboarding para clientes:**

O gateway dispara o aviso `📬 No home channel is set for Whatsapp... Type /sethome...` em toda primeira conversa quando `WHATSAPP_HOME_CHANNEL` está ausente. Isso é péssimo para UX de cliente final. Não dependa de o cliente mandar `/sethome` em modo `WHATSAPP_MODE=bot`, porque mensagens `fromMe` do próprio número conectado são ignoradas pelo bridge para evitar eco/loop.

Depois do QR, derive o chat_id real do número conectado a partir de `creds.json`:

```bash
PROFILE="$HOME/.hermes/profiles/<CLIENT_ID>"
HOME_LID=$(python3 <<'PY'
import json, pathlib, re, os
profile = pathlib.Path(os.environ['PROFILE'])
creds = json.loads((profile / 'session' / 'creds.json').read_text())
me = creds.get('me') or {}
lid = me.get('lid') or ''
phone = me.get('id') or ''
if lid:
    print(re.sub(r':.*@', '@', lid))
elif phone:
    print(re.sub(r':.*@', '@', phone))
PY
)
[ -n "$HOME_LID" ] || { echo "ERRO: não consegui derivar WHATSAPP_HOME_CHANNEL"; exit 1; }

# Editar .env do perfil via shell; não usar write_file no .env protegido.
if grep -q '^WHATSAPP_HOME_CHANNEL=' "$PROFILE/.env"; then
  sed -i "s|^WHATSAPP_HOME_CHANNEL=.*|WHATSAPP_HOME_CHANNEL=$HOME_LID|" "$PROFILE/.env"
else
  printf '\nWHATSAPP_HOME_CHANNEL=%s\n' "$HOME_LID" >> "$PROFILE/.env"
fi
if grep -q '^WHATSAPP_HOME_CHANNEL_NAME=' "$PROFILE/.env"; then
  sed -i "s|^WHATSAPP_HOME_CHANNEL_NAME=.*|WHATSAPP_HOME_CHANNEL_NAME=<CLIENT_ID>|" "$PROFILE/.env"
else
  printf 'WHATSAPP_HOME_CHANNEL_NAME=%s\n' "<CLIENT_ID>" >> "$PROFILE/.env"
fi
# Thread/topic não se aplica a WhatsApp DM; manter vazio se existir.
if grep -q '^WHATSAPP_HOME_CHANNEL_THREAD_ID=' "$PROFILE/.env"; then
  sed -i 's|^WHATSAPP_HOME_CHANNEL_THREAD_ID=.*|WHATSAPP_HOME_CHANNEL_THREAD_ID=|' "$PROFILE/.env"
else
  printf 'WHATSAPP_HOME_CHANNEL_THREAD_ID=\n' >> "$PROFILE/.env"
fi
```

Isso não transforma o próprio número em um bom canal de teste: em `bot`, self-chat continua ignorado. Serve para satisfazer a configuração home e suprimir o aviso. Para QA fim-a-fim, use outro número mandando mensagem ao bot.

**3g. Reverter patch do bridge.js:**

```bash
python3 << 'PYEOF'
path = '/home/<USER>/.hermes/hermes-agent/scripts/whatsapp-bridge/bridge.js'
with open(path) as f: content = f.read()
reverted = content.replace(
    "console.log('\\nWaiting for scan...\\n');\n      try { writeFileSync('/tmp/qr.txt', qr); } catch (e) {}\n    }",
    "console.log('\\nWaiting for scan...\\n');\n    }",
    1
)
if reverted == content:
    raise SystemExit("Revert não casou — bridge.js foi editado manualmente")
with open(path, 'w') as f: f.write(reverted)
print("Patch revertido")
PYEOF
```

## Phase 4 — Subir Gateway Python (NÃO PULAR)

O Bridge Node.js é SÓ transporte. O cérebro é o Gateway Python. Sem ele, mensagens entram na fila do bridge (`queueLength > 0`) e ninguém responde.

```bash
# 1. Criar symlink: gateway procura creds em $HERMES_HOME/platforms/whatsapp/session,
#    mas o bridge salva em ~/.hermes/profiles/<CLIENT_ID>/session. Symlink reconcilia.
export HERMES_HOME=/home/<USER>/.hermes/profiles/<CLIENT_ID>
mkdir -p "$HERMES_HOME/platforms/whatsapp"
ln -sfn "$SESSION_DIR" "$HERMES_HOME/platforms/whatsapp/session"

# Validar antes de subir
ls -la "$HERMES_HOME/platforms/whatsapp/session/creds.json" || echo "ERRO: symlink quebrado"

# 2. Carregar env do perfil e do venv
set -a
source ~/.hermes/profiles/<CLIENT_ID>/.env
set +a
export HERMES_HOME=/home/<USER>/.hermes/profiles/<CLIENT_ID>
export VIRTUAL_ENV=/home/<USER>/.hermes/hermes-agent/venv
export PATH="$VIRTUAL_ENV/bin:$PATH"

# 3. Subir gateway em background
# Usar terminal(background=true, notify_on_complete=false)
nohup hermes gateway run --replace \
  > ~/.hermes/profiles/<CLIENT_ID>/logs/gateway.log 2>&1 &
echo $! > ~/.hermes/profiles/<CLIENT_ID>/gateway.pid
```

## Phase 4.4 — Configurar Slash Commands Admin-Only

Antes de expor o perfil para clientes, garantir que comandos de configuração do Hermes no WhatsApp fiquem restritos ao Root admin. Como os perfis usam `config.yaml` como symlink do global, essa política deve existir em `~/.hermes/config.yaml`:

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

Sem `allow_admin_from`, o Hermes fica em modo compatível antigo e usuários permitidos podem executar todos os slash commands. Com `user_allowed_commands: []`, clientes comuns não executam comandos de configuração como `/restart`, `/sethome`, `/model`, `/tools`, `/skills`, `/cron`, etc. Neste ambiente, `gateway/slash_access.py` também foi patchado para manter apenas `/whoami` em `_ALWAYS_ALLOWED_FOR_USERS`; portanto `/help` também fica bloqueado para clientes comuns e liberado só para admin.

## Phase 4.4b — Silenciar Progresso de Ferramentas no WhatsApp

Nunca deixar previews internos de ferramentas aparecerem para cliente final no WhatsApp, exemplos proibidos: `send_message: "to whatsapp..."`, `vision_analyze: "..."`, `skill_view: ...`. Isso é apresentação do gateway (`display.tool_progress`), não deve depender só de prompt/SOUL.

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

Além da configuração, o `SOUL.md` do perfil deve conter guardrail de sigilo: usar ferramentas silenciosamente e nunca mencionar nomes de ferramentas, chamadas, argumentos, previews ou logs operacionais ao usuário final.

Após alterar `config.yaml`, reiniciar os gateways afetados por PID do perfil; não precisa reiniciar o bridge se ele estiver saudável.

## Phase 4.4b2 — Desabilitar geração de imagem (baseline)

Bots de triagem/suporte não devem gerar imagens. O modelo às vezes dispara
`image_generate` indevidamente (ex.: numa mensagem sobre "cor favorita"), e uma chamada
malformada pode ainda travar a virada com stale de API. Bloqueio duro em
`~/.hermes/config.yaml` (global, symlinkado — vale para todos os perfis):

```yaml
agent:
  disabled_toolsets: [image_gen]
```

`disabled_toolsets` é aplicado por último na resolução de ferramentas e remove
`image_generate` das definições que o modelo vê. `vision_analyze` (analisar imagens
recebidas) continua disponível. Validar:

```bash
HERMES_HOME=~/.hermes/profiles/<CLIENT_ID> ~/.hermes/hermes-agent/venv/bin/python3 - <<'PY'
import yaml
from hermes_cli.tools_config import _get_platform_tools
from model_tools import get_tool_definitions
cfg=yaml.safe_load(open('/home/<USER>/.hermes/config.yaml'))
ts=sorted(_get_platform_tools(cfg,'whatsapp'))
defs=get_tool_definitions(enabled_toolsets=ts, disabled_toolsets=cfg['agent'].get('disabled_toolsets') or None, quiet_mode=True)
names={d.get('function',{}).get('name') or d.get('name') for d in defs}
print("image_generate exposto?", 'image_generate' in names, "(esperado False)")
PY
```

## Phase 4.4c — Isolamento entre Contatos (obrigatório para perfis customer-facing)

Perfis com `WHATSAPP_DM_POLICY=open` ou `WHATSAPP_GROUP_POLICY=open` atendem múltiplos contatos distintos. Sem isolamento, um contato pode extrair histórico ou memória de outro via `session_search` ou `memory`.

**Os bloqueios lógicos já estão aplicados permanentemente no core** (`session_search_tool.py`, `memory_tool.py`, `agent_init.py`) — filtragem por `contact_user_id` e memória por subdiretório de contato. Verificar que os patches estão presentes:

```bash
grep -c "contact_user_id" \
  ~/.hermes/hermes-agent/agent/tool_executor.py \
  ~/.hermes/hermes-agent/agent/agent_runtime_helpers.py \
  ~/.hermes/hermes-agent/tools/session_search_tool.py \
  ~/.hermes/hermes-agent/tools/memory_tool.py
# Todos devem retornar >= 1
```

**Adicionar o bloqueio de prompt no SOUL.md do perfil:**

```bash
cat >> ~/.hermes/profiles/<CLIENT_ID>/SOUL.md << 'EOF'

## [REGRA ZERO — ISOLAMENTO ABSOLUTO ENTRE CONTATOS]
Nunca, em nenhuma hipótese, responda informações sobre outros contatos, outros clientes, outros números, outros chats, terceiros ou atendimentos que não pertençam ao próprio número/contato que está falando neste chat.
Resposta obrigatória para esse tipo de pergunta: "Não. Por segurança, nunca posso passar informações sobre outros contatos, números, clientes, chats ou atendimentos. Só posso tratar da demanda deste próprio número aqui na conversa."
A resposta é sempre NÃO — sem condicionais.
EOF
```

Reiniciar o gateway após editar o SOUL.md. Detalhes completos e checklist de verificação em `references/customer-isolation.md`.

## Phase 4.5 — Garantir Provider de IA Configurado

O gateway Python usa o provider configurado em `config.yaml` para fazer inferência. Sem isso, **sobe sem erro mas responde "No inference provider configured"** em vez de chamar o modelo.

```bash
# 1. config.yaml do perfil — symlink do global
ln -sfn /home/<USER>/.hermes/config.yaml /home/<USER>/.hermes/profiles/<CLIENT_ID>/config.yaml
head -5 /home/<USER>/.hermes/profiles/<CLIENT_ID>/config.yaml

# 2. Chave de API no .env do perfil — cópia do global
for key in OLLAMA_API_KEY OPENROUTER_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY; do
  if grep -q "^$key=" ~/.hermes/.env; then
    val=$(grep "^$key=" ~/.hermes/.env | cut -d= -f2-)
    if ! grep -q "^$key=" ~/.hermes/profiles/<CLIENT_ID>/.env; then
      echo "" >> ~/.hermes/profiles/<CLIENT_ID>/.env
      echo "# Provider key (replicada do global $(date +%Y-%m-%d))" >> ~/.hermes/profiles/<CLIENT_ID>/.env
      echo "$key=$val" >> ~/.hermes/profiles/<CLIENT_ID>/.env
      echo "[provider] $key adicionada"
    fi
  fi
done

# 3. Reiniciar gateway pra ele reler
kill -TERM $(cat ~/.hermes/profiles/<CLIENT_ID>/gateway.pid) 2>/dev/null
sleep 3
[ -f ~/.hermes/profiles/<CLIENT_ID>/gateway.pid ] && kill -9 $(cat ~/.hermes/profiles/<CLIENT_ID>/gateway.pid) 2>/dev/null

set -a; source ~/.hermes/profiles/<CLIENT_ID>/.env; set +a
export HERMES_HOME=/home/<USER>/.hermes/profiles/<CLIENT_ID>
export VIRTUAL_ENV=/home/<USER>/.hermes/hermes-agent/venv
export PATH="$VIRTUAL_ENV/bin:$PATH"
nohup hermes gateway run --replace \
  > ~/.hermes/profiles/<CLIENT_ID>/logs/gateway.log 2>&1 &
echo $! > ~/.hermes/profiles/<CLIENT_ID>/gateway.pid
sleep 5

# 4. Validar: NÃO deve aparecer "No inference provider configured"
! grep -q "No inference provider configured" ~/.hermes/profiles/<CLIENT_ID>/logs/gateway.log \
  && echo "OK: provider configurado" || echo "FALHA: provider ainda ausente"
```

## Phase 4.6 — Baseline de configuração (checklist verificável)

Resumo do que TODO perfil customer-facing deve ter ao final. Rode para confirmar que
nada foi pulado:

```bash
PROFILE=~/.hermes/profiles/<CLIENT_ID>
echo "== .env do perfil =="
grep -E '^(WHATSAPP_ALLOWED_USERS|WHATSAPP_DM_POLICY|WHATSAPP_GROUP_POLICY|WHATSAPP_REQUIRE_MENTION)=' "$PROFILE/.env"
# Esperado: ALLOWED_USERS=*, DM/GROUP_POLICY=open, REQUIRE_MENTION=true (grupo só responde @mencionado; DM sempre)

echo "== config.yaml global (symlinkado) =="
grep -E '^  disabled_toolsets:' ~/.hermes/config.yaml          # deve conter image_gen
python3 -c "import yaml;c=yaml.safe_load(open('$HOME/.hermes/config.yaml'));e=(c.get('gateway') or {}).get('platforms',{}).get('whatsapp',{}).get('extra',{});print('allow_admin_from:', e.get('allow_admin_from')); print('user_allowed_commands:', e.get('user_allowed_commands'))"

echo "== isolamento entre contatos (patches no core) =="
grep -lc contact_user_id ~/.hermes/hermes-agent/tools/session_search_tool.py ~/.hermes/hermes-agent/tools/memory_tool.py >/dev/null && echo "isolamento presente"

echo "== SOUL.md tem REGRA ZERO de isolamento =="
grep -q "ISOLAMENTO ABSOLUTO ENTRE CONTATOS" "$PROFILE/SOUL.md" && echo OK || echo "FALTA REGRA ZERO"

echo "== config.yaml é symlink do global? =="
[ -L "$PROFILE/config.yaml" ] && echo "symlink OK" || echo "ATENCAO: config.yaml não é symlink"
```

Baseline esperado (todas as regras recentes):

| Item | Onde | Valor/efeito |
|------|------|--------------|
| Responder em grupo só com @menção | `.env` do perfil | `WHATSAPP_REQUIRE_MENTION=true` (Phase 4.4b2/4.4d) |
| Sem geração de imagem | `config.yaml` global | `agent.disabled_toolsets: [image_gen]` (Phase 4.4b2) |
| Isolamento entre contatos (SQL + memória + SOUL) | core + `SOUL.md` | filtro por `user_id`, `memories/contacts/<id>/`, REGRA ZERO (Phase 4.4c) |
| Slash admin-only | `config.yaml` global | `allow_admin_from` + `*_allowed_commands: []` (Phase 4.4) |
| Tool progress silenciado | `config.yaml` global | `display.platforms.whatsapp.tool_progress: off` (Phase 4.4b) |
| `config.yaml` por symlink | perfil | aponta para `~/.hermes/config.yaml` (Phase 4.5) |

## Phase 5 — Padrão de Encerramento do Wizard (gateway ligado)

Ao final de TODO `create-profile`, o estado padrão obrigatório é: **bridge conectado + gateway rodando**. Não encerrar o wizard deixando só o bridge ativo.

Checklist obrigatório antes de declarar concluído:

```bash
PROFILE=~/.hermes/profiles/<CLIENT_ID>
PORT=$(grep -oP '^BRIDGE_PORT=\K.*' "$PROFILE/.env")

# Se existir lock real de gateway, corrigir gateway.pid para o PID ativo
if [ -f "$PROFILE/gateway.lock" ]; then
  LOCK_PID=$(python3 - <<PY
import json, pathlib
p=pathlib.Path("$PROFILE/gateway.lock").expanduser()
try: print(json.loads(p.read_text()).get("pid", ""))
except Exception: print("")
PY
)
  if [ -n "$LOCK_PID" ] && ps -p "$LOCK_PID" >/dev/null 2>&1; then
    echo "$LOCK_PID" > "$PROFILE/gateway.pid"
  fi
fi

# Se gateway ainda não estiver vivo, subir agora com HERMES_HOME do perfil
if ! [ -f "$PROFILE/gateway.pid" ] || ! ps -p $(cat "$PROFILE/gateway.pid" 2>/dev/null) >/dev/null 2>&1; then
  set -a; source "$PROFILE/.env"; set +a
  export HERMES_HOME="$PROFILE"
  export VIRTUAL_ENV=~/.hermes/hermes-agent/venv
  export PATH="$VIRTUAL_ENV/bin:$PATH"
  # Rodar em background via ferramenta terminal(background=true), sem pkill global.
  hermes gateway run --replace >> "$PROFILE/logs/gateway.log" 2>&1
fi
```

Se aparecer `Gateway runtime lock is already held by another instance`, NÃO matar por nome. Validar o PID dentro de `gateway.lock`; se estiver vivo e com `HERMES_HOME` do perfil correto, apenas corrigir `gateway.pid`.

## Phase 6 — Verificação de Saúde End-to-End

**Não basta o bridge estar conectado. O gateway TEM que estar drenando a fila e respondendo.**

```bash
# 1. Bridge respondendo na porta designada?
curl -s http://localhost:<PORTA>/health

# 2. Gateway Python rodando?
tail -20 ~/.hermes/profiles/<CLIENT_ID>/logs/gateway.log | grep -E "✓ whatsapp connected|Cron ticker"

# 3. Os DOIS processos estão simultaneamente ativos?
ps aux | grep -E "bridge.js.*--port <PORTA>|hermes.*gateway run" | grep -v grep | wc -l
# Esperado: 2 (bridge + gateway)

# 4. queueLength deve estar em 0 (sinal de que o gateway está drenando)
curl -s http://localhost:<PORTA>/health | grep -oE '"queueLength":[0-9]+'

# 5. **Teste fim-a-fim real** (NÃO PULAR): peça ao admin para mandar uma
#    mensagem de WhatsApp pro número do bot. Verifique no log:
grep -E "inbound message|response ready|Sending response" ~/.hermes/profiles/<CLIENT_ID>/logs/gateway.log | tail -5
# Sequência esperada: inbound message → response ready → Sending response
# Se mostrar "api_calls=0" → provider não configurado (voltar pra Phase 4.5)
# Se mostrar "Unauthorized user: <id>@lid" → ver messaging-bridge-troubleshooting
```

**Sintomas clássicos de falha neste fluxo:**

| Sintoma | Causa | Fix |
|---|---|---|
| Bridge connected, gateway morto | Phase 4 não rodada | Subir gateway manualmente |
| Gateway `no creds.json at <HERMES_HOME>/platforms/whatsapp/session/` | HERMES_HOME errado ou symlink ausente | Recriar symlink |
| Gateway `Unauthorized user: <id>@lid` | WHATSAPP_ALLOWED_USERS muito restritivo | Setar `*` no .env do perfil |
| `bridge queueLength` sobe sem cair | Gateway não drena fila (caiu/zumbi) | Reiniciar gateway |
| Inbound message aparece mas nenhuma response ready | Provedor de inferência não configurado | Phase 4.5: config.yaml symlink + chave no .env do perfil |

## Procedimentos de Manutenção e Diagnóstico Multi-Tenant

### Reiniciar Bridge de um Cliente Específico

```bash
# Matar APENAS o processo desta porta específica
lsof -t -i :<PORTA> | xargs -r kill -9
sleep 2

# Relançar
set -a; source ~/.hermes/profiles/<CLIENT_ID>/.env; set +a
cd /home/<USER>/.hermes/hermes-agent/scripts/whatsapp-bridge
nohup node bridge.js --port "$BRIDGE_PORT" --session "$SESSION_DIR" --mode "$WHATSAPP_MODE" \
  > ~/.hermes/profiles/<CLIENT_ID>/logs/bridge.log 2>&1 &
echo $! > ~/.hermes/profiles/<CLIENT_ID>/bridge.pid
```

### Desconectar um Número (Logout)

```bash
# Deletar credenciais exclusivas do cliente (força novo QR)
rm ~/.hermes/profiles/<CLIENT_ID>/session/creds.json
# Reiniciar o passo da Phase 3 (Foreground) para novo QR Code
```

## Arquivos de Estado do Perfil

Todos os arquivos restritos à pasta `~/.hermes/profiles/<CLIENT_ID>/`:

- `.env` — WHATSAPP_* vars, HOME_NUMBER (metadado), cópias de chaves de API, paths
- `config.yaml` — SYMLINK para `~/.hermes/config.yaml` (provider global)
- `produto.md` — Contexto de negócio exclusivo e editável pelo Número Home
- `session/creds.json` — Credenciais Baileys
- `session/lid-mapping-*` — Mapeamentos de identidade do WhatsApp Business
- `platforms/whatsapp/session → ../../session` — Symlink para o gateway achar creds
- `logs/bridge.log`, `logs/gateway.log` — Logs operacionais isolados
- `bridge.pid`, `gateway.pid` — PIDs dos processos para kills seguros

## Referências adicionais

- **`references/gateway-multi-profile-errors.md`** — erros reais vividos no provisionamento multi-tenant (gateway faltando, HERMES_HOME ausente, HOME_NUMBER divergente, QR stale, provider sem config, HOME_NUMBER como env var inexistente). Use quando o usuário reportar "mandei mensagem e nada acontece" ou qualquer falha pós-provisionamento.
- **`references/provider-key-resync.md`** — receita standalone de re-sync de chaves em massa (todos os perfis) quando o admin rotaciona `OLLAMA_API_KEY` ou similar no `~/.hermes/.env` global. Use via `edit-profile` Phase 6 para 1 perfil; este arquivo para todos de uma vez.
- **`references/whatsapp-home-channel-ux.md`** — detalhe do bug/UX em que falta de `WHATSAPP_HOME_CHANNEL` faz o gateway enviar o aviso `/sethome` para clientes novos; inclui regra de provisionamento para preencher o home channel automaticamente via LID/JID pós-scan.
- **`references/customer-isolation.md`** — documentação completa dos dois layers de isolamento entre contatos (prompt + lógica). Inclui descrição dos patches no core (`session_search_tool.py`, `memory_tool.py`, call sites), checklist de verificação, e diagnóstico de vazamento residual por skills customizadas.