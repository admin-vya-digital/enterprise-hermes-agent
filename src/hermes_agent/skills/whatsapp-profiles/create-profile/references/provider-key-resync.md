# Provider Key Re-Sync — Standalone Recipe

> Quando o admin do sistema rotaciona chaves de API no `~/.hermes/.env` global
> e os perfis que copiaram precisam ser atualizados em massa.
>
> Não está embutido na `edit-profile` SKILL.md (que cobre 1 perfil por vez).
> Este arquivo é o atalho **em loop** sobre todos os perfis.

---

## Quando usar

- Admin rotacionou `OLLAMA_API_KEY` no root
- Admin mudou de provedor (Ollama → OpenRouter, etc.)
- Admin adicionou uma nova chave
- Após incidente onde creds foram comprometidos

## Por que o `config.yaml` é diferente

| Arquivo | Como o perfil referencia | Quando o root muda, o perfil... |
|---|---|---|
| `~/.hermes/config.yaml` | **symlink** (`profiles/<id>/config.yaml -> ~/.hermes/config.yaml`) | ...atualiza sozinho |
| `~/.hermes/.env` (chaves API) | **cópia** em `profiles/<id>/.env` | ...NÃO atualiza — precisa re-sync |

O `config.yaml` é symlink porque o provider/modelo é o mesmo pra todos os perfis neste ambiente. As chaves de API são cópia porque (a) gateway lê `$HERMES_HOME/.env` no startup e (b) ter cada perfil com sua própria cópia isola falhas de provisionamento.

## Receita (todos os perfis)

```bash
#!/usr/bin/env bash
# Rodar do host, com permissões do user dono dos perfis.
# Não precisa estar dentro do venv do Hermes — só edita arquivos e mata processos.

set -euo pipefail

GLOBAL_ENV="$HOME/.hermes/.env"
PROFILES_DIR="$HOME/.hermes/profiles"

# Chaves que sincronizamos (adicione mais se usar outro provider)
PROVIDER_KEYS=(OLLAMA_API_KEY OPENROUTER_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY)

# Confirmação
echo "=== Re-sync de chaves de provider ==="
echo "Origem: $GLOBAL_ENV"
echo "Destino: todos os perfis em $PROFILES_DIR"
echo "Chaves: ${PROVIDER_KEYS[*]}"
echo ""
read -p "Continuar? (digite 'sim'): " CONF
[ "$CONF" = "sim" ] || { echo "Abortado"; exit 1; }

echo ""
UPDATED=0
SKIPPED=0

for profile_dir in "$PROFILES_DIR"/*/; do
  [ -d "$profile_dir" ] || continue
  profile_id=$(basename "$profile_dir")

  # Pular se não tem .env ou se é symlink
  profile_env="$profile_dir/.env"
  if [ ! -f "$profile_env" ]; then
    echo "[skip] $profile_id: sem .env"
    SKIPPED=$((SKIPPED + 1))
    continue
  fi
  if [ -L "$profile_env" ]; then
    echo "[skip] $profile_id: .env é symlink (já atualizado)"
    SKIPPED=$((SKIPPED + 1))
    continue
  fi

  echo "--- $profile_id ---"
  for key in "${PROVIDER_KEYS[@]}"; do
    if ! grep -q "^$key=" "$GLOBAL_ENV"; then
      continue  # chave não existe no global, pula
    fi
    new_value=$(grep "^$key=" "$GLOBAL_ENV" | cut -d= -f2-)

    if grep -q "^$key=" "$profile_env"; then
      old_value=$(grep "^$key=" "$profile_env" | cut -d= -f2-)
      if [ "$old_value" = "$new_value" ]; then
        echo "  $key: já está igual, pulando"
        continue
      fi
      sed -i "s|^$key=.*|$key=$new_value|" "$profile_env"
      echo "  $key: atualizada"
      UPDATED=$((UPDATED + 1))
    else
      echo "$key=$new_value" >> "$profile_env"
      echo "  $key: adicionada"
      UPDATED=$((UPDATED + 1))
    fi
  done

  # Reiniciar gateway deste perfil pra pegar a chave nova
  pidfile="$profile_dir/gateway.pid"
  if [ -f "$pidfile" ]; then
    gw_pid=$(cat "$pidfile")
    if ps -p "$gw_pid" > /dev/null 2>&1; then
      echo "  reiniciando gateway (PID $gw_pid)..."
      kill -TERM "$gw_pid" 2>/dev/null || true
      sleep 3
      if ps -p "$gw_pid" > /dev/null 2>&1; then
        kill -9 "$gw_pid" 2>/dev/null || true
      fi
      # Relançar com env do perfil carregado
      (
        cd "$profile_dir"
        set -a
        # shellcheck disable=SC1091
        source "$profile_env"
        set +a
        export HERMES_HOME="$profile_dir"
        export VIRTUAL_ENV="$HOME/.hermes/hermes-agent/venv"
        export PATH="$VIRTUAL_ENV/bin:$PATH"
        nohup hermes gateway run --replace \
          > "$profile_dir/logs/gateway.log" 2>&1 &
        echo $! > "$pidfile"
      )
    else
      echo "  gateway não estava rodando (PID $gw_pid morto); pulando restart"
    fi
  else
    echo "  sem gateway.pid; pulando restart"
  fi
done

echo ""
echo "=== Resultado ==="
echo "Perfis atualizados: $UPDATED chave(s)"
echo "Perfis pulados:    $SKIPPED"
echo ""
echo "Validar todos os perfis:"
echo "  for p in $PROFILES_DIR/*/; do"
echo "    id=\$(basename \$p)"
echo "    grep -q 'No inference provider' \$p/logs/gateway.log && echo \"\$id COM PROBLEMA\""
echo "  done"
```

## Variantes

### Atualizar SÓ um perfil (sem loop)

Use `edit-profile` SKILL.md, Phase 6.

### Sincronizar APENAS UMA chave específica

```bash
KEY="OPENROUTER_API_KEY"
new=$(grep "^$KEY=" ~/.hermes/.env | cut -d= -f2-)
for p in ~/.hermes/profiles/*/; do
  [ -L "$p/.env" ] && continue
  if grep -q "^$KEY=" "$p/.env"; then
    sed -i "s|^$KEY=.*|$KEY=$new|" "$p/.env"
    echo "[ok] $p"
  fi
done
```

### Verificar drift (sem atualizar)

```bash
echo "Diff entre global e cópias dos perfis:"
for p in ~/.hermes/profiles/*/; do
  [ -L "$p/.env" ] && continue
  for key in OLLAMA_API_KEY OPENROUTER_API_KEY OPENAI_API_KEY; do
    g=$(grep "^$key=" ~/.hermes/.env | cut -d= -f2-)
    l=$(grep "^$key=" "$p/.env" 2>/dev/null | cut -d= -f2-)
    [ -n "$g" ] && [ "$g" != "$l" ] && echo "DRIFT: $p $key (global: ${g:0:8}..., perfil: ${l:0:8}...)"
  done
done
```

## Por que isso não é automática

Você poderia perguntar: "o gateway não tem hot-reload de .env?" — não tem. O gateway lê env vars uma vez no startup e cacheia. Por isso o re-sync precisa **matar e relançar** o processo, não basta editar o arquivo.

Alternativas futuras (não implementadas):
- Gateway poderia ler .env a cada mensagem (latência +10ms, mas sem restart)
- Poderia haver um `signal handler` que recarrega config on SIGUSR1
- `config.yaml` poderia ser watched via inotify

Por ora, o caminho é restart. É barato (~5s downtime) e correto.