---
name: edit-profile
summary: Editar as configurações e parâmetros de um Perfil Isolado (Cliente) existente no Hermes Agent, garantindo o alinhamento de variáveis. Inclui re-sync de chaves do root (Phase 6).
description: "Procedimento orquestrado para alterar dados de um perfil (como Porta, Número Home, Políticas ou Contexto). Classifica o escopo da mudança para parar/reiniciar somente os processos necessários: gateway-only quando possível, bridge + gateway quando a alteração afeta transporte/sessão/porta. Phase 6 cobre o caso especial de re-sync quando chaves mudam no ~/.hermes/.env global."
trigger: "O usuário (Root Admin) pede para alterar, editar, mudar a porta, trocar o administrador, atualizar o Número Home, modificar regras de um cliente existente, OU re-sincronizar chaves de API que mudaram no ~/.hermes/.env global."
pitfalls:
  - "Risco de dessincronização: Se alterar a PORTA do cliente, você DEVE alterar a variável PORT no arquivo .env E garantir que o processo inicie na nova porta. O mesmo vale para outras variáveis."
  - "EDITAR AFETA PROCESSOS CONFORME ESCOPO: variáveis lidas pelo bridge (porta, session dir, modo WhatsApp) exigem reiniciar bridge + gateway. Mudanças só de gateway (`SOUL.md`, `produto.md`, provider key, config.yaml, policy lida pelo gateway) normalmente exigem apenas gateway. Não declarar restart total sem necessidade; primeiro classificar o escopo."
  - "Edição com processo rodando: evite editar arquivos que o processo ativo possa ler/escrever durante a operação. Para `.env`/provider/SOUL/produto.md`, pare pelo menos o gateway do perfil; pare o bridge também quando a mudança afetar bridge."
  - "Risco de vazamento de escopo: Certifique-se absolutamente de estar editando o arquivo .env e os dados de ~/.hermes/profiles/<CLIENT_ID>/, e não de outro cliente."
  - "PROVIDER (chave no .env do perfil): se você mudar a chave de API no .env global E usou symlink de .env, todos os perfis atualizam. Se duplicou a chave no .env do perfil (caso padrão deste ambiente), só atualiza aquele perfil — rode Phase 6."
  - "PROVIDER (config.yaml): é symlink do global por padrão, então atualização no root é automática. NÃO mexer no config.yaml do perfil."
  - "RE-SYNC DO ROOT: chaves de API (OLLAMA_API_KEY, OPENROUTER_API_KEY, etc.) foram COPIADAS para o .env do perfil na criação (Phase 4.6 do create-profile). Se o admin trocar a chave no ~/.hermes/.env, ESTE perfil continua com a chave antiga até você rodar o re-sync (Phase 6 abaixo). Para re-sync em massa de todos os perfis, ver `root-soul.md` seção 'Re-sync rápido'."
  - "GROWLING SIDE EFFECT: usar `pkill -f 'hermes gateway run'` afeta TODOS os perfis. Em edit-profile, matar APENAS o gateway DESTE perfil via `kill -TERM $(cat profiles/<CLIENT_ID>/gateway.pid)`."
  - "Nem toda edição exige reiniciar bridge: mudanças só em `config.yaml`, provider key, SOUL/persona ou código do gateway normalmente exigem reiniciar apenas o gateway do perfil. Mudanças no `.env` que o bridge lê (porta, session dir, modo WhatsApp) exigem bridge + gateway. Declare o escopo antes de parar processos."
  - "SOUL.md NÃO deve ser tratado como hot-reload por mensagem: o conteúdo entra no system prompt e o AIAgent cacheia esse prompt durante a sessão. Para garantir persona nova no gateway, reiniciar só o gateway do perfil (bridge não precisa se foi apenas SOUL/persona)."
  - "Bridge manual precisa subir com o `.env` do perfil carregado. Se iniciar `node bridge.js --mode bot` sem `set -a; source <profile>/.env`, variáveis como `WHATSAPP_ALLOWED_USERS=*` podem faltar no processo e DMs ficam silenciosas/rejeitadas apesar do health mostrar connected."
  - "Depois dos aprendizados de WhatsApp customer-facing, toda edição relevante deve verificar três invariantes de exposição: `WHATSAPP_HOME_CHANNEL` presente, slash commands admin-only no config global, e `display.platforms.whatsapp.tool_progress: off` para não vazar tool calls."
  - "PIDFILE DO GATEWAY PODE SER JSON: versões recentes do Hermes escrevem `gateway.pid` como objeto JSON (`{\"pid\": ...}`), não número puro. Nunca usar `ps -p $(cat gateway.pid)` sem parse; extraia `.pid` com Python/jq ou use `hermes gateway status` com `HERMES_HOME=<profile>`."
