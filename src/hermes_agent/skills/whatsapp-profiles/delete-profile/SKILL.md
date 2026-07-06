---
name: delete-profile
summary: Deletar completamente UM Perfil Isolado (Cliente) do Hermes Agent (matar processos específicos → liberar porta → deletar arquivos). Exige o admin digitar o nome do perfil para confirmar.
description: "Procedimento destrutivo para remover um cliente do ambiente multi-tenant. Encerra o gateway e bridge DESTE perfil apenas (via PID), deleta todo o diretório do perfil. NUNCA afeta outros perfis."
trigger: "O usuário (Root Admin) pede para deletar, remover, apagar, limpar ou destruir UM perfil específico de cliente."
pitfalls:
  - "Ação irreversível: Uma vez deletado o diretório de sessão, o cliente precisará escanear um novo QR code caso a instância seja recriada."
  - "CONFIRMAÇÃO OBRIGATÓRIA POR DIGITAÇÃO: antes de qualquer ação destrutiva, pedir ao admin que digite o nome EXATO do perfil (ex: '<CLIENT_ID>'). Se ele digitar diferente do <CLIENT_ID>, ABORTAR. Isso previne deleção acidental."
  - "Risco de derrubar a frota: NUNCA use 'pkill -f bridge.js' ou 'killall node' ou 'pkill -f \"hermes gateway run\"'. Isso matará TODOS os outros clientes no container. Sempre mate lendo o PID específico do cliente (lido do arquivo <profile>/gateway.pid ou <profile>/bridge.pid)."
  - "Risco de exclusão em massa: NUNCA use curingas no comando de remoção (ex: rm -rf ~/.hermes/profiles/* ou rm -rf ~/.hermes/profiles/<CLIENT_ID>/*). SEMPRE passe o <CLIENT_ID> completo no `rm -rf ~/.hermes/profiles/<CLIENT_ID>` (sem curinga, sem /*)."
  - "Gateway Python PRIMEIRO, bridge DEPOIS. Se matar só o bridge, o gateway fica tentando reconectar indefinidamente e pode corromper `gateway_state.json`. Ordem: `kill -TERM $(cat profiles/<CLIENT_ID>/gateway.pid)` → esperar 3s → matar bridge → deletar pasta."
  - "SIGTERM no gateway, SIGKILL no bridge. Gateway tem cleanup handler que suspende sessão corretamente; -9 pode deixar estado inconsistente. Bridge Node.js não responde a SIGTERM de forma confiável, sempre precisa de -9."
  - "MATAR SÓ O GATEWAY DESSE PERFIL: usar `kill -TERM $(cat profiles/<CLIENT_ID>/gateway.pid)` e NÃO `pkill -f \"hermes gateway run\"` — o segundo mata gateways de TODOS os perfis. (Bug histórico: o create-profile original ensinava pkill; corrigido.)"
  - "Se só existe um perfil no container, pkill pode PARECER funcionar, mas vira bomba quando houver 2+ perfis. Sempre trate como multi-tenant."
  - "Verificar que outros perfis não estão rodando neste <CLIENT_ID>: checar `ls ~/.hermes/profiles/` ANTES de deletar, pra confirmar que o ID não foi confundido."
  - "Após deletar, se o admin quiser recriar o mesmo perfil, vai precisar escanear QR de novo (sessão Baileys foi apagada). Avise antes."
---

# Delete Instance — Exclusão de UMA instância Multi-Agentes

**Classe de tarefa**: Exclusão completa e irreversível de UMA instância (Perfil/Cliente) do Hermes Agent, liberando os recursos de rede e disco no container. Não afeta outros perfis.

## Phase 0 — Identificação e Validação da Existência

Antes de qualquer coisa, confirmar que o perfil EXISTE:

```bash
# 1. Listar perfis existentes (pra evitar digitar errado)
ls ~/.hermes/profiles/ 2>/dev/null

# 2. Verificar que <CLIENT_ID> é um diretório válido
test -d ~/.hermes/profiles/<CLIENT_ID> && echo "EXISTE" || { echo "ERRO: perfil <CLIENT_ID> não existe"; exit 1; }

# 3. Se existe, mostrar resumo do que será apagado
echo "=== RESUMO DO PERFIL <CLIENT_ID> ==="
echo "Processo gateway: PID $(cat ~/.hermes/profiles/<CLIENT_ID>/gateway.pid 2>/dev/null || echo 'sem PID salvo')"
echo "Processo bridge:  PID $(cat ~/.hermes/profiles/<CLIENT_ID>/bridge.pid 2>/dev/null || echo 'sem PID salvo')"
echo "Tamanho em disco:"
du -sh ~/.hermes/profiles/<CLIENT_ID> 2>/dev/null
echo "Sessão WhatsApp:"
ls ~/.hermes/profiles/<CLIENT_ID>/session/creds.json 2>/dev/null && echo "  creds.json existe (autenticado)"
```

Se o perfil não existir, ABORTAR e perguntar ao admin.

## Phase 1 — Confirmação Explícita por Digitação

**NUNCA deletar sem o admin digitar o nome EXATO.** Mesmo que o nome esteja no contexto da conversa.

