# Wizard Flow — CREATE perfil de cliente

Fluxo interativo completo para provisionar um novo perfil WhatsApp dentro do container multi-tenant.

## Pré-condições
- Container rodando, Hermes Root ativo
- `~/.hermes/hermes-agent/` com bridge.js e node_modules/ instalados
- `.env` global existe e tem API keys (não toca em config de perfil)
- Nenhum bridge Node.js anterior ocupando portas (verificar com `lsof -i :3000+`)

## Phase 0 — Reconhecimento
Antes de perguntar nada, faça um reconhecimento silencioso:
```bash
ps aux | grep -E "bridge.js|node.*whatsapp" | grep -v grep
ls -la ~/.hermes/whatsapp/ 2>/dev/null    # vestígios de instância antiga?
ls -la ~/.hermes/profiles/ 2>/dev/null    # árvore de perfis existe?
lsof -i :3000 2>/dev/null; lsof -i :3001 2>/dev/null; lsof -i :3002 2>/dev/null
grep -E "^WHATSAPP_" ~/.hermes/.env 2>/dev/null   # config global?
```
Apresente um resumo do estado atual antes de prosseguir.

## Phase 1 — Decisões de governança
Pergunte ao usuário 3 itens, cada um com opções a/b/c quando envolver escolha de estado:

1. **Identificador do cliente** → vira `{id}` da pasta
2. **Número Home** → formato internacional sem `+` nem espaços (ex: `5513988396616`)
3. **Porta inicial do bridge** → sugestão 3000 (autoincrement depois)

Antes de QUALQUER delete/kill, confirme com:
- "O `~/.hermes/whatsapp/` antigo (com session/ + log) deve ser: (a) preservado / (b) backup e começar do zero / (c) mover pra dentro do perfil novo?"
- "O `~/.hermes/.env` já tem vars WHATSAPP_*: (a) manter global e perfil lê dele / (b) criar .env só do perfil / (c) duplicar?"
- "QR code: (a) PTY interativo / (b) PNG em /tmp/qr.png / (c) PNG + ASCII no terminal?"

## Phase 2 — Limpeza (se aprovado)
```bash
# Backup do .env global antes de mexer
cp ~/.hermes/.env ~/.hermes/.env.bak.pre-{profile_id}.$(date +%Y%m%d_%H%M%S)

# Vestígios do whatsapp/ antigo (se opção "do zero")
rm -rf ~/.hermes/whatsapp/

# Remover bloco WHATSAPP_* do .env global (se opção "isolamento total")
sed -i '/^WHATSAPP_/d' ~/.hermes/.env
```

## Phase 3 — Estrutura do perfil
```bash
mkdir -p ~/.hermes/profiles/{id}/{session,logs}
# Criar .env com perms 600 (via write_file, conteúdo do template profile-env.template)
# Criar produto.md base (via write_file, conteúdo do template produto.md.template)
```

## Phase 4 — Patch temporário do bridge (para PNG do QR)
```bash
# Localizar bloco if (qr) {} em ~/.hermes/hermes-agent/scripts/whatsapp-bridge/bridge.js
# Adicionar dentro:
#   try { writeFileSync('/tmp/qr.txt', qr); } catch (e) {}
# Use patch (mode=replace, old_string único, new_string).
```
**IMPORTANTE:** esse patch será revertido após pareamento.

## Phase 5 — Subir bridge em background
```bash
# terminal(background=true, notify_on_complete=false) — NUNCA nohup & em foreground
set -a && source ~/.hermes/profiles/{id}/.env && set +a && \
  cd ~/.hermes/hermes-agent/scripts/whatsapp-bridge && \
  exec node bridge.js --port "$BRIDGE_PORT" --session "$SESSION_DIR" --mode "$WHATSAPP_MODE" \
  > "$BRIDGE_LOG" 2>&1
```

## Phase 6 — Esperar QR e gerar PNG
```bash
for i in $(seq 1 30); do
  if [ -f /tmp/qr.txt ] && [ -s /tmp/qr.txt ]; then
    echo "QR após ${i}s"
    break
  fi
  sleep 1
done
python3 -c "import qrcode; qrcode.make(open('/tmp/qr.txt').read().strip()).save('/tmp/qr.png')"
```

## Phase 7 — Apresentar QR (dois formatos)
Mostre ao usuário:
1. Caminho do PNG: `/tmp/qr.png`
2. Bloco ASCII colado de `tail -50 $BRIDGE_LOG`

Aguarde o usuário confirmar que escaneou.