---

# Edit Instance — Atualização de Perfil Multi-Agentes

## Modo objetivo (padrão)

Quando o pedido já trouxer `<CLIENT_ID>` e a mudança exata, NÃO fazer roteiro longo. Execute em blocos curtos e verificáveis:

1. Carregar `hermes-root-soul`, `edit-profile` e, se envolver Hermes config/provider/model, `hermes-agent`.
2. Classificar escopo em uma linha: `gateway-only` ou `bridge+gateway`.
3. Descobrir estado atual com `hermes config` / `gateway status` / PID do perfil.
4. Aplicar mudança com ferramenta oficial quando existir. Para modelo/provider use:
   `HERMES_HOME=<profile> hermes config set model.provider <provider>`
   `HERMES_HOME=<profile> hermes config set model.default <model>`
   `HERMES_HOME=<profile> hermes config set model.context_length <n>`
5. Reiniciar só o necessário. Para model/provider: gateway-only.
6. Verificar com `hermes config`, `hermes gateway status` e logs do perfil. Reportar somente: arquivo alterado, modelo/provider efetivo, PID/status, qualquer alerta.

Evite despejar Phase 1-6 na resposta. Use as fases abaixo só como referência operacional ou quando faltar escopo.

**Classe de tarefa**: Modificar com segurança os parâmetros de configuração de um cliente existente no módulo multi-tenant, garantindo consistência entre os arquivos e o processo em execução.

## Quando usar esta skill

| Cenário | Phase apropriada |
|---|---|
| Mudar porta do bridge do cliente | Phase 1-5 |
| Trocar HOME_NUMBER (metadado) | Phase 1-5 (Phase 3 com sed) |
| Mudar WHATSAPP_GROUP_POLICY, WHATSAPP_DM_POLICY, etc | Phase 1-5 |
| Atualizar `produto.md` (contexto de negócio) | Phase 1-5 (Phase 3 com write_file) |
| Atualizar `SOUL.md` / fluxo de atendimento / notificação interna para home channel | Phase 1, Phase 3 e referência `references/home-channel-escalation-notifications.md` |
| Proibir vazamento entre clientes/números em perfil WhatsApp customer-facing | Gateway-only: editar `SOUL.md`, reiniciar gateway e usar `references/customer-chat-isolation.md` |
| Em grupo, responder só quando @mencionado (ou parar de exigir menção) | Gateway-only: setar `WHATSAPP_REQUIRE_MENTION` no `.env` do perfil e reiniciar só o gateway (ver Phase 3) |
| **Admin rotacionou chave de API no ~/.hermes/.env** | **Phase 6 (re-sync)** |
| Admin mudou de provedor (Ollama → OpenRouter) | Phase 6 |
| Admin adicionou nova chave de provider | Phase 6 |

## Phase 1 — Identificação e Coleta da Alteração

Para editar um cliente, você (Hermes Root) deve primeiro confirmar:
1. **Nome/ID do Cliente** exato (`<CLIENT_ID>`).
2. **O que será alterado** (Ex: Nova Porta? Novo Número Home? Nova política de grupos?).
3. **Validação**: Se for uma troca de porta, verifique se a nova porta está livre usando `lsof -i :<NOVA_PORTA>`.

## Phase 2 — Congelamento (Parar os Processos Necessários)

Antes de alterar arquivos, declare o escopo da edição e pare só os processos necessários:

- Alterou porta, `SESSION_DIR`, modo WhatsApp ou qualquer variável consumida pelo bridge: parar gateway + bridge.
- Alterou `.env` consumido só pelo gateway, provider key, `SOUL.md`, `produto.md`, `config.yaml` ou código do gateway: parar/reiniciar só o gateway, salvo evidência de stale state no bridge.
- Operação destrutiva ou ambígua: preferir passos pequenos e verificáveis.