```bash
echo ""
echo "⚠️  ATENÇÃO: Esta operação é IRREVERSÍVEL."
echo "   Vou deletar a pasta ~/.hermes/profiles/<CLIENT_ID>/"
echo "   Junto com: sessão Baileys, produto.md, .env, logs, PIDs."
echo "   Para confirmar, digite EXATAMENTE o nome do perfil: <CLIENT_ID>"
echo ""
read -p "Nome do perfil: " CONFIRMACAO

if [ "$CONFIRMACAO" != "<CLIENT_ID>" ]; then
  echo ""
  echo "✗ Nome digitado ('$CONFIRMACAO') difere do alvo ('<CLIENT_ID>'). ABORTADO."
  exit 1
fi

echo "✓ Confirmado. Prosseguindo com delete..."
```

**Por que essa confirmação?**
- Deleta sessão Baileys (não tem undo — vai precisar novo QR)
- Pode ter `produto.md` com horas de trabalho do cliente
- Comando destrutivo único (`rm -rf`)

Se em conversa o admin disser "pode deletar", "vai", "confirmo" sem digitar — pedir a digitação mesmo assim.

## Phase 2 — Encerrar Gateway Python (SÓ deste perfil)

**CRÍTICO:** matar APENAS o gateway DESTE perfil via PID salvo, não via pkill.

```bash
if [ -f ~/.hermes/profiles/<CLIENT_ID>/gateway.pid ]; then
  GATEWAY_PID=$(cat ~/.hermes/profiles/<CLIENT_ID>/gateway.pid)
  kill -TERM $GATEWAY_PID 2>/dev/null
  sleep 3

  # Escalonar pra SIGKILL só se necessário e só neste PID
  if ps -p $GATEWAY_PID > /dev/null 2>&1; then
    kill -9 $GATEWAY_PID 2>/dev/null
    sleep 1
  fi
fi

# Confirmar: contar gateways TOTAL no container (deve diminuir se era o único)
ps aux | grep "hermes gateway run" | grep -v grep | wc -l
echo "(Se outros perfis existirem, este número > 0 é esperado — não significa falha)"
```

## Phase 3 — Encerrar Bridge (SÓ deste perfil, via porta)

```bash
# Matar bridge lendo a porta do .env (mais robusto que o PID)
if [ -f ~/.hermes/profiles/<CLIENT_ID>/.env ]; then
  PORTA=$(grep -oP '^BRIDGE_PORT=\K.*' ~/.hermes/profiles/<CLIENT_ID>/.env)
  lsof -t -i :$PORTA 2>/dev/null | xargs -r kill -9
fi

# Backup: matar pelo PID salvo
if [ -f ~/.hermes/profiles/<CLIENT_ID>/bridge.pid ]; then
  kill -9 $(cat ~/.hermes/profiles/<CLIENT_ID>/bridge.pid) 2>/dev/null
fi
sleep 2

# Confirmar porta liberada
test -n "$PORTA" && lsof -i :$PORTA 2>/dev/null && echo "AINDA OCUPADA" || echo "PORTA $PORTA LIVRE"
```

## Phase 4 — Remoção da Estrutura de Arquivos

**SEM curinga, SEM `/*` — sempre caminho completo até o `CLIENT_ID`:**

```bash
# Deletar o diretório do cliente inteiro
rm -rf ~/.hermes/profiles/<CLIENT_ID>

# Validar
test -d ~/.hermes/profiles/<CLIENT_ID> && echo "AINDA EXISTE — investigar" || echo "✓ Deletado"
```

**NUNCA usar:**
- `rm -rf ~/.hermes/profiles/*` ← apaga TODOS
- `rm -rf ~/.hermes/profiles/<CLIENT_ID>/*` ← ok neste caso MAS se confundir o ID, apaga outro
- `find ~/.hermes/profiles -name "<CLIENT_ID>" -exec rm -rf {} \;` ← perigoso

## Phase 5 — Verificação Pós-Delete

```bash
# 1. Pasta realmente apagada
ls -la ~/.hermes/profiles/<CLIENT_ID> 2>&1 | head -1
# (deve dar "Arquivo ou diretório inexistente")

# 2. Porta liberada
test -n "$PORTA" && lsof -i :$PORTA 2>/dev/null && echo "PORTA AINDA OCUPADA" || echo "PORTA $PORTA LIVRE"

# 3. Listar perfis restantes (sanidade)
ls ~/.hermes/profiles/

# 4. Contar gateways restantes (deve ser 1 por perfil vivo)
echo "Gateways restantes: $(ps aux | grep 'hermes gateway run' | grep -v grep | wc -l)"
echo "Perfis restantes: $(ls ~/.hermes/profiles/ 2>/dev/null | wc -l)"
# (Se os dois números não baterem, algum perfil ficou sem gateway — investigar)
```

## Resumo da operação

```
ANTES:    N perfis (gateway[N] + bridge[N]) + estado consistente
DEPOIS:   N-1 perfis (gateway[N-1] + bridge[N-1]) + estado consistente
```

Se o número de gateways ≠ número de perfis após o delete, há inconsistência. Diagnosticar com:

```bash
for p in ~/.hermes/profiles/*/; do
  id=$(basename "$p")
  gw=$(ps -p $(cat "$p/gateway.pid" 2>/dev/null) -o pid= 2>/dev/null && echo "OK" || echo "MORTO")
  br=$(curl -s "http://localhost:$(grep -oP '^BRIDGE_PORT=\K.*' "$p/.env")/health" 2>/dev/null | grep -oP '"status":"\K[^"]+' || echo "OFF")
  printf "%-20s gateway=%-6s bridge=%s\n" "$id" "$gw" "$br"
done
```