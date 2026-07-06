<!--
Criado em: 06/07/2026 13:10
Modificado em: 06/07/2026 13:10
-->

# docker_api — API de interação com o hermes-agent

Proxy/wrapper FastAPI para a `vya-workforce-api` (hermes-agent em
homologação, ver `src/docker_hermes/`). Serviço independente — não builda
nem depende do código-fonte do hermes-agent, só fala HTTP com ele.

```
src/docker_api/
├── main.py
├── core/
│   └── config.py        # Settings (upstream base URL, timeout, VYA_API_KEY)
├── clients/
│   └── vya_client.py     # cliente httpx assíncrono para a vya-workforce-api
├── models/
│   └── agent.py          # schemas de request (Create/UpdateAgentRequest)
├── routers/
│   ├── health.py          # /health (próprio) e /health/upstream (repassa)
│   └── agents.py          # CRUD de agentes, repassa para a vya-workforce-api
├── Dockerfile
├── docker-compose.yaml
├── entrypoint.sh          # injeta Docker secret VYA_API_KEY como env var
└── .env.example
```

## Por que existe

O hermes-agent (+ dashboard + gateway + vya-workforce-api, stack
`src/docker_hermes/`) está em homologação. Este serviço é a camada de
interação com ele — hoje um proxy fino do CRUD de agentes (`/agents`), para
crescer com regras de negócio próprias antes de repassar para a
vya-workforce-api (validações extras, orquestração de múltiplas chamadas,
etc.), sem precisar tocar no código vendorizado do hermes-agent.

Rotas cobertas até agora (extensível — ver `hermes-api/server/app.py` em
`docker_hermes` para os demais endpoints ainda não espelhados: knowledge,
skills, contacts, followup, calendar):

| Rota | Repassa para |
|------|--------------|
| `GET /api/v1/health` | (local, não chama upstream) |
| `GET /api/v1/health/upstream` | `GET /health` |
| `GET /api/v1/agents` | `GET /agents` |
| `GET /api/v1/agents/{id}` | `GET /agents/{id}` |
| `POST /api/v1/agents` | `POST /agents` |
| `PUT /api/v1/agents/{id}` | `PUT /agents/{id}` |
| `DELETE /api/v1/agents/{id}` | `DELETE /agents/{id}` |

## Segredo

Reusa a **mesma** credencial `VYA_API_KEY` da `vya-workforce-api` (não
duplica) — `.secrets/hermes/VYA_API_KEY`, injetada via Docker secret +
`entrypoint.sh` (mesmo padrão de `src/docker_hermes`).

## Uso

Requer a rede externa `app-network` (a mesma usada por `src/docker_hermes`)
para resolver o hostname `vya-workforce-api` por nome do container:

```bash
cd src/docker_api
cp .env.example .env
docker compose up -d --build
```

- API: http://localhost:8000 (ajuste via `DOCKER_API_PORT`)
- Health próprio: `GET /api/v1/health`
- Health do upstream: `GET /api/v1/health/upstream` (não derruba a app se o
  upstream estiver fora do ar — retorna `{"status": "error", ...}` com
  `200`, não propaga exceção)

## Erros do upstream

`VyaApiError` cobre tanto respostas HTTP de erro da `vya-workforce-api`
quanto falhas de conexão (`httpx.RequestError` — upstream fora do ar,
timeout, DNS). Erros de conexão viram `503` com a mensagem original; erros
HTTP do upstream repassam o status code real — nunca um `500` genérico sem
contexto.