Quando precisar parar AMBOS os processos do cliente, use:

```bash
# 1. Matar gateway Python (SIGTERM primeiro, depois SIGKILL se necessário)
if [ -f ~/.hermes/profiles/<CLIENT_ID>/gateway.pid ]; then
  kill -TERM $(cat ~/.hermes/profiles/<CLIENT_ID>/gateway.pid) 2>/dev/null
  sleep 3
  kill -9 $(cat ~/.hermes/profiles/<CLIENT_ID>/gateway.pid) 2>/dev/null
fi

# 2. Matar bridge (sempre -9, Node.js não responde a SIGTERM bem)
PORTA_ATUAL=$(grep -oP '^BRIDGE_PORT=\K.*' ~/.hermes/profiles/<CLIENT_ID>/.env)
lsof -t -i :$PORTA_ATUAL | xargs -r kill -9

# OU, por segurança, matar usando o PID salvo do bridge
if [ -f ~/.hermes/profiles/<CLIENT_ID>/bridge.pid ]; then
  kill -9 $(cat ~/.hermes/profiles/<CLIENT_ID>/bridge.pid) 2>/dev/null
fi
sleep 2

# 3. Confirmar
ps aux | grep -E "bridge.js.*$PORTA_ATUAL|hermes gateway run" | grep -v grep && echo "AINDA VIVO" || echo "AMBOS MORTOS"
```

## Phase 3 — Sincronização de Arquivos (Edição)

Agora, aplique as edições nos arquivos necessários. **Atenção à regra de sincronização:** se uma informação existe em mais de um lugar, atualize todos.

```bash
# Se for alterar a Porta:
sed -i 's/^BRIDGE_PORT=.*/BRIDGE_PORT=<NOVA_PORTA>/' ~/.hermes/profiles/<CLIENT_ID>/.env

# Se for alterar o Número Home (Administrador do Bot, metadado):
sed -i 's/^HOME_NUMBER=.*/HOME_NUMBER=<NOVO_NUMERO_HOME>/' ~/.hermes/profiles/<CLIENT_ID>/.env

# Se for alterar a política de grupos:
sed -i 's/^WHATSAPP_GROUP_POLICY=.*/WHATSAPP_GROUP_POLICY=<NOVA_POLITICA>/' ~/.hermes/profiles/<CLIENT_ID>/.env

# Em grupo, responder só quando @mencionado (gateway-only). true=exige menção, false=responde tudo.
# DMs nunca são afetadas. Idempotente (adiciona se ausente, atualiza se existir):
ENV=~/.hermes/profiles/<CLIENT_ID>/.env
grep -q '^WHATSAPP_REQUIRE_MENTION=' "$ENV" \
  && sed -i 's/^WHATSAPP_REQUIRE_MENTION=.*/WHATSAPP_REQUIRE_MENTION=true/' "$ENV" \
  || printf '\nWHATSAPP_REQUIRE_MENTION=true\n' >> "$ENV"
```

Para alterações em `produto.md`, use `write_file` (não sed — é markdown com estrutura livre).

Para alterações de comportamento/persona do agente, editar `SOUL.md` do perfil. Quando o pedido for notificar o dono/admin após coletar uma solicitação, use a receita em `references/home-channel-escalation-notifications.md`: instruir o agente a chamar `send_message(action="send", target="whatsapp", message="...")` depois da triagem, com `WHATSAPP_HOME_CHANNEL` já configurado. Faça em passos pequenos e verificáveis, especialmente se também houver edição de `.env` ou restart de gateway.

Quando o problema for vazamento entre clientes/números (o agente responde a um contato usando dados de outro), use `references/customer-chat-isolation.md`: adicionar regras explícitas de isolamento no `SOUL.md`, reiniciar somente o gateway, verificar que o gateway subiu depois da edição do SOUL, e se ainda houver vazamento tratar como possível histórico contaminado do contato exato via `reset-profile-history`.

## Phase 4 — Reinicialização (Gateway ou Bridge + Gateway)

