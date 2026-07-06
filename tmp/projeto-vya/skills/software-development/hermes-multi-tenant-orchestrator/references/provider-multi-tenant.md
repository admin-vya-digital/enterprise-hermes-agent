# Provider de IA em Setup Multi-Tenant (Hermes)

> **Regra fundamental**: quando o Hermes roda em setup multi-tenant (`HERMES_HOME=~/.hermes/profiles/{id}/`), o provider de IA precisa estar configurado em **DOIS lugares** dentro de `$HERMES_HOME`. Configurar só um = gateway sobe sem erro mas responde em modo degradado (`api_calls=0`).

## Onde o gateway busca o provider

O gateway Python resolve configuração via env var `HERMES_HOME`:

```python
# gateway/run.py (simplificado)
hermes_home = os.environ.get('HERMES_HOME') or default = ~/.hermes/
config = load_config(f'{hermes_home}/config.yaml')   # (1) provider, model, base_url
env = load_dotenv(f'{hermes_home}/.env')             # (2) API keys
api_key = env.get('OLLAMA_API_KEY')                  # ← SÓ do .env do HERMES_HOME
```

Se `HERMES_HOME` aponta pro perfil mas `config.yaml` não tem provider ou `.env` não tem chave, gateway **não aborta** — sobe, conecta no WhatsApp, e cai em fallback na primeira chamada real.

## O que vai em cada arquivo

| Arquivo | Conteúdo | Onde |
|---|---|---|
| `~/.hermes/config.yaml` | `model.default`, `model.provider`, `model.base_url` | global |
| `~/.hermes/profiles/{id}/config.yaml` | (geralmente symlink pro global) | perfil |
| `~/.hermes/.env` | `OLLAMA_API_KEY`, etc | global |
| `~/.hermes/profiles/{id}/.env` | `WHATSAPP_*`, `BRIDGE_PORT`, **cópia da chave de API** | perfil |

## Setup recomendado (v1)

```bash
# A) config.yaml do perfil é symlink do global (1 escrita, N perfis)
ln -sfn ~/.hermes/config.yaml ~/.hermes/profiles/<CLIENT_ID>/config.yaml

# B) Chave de API é CÓPIA no .env do perfil (cada perfil tem o seu)
grep -q "^OLLAMA_API_KEY" ~/.hermes/profiles/<CLIENT_ID>/.env || \
  echo "OLLAMA_API_KEY=*** '^OLLAMA_API_KEY' ~/.hermes/.env | cut -d= -f2-)" \
    >> ~/.hermes/profiles/<CLIENT_ID>/.env

# C) Reiniciar gateway pra reler config
pkill -TERM -f "hermes gateway run"
sleep 3
# relançar com HERMES_HOME apontado pro perfil
```

## Setup alternativo: symlink do `.env` inteiro

Se você quer que mudar a chave global propague pra todos os perfis sem replicar:

```bash
# ATENÇÃO: só funciona se o .env global NÃO tiver vars que conflitam com o perfil
# (ex: WHATSAPP_ENABLED seria igual pra todos, e ia dar conflito se cada perfil
# tiver allowlist diferente)
rm ~/.hermes/profiles/<CLIENT_ID>/.env
ln -sfn ~/.hermes/.env ~/.hermes/profiles/<CLIENT_ID>/.env
```

**Limitação**: o `.env` do perfil precisa ter também as `WHATSAPP_*` (que são por perfil). Se você symlinkar o global, perde isolamento. Solução: manter `WHATSAPP_*` no perfil como overrides via `source` ou trocar pra um sistema de config mais sofisticado (não existe nativamente).

**Recomendação**: usar cópia no `.env` do perfil. Drift é gerenciável com disciplina; conflito é explosivo.

## Provider por perfil — NÃO EXISTE nativamente

O Hermes hoje tem **UM** provider global configurado em `config.yaml`. Os "profiles" mencionados no código (`get_provider_profile` em `agent/auxiliary_client.py`) são profiles de PROVEDOR (ex: profile do OpenRouter com headers custom), não profiles de CLIENTE.

Se você precisa de provider diferente por cliente (ex: cliente A usa OpenAI, cliente B usa Ollama local), é **trabalho de código** em:
- `gateway/run.py` → resolver provider a partir do `config.yaml` carregado
- `agent/auxiliary_client.py` → carregar provider por sessão/perfil

Workaround v1: manter provider global único e usar o mesmo pra todos os perfis. Customizar por cliente é roadmap.

## Como diagnosticar "api_calls=0"

```bash
# 1. Verificar config.yaml do perfil
ls -la ~/.hermes/profiles/<CLIENT_ID>/config.yaml
head -10 ~/.hermes/profiles/<CLIENT_ID>/config.yaml
# Se for symlink, segue o global. Se for arquivo próprio, verifica provider/.

# 2. Verificar chave no .env do perfil
grep -E "^OLLAMA_API_KEY|^OPENROUTER_API_KEY|^OPENAI_API_KEY" \
  ~/.hermes/profiles/<CLIENT_ID>/.env

# 3. Smoke test direto (independe do gateway)
python3 << PYEOF
import urllib.request, json
with open('/home/praxislatina/.hermes/profiles/<CLIENT_ID>/.env') as f:
    for line in f:
        if line.startswith('OLLAMA_API_KEY=***            key = line.split('=', 1)[1].strip()
            break
req = urllib.request.Request(
    'https://ollama.com/v1/chat/completions',
    data=json.dumps({"model":"minimax-m3","messages":[{"role":"user","content":"diga ok"}],"max_tokens":5}).encode(),
    headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
    method='POST'
)
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        print(f'Status {r.status}: OK — provider responde')
except urllib.error.HTTPError as e:
    print(f'ERRO {e.code}: {e.read().decode()[:200]}')
PYEOF
```

Se smoke test dá OK mas gateway loga `api_calls=0`, o problema é cache do gateway — reinicie.

## Onde aplicar

- `hermes-multi-tenant-orchestrator` Phase D.2 (já referencia este setup)
- `whatsapp-instances/instance-number` Phase 4.6 (versão whatsapp-specific)
- Qualquer skill que adicione nova plataforma (Telegram, Discord, Slack) que use `HERMES_HOME`

## Mudanças recentes (timeline)

- **2026-06-26:** Descoberto o problema em provisionamento `jordao-teste`. Gateway tinha config global mas perfil não — `api_calls=0` constante. Fix: symlink de config.yaml + cópia da chave no `.env` do perfil.