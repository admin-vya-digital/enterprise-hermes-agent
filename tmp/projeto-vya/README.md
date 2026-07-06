# Vya Digital Workforce

Estrutura de entrega do produto. Tudo funciona relativo a esta raiz — nada
depende de `~/.hermes`.

```
projeto-vya/
├── hermes-agent/      # hermes-agent 0.15.1 patchado (código + venv)
├── hermes-api/        # vya-workforce-api (FastAPI de provisionamento/gestão)
├── profiles/          # dados de runtime dos agentes (um diretório por agente)
├── skills/            # skills compartilhadas (symlinkadas em cada perfil)
└── config.base.yaml   # (opcional) config.yaml base copiado para novos perfis
```

## Docker (recomendado)

```bash
cp .env.example .env   # preencha VYA_API_KEY e ANTHROPIC_API_KEY
docker compose up -d --build
```

- API: http://localhost:8700 (swagger em /docs)
- Dashboard hermes: http://localhost:9119 (login por pareamento:
  `docker exec -e HERMES_HOME=/app/profiles/dashboard vya-dashboard /app/hermes-agent/venv/bin/hermes pairing approve <código>`)
- Dados dos agentes persistem em `./data/profiles` (volume).

## Setup manual (sem Docker)

Pré-requisitos: Python ≥ 3.11 (testado com 3.12), Node ≥ 20 (testado com 24).

```bash
# 1. venv do hermes-agent + deps da API
cd hermes-agent
python3 -m venv venv
./venv/bin/pip install -e .
./venv/bin/pip install -r ../hermes-api/requirements.txt

# 2. bridge do WhatsApp (uma vez por servidor, antes do primeiro agente)
cd scripts/whatsapp-bridge && npm install && cd ../..

# 3. dashboard web (uma vez; builda para hermes_cli/web_dist)
cd web && npm install && npm run build && cd ..

# 4. subir a API
cd ../hermes-api
export VYA_API_KEY=<chave>
./start.sh          # porta 8700 (VYA_PORT para mudar)

# 5. (opcional) subir o dashboard
HERMES_HOME=<raiz>/profiles/dashboard \
  <raiz>/hermes-agent/venv/bin/hermes dashboard --no-open   # porta 9119
```

> **Importante:** `hermes-agent/venv/` e `node_modules/` NÃO são portáveis
> entre máquinas — sempre reconstrua no ambiente de destino (o Dockerfile
> já faz isso na imagem).

## Validação rápida (o que deve funcionar)

```bash
curl http://localhost:8700/health
# → {"status":"ok",...}

# criar um agente
curl -X POST http://localhost:8700/agents \
  -H "Authorization: Bearer $VYA_API_KEY" -H 'Content-Type: application/json' \
  -d '{"agent_id":"sdr-01","name":"SDR","provider":"anthropic","provider_api_key":"<chave-real>"}'
# → 201; cria profiles/sdr-01/ com SOUL.md, config.yaml, plugin whatsapp-mixed

# conectar WhatsApp (retorna pareamento; QR em GET .../channels/whatsapp/qr → PNG)
curl -X POST http://localhost:8700/agents/sdr-01/channels/whatsapp \
  -H "Authorization: Bearer $VYA_API_KEY"
```

Todas as rotas (exceto `/health`) exigem `Authorization: Bearer <VYA_API_KEY>`.
Swagger completo em `http://localhost:8700/docs`. Grupos de endpoints:
agents (CRUD), knowledge (URL/upload), skills, contacts (`owner`/`cliente`),
followup (jobs cron), memory por contato, logs/runs, calendar (Google OAuth)
e channels/whatsapp (pareamento + QR). Suíte completa dos 31 endpoints
validada em 2026-07-06.

## Portas

| Porta | Serviço |
|-------|---------|
| 8700  | vya-workforce-api |
| 9119  | dashboard web do hermes (login por código de pareamento) |
| 3100+ | bridges de WhatsApp (um por agente, alocação automática) |
| 8810+ | gateways hermes (um por agente, alocação automática) |

## Caminhos configuráveis (env vars)

| Env var            | Default              | O que é                        |
|--------------------|----------------------|--------------------------------|
| `VYA_PROFILES_DIR` | `<raiz>/profiles`    | onde vivem os perfis           |
| `VYA_HERMES_DIR`   | `<raiz>/hermes-agent`| código/venv do hermes patchado |
| `VYA_SKILLS_DIR`   | `<raiz>/skills`      | skills compartilhadas          |

Chaves de provider (ANTHROPIC_API_KEY etc.) são lidas de
`hermes-agent/.env` ou `<raiz>/.env` na hora de provisionar um perfil.

Documentação da API: `hermes-api/docs/` (PLAN.md, DEPLOY.md, swagger.html).

## Versão do hermes-agent

O `hermes-agent/` reporta v0.15.1, mas a base real é a `main` oficial de
2026-06-04 (commit `80672754a` do NousResearch/hermes-agent) — **posterior**
à release 0.15.2, que foi um hotfix apenas de metadados de empacotamento.
Diretórios `tests/` e `website/` foram removidos da cópia.

As modificações Vya sobre essa base (11 arquivos, ~112 linhas) estão
documentadas em `hermes-agent-patches.diff` — use-as como guia para
rebasear em versões futuras do hermes.