Com os arquivos sincronizados, reinicie os processos que foram parados na Phase 2. Se a edição não afetou o bridge, relance apenas o gateway. Se afetou porta/session/mode, reinicie AMBOS.

```bash
# Se a edição afetou o bridge, reinicie o BRIDGE. Se foi gateway-only, pule este bloco.
# 1. Ler porta (pode ou não ter sido alterada) do .env atualizado
NOVA_PORTA=$(grep -oP '^BRIDGE_PORT=\K.*' ~/.hermes/profiles/<CLIENT_ID>/.env)

# 2. Reiniciar BRIDGE
# IMPORTANTE: carregar o .env do perfil antes do node, senão o processo pode
# subir sem WHATSAPP_ALLOWED_USERS/WHATSAPP_DM_POLICY e ficar conectado mas silencioso.
set -a
source ~/.hermes/profiles/<CLIENT_ID>/.env
set +a
nohup node ~/.hermes/hermes-agent/scripts/whatsapp-bridge/bridge.js \
  --port $NOVA_PORTA \
  --session ~/.hermes/profiles/<CLIENT_ID>/session \
  --mode ${WHATSAPP_MODE:-bot} \
  > ~/.hermes/profiles/<CLIENT_ID>/logs/bridge.log 2>&1 &
echo $! > ~/.hermes/profiles/<CLIENT_ID>/bridge.pid

# 3. Reiniciar GATEWAY (NÃO ESQUECER — caso contrário fica em estado parcial)
set -a
source ~/.hermes/profiles/<CLIENT_ID>/.env
set +a
export HERMES_HOME=/home/<USER>/.hermes/profiles/<CLIENT_ID>
export VIRTUAL_ENV=/home/<USER>/.hermes/hermes-agent/venv
export PATH="$VIRTUAL_ENV/bin:$PATH"
nohup hermes gateway run --replace \
  > ~/.hermes/profiles/<CLIENT_ID>/logs/gateway.log 2>&1 &
echo $! > ~/.hermes/profiles/<CLIENT_ID>/gateway.pid
```

## Phase 5 — Healthcheck Pós-Edição

Valide que os processos necessários subiram corretamente com as novas configurações:

```bash
# 1. Bridge respondendo na porta?
curl -s http://localhost:$NOVA_PORTA/health

# 2. Gateway log sem erros?
tail -15 ~/.hermes/profiles/<CLIENT_ID>/logs/gateway.log | grep -E "✓ whatsapp connected|provider|error" | head -5

# 3. Ambos vivos? Validar bridge pela porta e gateway pelo PID do perfil.
#    gateway.pid pode ser número puro OU JSON {"pid": ...}; parsear antes de usar ps.
BRIDGE_OK=$(curl -s http://localhost:$NOVA_PORTA/health | grep -oP '"status":"\K[^"]+' || echo OFF)
GW_PID=$(python3 - <<'PY'
import json, pathlib, re
f=pathlib.Path.home()/'.hermes/profiles/<CLIENT_ID>/gateway.pid'
raw=f.read_text().strip() if f.exists() else ''
try:
    v=json.loads(raw); print(v.get('pid') if isinstance(v, dict) else v)
except Exception:
    m=re.search(r'\d+', raw); print(m.group() if m else '')
PY
)
GW_OK=OFF
if [ -n "$GW_PID" ] && ps -p "$GW_PID" >/dev/null 2>&1; then
  ENV_HOME=$(tr '\0' '\n' < "/proc/$GW_PID/environ" 2>/dev/null | awk -F= '$1=="HERMES_HOME"{print substr($0,13)}' || true)
  [ "$ENV_HOME" = "$HOME/.hermes/profiles/<CLIENT_ID>" ] && GW_OK=OK || GW_OK="PID_DE_OUTRO_PROFILE:$ENV_HOME"
fi
printf 'bridge=%s gateway=%s\n' "$BRIDGE_OK" "$GW_OK"

# 4. Se mudou .env que afeta provider: rodar smoke test direto com a chave do perfil
key=$(grep '^OLLAMA_API_KEY=' ~/.hermes/profiles/<CLIENT_ID>/.env | cut -d= -f2-)
curl -s -X POST https://ollama.com/v1/chat/completions \
  -H "Authorization: Bearer $key" \
  -H "Content-Type: application/json" \
  -d '{"model":"minimax-m3","messages":[{"role":"user","content":"oi"}],"max_tokens":5}' \
  | head -c 100
```