## Phase 9 — Confirmar conexão e reverter patch
```bash
# Esperar conexão
for i in $(seq 1 60); do
  if grep -q "WhatsApp connected" $BRIDGE_LOG 2>/dev/null; then
    echo "Conectado após ${i}s"
    break
  fi
  sleep 1
done

ls $SESSION_DIR/creds.json   # deve existir

# VALIDAR HOME_NUMBER contra creds.json (NUNCA confiar em backup ou histórico)
EXPECTED_PHONE=$(grep ^HOME_NUMBER= ~/.hermes/profiles/{id}/.env | cut -d= -f2)
ACTUAL_PHONE=$(python3 -c "import json; d=json.load(open('$SESSION_DIR/creds.json')); print(d['me']['id'].split(':')[0])")
if [ "$EXPECTED_PHONE" != "$ACTUAL_PHONE" ]; then
  echo "ATENCAO: HOME_NUMBER esperado=$EXPECTED_PHONE, real=$ACTUAL_PHONE"
  echo "PARE E PERGUNTE AO USUARIO QUAL EH O CORRETO ANTES DE PROSSEGUIR"
fi

# Reverter patch do bridge.js — usar patch (mode=replace) deletando as 2 linhas:
#   // [Hermes Root] Persist raw QR string for PNG generation
#   try { writeFileSync('/tmp/qr.txt', qr); } catch (e) {}
```

## Phase 10 — Subir Gateway Python (NÃO PULE — bridge sozinho não responde)

Bridge Node.js só transporta mensagens. Gateway Python é o cérebro. Sem ele, mensagens entram na fila do bridge e ninguém responde.

```bash
# 1. Symlink da session no path que o gateway espera
mkdir -p $HERMES_HOME/platforms/whatsapp
ln -sfn $SESSION_DIR $HERMES_HOME/platforms/whatsapp/session

# 2. Symlink do config.yaml global (se quiser provider compartilhado)
ln -sfn /home/<user>/.hermes/config.yaml $HERMES_HOME/config.yaml

# 3. Subir gateway em background (terminal(background=true, notify_on_complete=false))
set -a && source ~/.hermes/profiles/{id}/.env && set +a
export HERMES_HOME=/home/<user>/.hermes/profiles/{id}
export VIRTUAL_ENV=/home/<user>/.hermes/hermes-agent/venv
export PATH=$VIRTUAL_ENV/bin:$PATH
exec hermes gateway run --replace > "$GATEWAY_LOG" 2>&1

# 4. Aguardar inicialização (5-8s)
sleep 8

# 5. Verificar que conectou ao WhatsApp
grep -E "whatsapp connected|Cron ticker" $GATEWAY_LOG
# Deve mostrar ambas
```

## Phase 11 — Healthcheck end-to-end
```bash
# Bridge vivo?
curl -s http://localhost:$BRIDGE_PORT/health
# {"status":"connected","queueLength":0,...}

# Gateway vivo?
ps aux | grep "hermes gateway run" | grep -v grep | head -1

# Provider funcionando? (smoke test isolado)
echo "oi" | timeout 30 hermes chat --model <MODELO> 2>&1 | tail -3
# Deve mostrar resposta (qualquer coisa ≠ erro)

# Teste real (do celular do usuário): outro número manda msg → bot responde em ~10s
tail -30 $GATEWAY_LOG | grep -E "inbound|response|Sending"
# Esperado: inbound message → response ready (api_calls>=1) → Sending response
```

## Phase 12 — Relatório ao usuário
Resumo:
- Pasta do perfil: `~/.hermes/profiles/{id}/`
- Porta bridge: `$BRIDGE_PORT`
- Porta gateway: `$GATEWAY_PORT`
- Home: `$HOME_NUMBER` (validado contra creds.json)
- Bridge PID: gravado em `~/.hermes/profiles/{id}/bridge.pid`
- Gateway PID: visível em `ps aux | grep "hermes gateway run"`
- Status: bridge=connected, gateway=running, provider=ok
- Próximo passo: o Número Home pode mandar `/sethome` pelo WhatsApp para se tornar canal oficial de notificações, e enviar mensagens para refinar `produto.md`

## Saída do wizard bem-sucedido
```
✅ Perfil {id} provisionado
   Bridge:  porta 3000, PID 25814, status connected
   Gateway: porta 8800, PID 27198, status running, provider ollama-cloud
   Home:    551131350743 (validado contra creds.json)
   Logs:    ~/.hermes/profiles/{id}/logs/
   produto.md: template base (pronto para edição pelo Home via /sethome)
```