---

## Phase 6 — Re-sync de chaves do root (caso especial)

Quando o admin do sistema **troca uma chave de API no `~/.hermes/.env` global** (ex: rotacionou `OLLAMA_API_KEY`, mudou de provedor), os perfis que copiaram a chave no `.env` continuam com a chave antiga. Esta fase re-sincroniza.

**Pré-condição:** o admin JÁ editou `~/.hermes/.env` (Root não mexe nisso — é configuração do sistema, não do tenant).

```bash
# 1. Confirmar que o .env do perfil tem chave (não é symlink)
if [ -L ~/.hermes/profiles/<CLIENT_ID>/.env ]; then
  echo "Este perfil usa symlink de .env — atualização é automática, pular esta phase"
  exit 0
fi

# 2. Para CADA chave de provider conhecida, copiar do global pro perfil
for key in OLLAMA_API_KEY OPENROUTER_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY; do
  if grep -q "^$key=" ~/.hermes/.env; then
    new_value=$(grep "^$key=" ~/.hermes/.env | cut -d= -f2-)
    if grep -q "^$key=" ~/.hermes/profiles/<CLIENT_ID>/.env; then
      sed -i "s|^$key=.*|$key=$new_value|" ~/.hermes/profiles/<CLIENT_ID>/.env
      echo "[re-sync] $key atualizada no perfil <CLIENT_ID>"
    else
      echo "$key=$new_value" >> ~/.hermes/profiles/<CLIENT_ID>/.env
      echo "[re-sync] $key adicionada ao perfil <CLIENT_ID>"
    fi
  fi
done

# 3. Reiniciar gateway pra pegar a nova chave
kill -TERM $(cat ~/.hermes/profiles/<CLIENT_ID>/gateway.pid) 2>/dev/null
sleep 3
if ps -p $(cat ~/.hermes/profiles/<CLIENT_ID>/gateway.pid) > /dev/null 2>&1; then
  kill -9 $(cat ~/.hermes/profiles/<CLIENT_ID>/gateway.pid)
fi

set -a; source ~/.hermes/profiles/<CLIENT_ID>/.env; set +a
export HERMES_HOME=/home/<USER>/.hermes/profiles/<CLIENT_ID>
export VIRTUAL_ENV=/home/<USER>/.hermes/hermes-agent/venv
export PATH="$VIRTUAL_ENV/bin:$PATH"
nohup hermes gateway run --replace \
  > ~/.hermes/profiles/<CLIENT_ID>/logs/gateway.log 2>&1 &
echo $! > ~/.hermes/profiles/<CLIENT_ID>/gateway.pid

# 4. Validar: smoke test do provider com a chave NOVA
sleep 5
key=$(grep "^OLLAMA_API_KEY" ~/.hermes/profiles/<CLIENT_ID>/.env | cut -d= -f2-)
curl -s -X POST https://ollama.com/v1/chat/completions \
  -H "Authorization: Bearer $key" \
  -H "Content-Type: application/json" \
  -d '{"model":"minimax-m3","messages":[{"role":"user","content":"oi"}],"max_tokens":5}' \
  | head -c 100
# Esperado: resposta com id (ex: {"id":"chatcmpl-...}), NÃO "Unauthorized"
```

**Re-sync em massa (todos os perfis de uma vez):** ver `root-soul.md` seção "Re-sync rápido" (loop em todos os profiles/, replicar chaves, reiniciar gateways pelos PIDs).

**Quando rodar esta Phase:**
- Admin rotacionou chave de API no root
- Admin mudou de provedor (Ollama → OpenRouter, etc.)
- Admin adicionou nova chave de provider
- Após recovery de incidente onde creds foram comprometidos

**Quando NÃO rodar:**
- Mudança foi só no `.env` do perfil individual (esse é Phase 3 normal)
- Mudança foi em `config.yaml` (symlink, atualiza sozinho)
- Mudança foi em `produto.md` (não afeta provider)