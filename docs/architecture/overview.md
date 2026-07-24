<!-- Criado em: 24/07/2026 15:51 -->
<!-- Modificado em: 24/07/2026 15:53 -->

# Arquitetura: `src/` — Plataforma de Agentes Hermes (Vya Digital)

**Última atualização**: 24/07/2026
**Owner**: a definir

## Visão Geral

A pasta `src/` contém **três serviços HTTP independentes**, cada um com seu próprio
Dockerfile/build context, que juntos operam "agentes Hermes" — bots de WhatsApp com
IA — para clientes da Vya Digital. Não é um monólito: os serviços se comunicam por
HTTP entre si e compartilham dados principalmente através de um volume de disco
(`profiles/<agent_id>/`), não através de código Python compartilhado.

```
[Cliente/Browser]
       │
       ▼
app-vya-digital  (dashboard operacional, aiohttp, porta 9119)
       │  lê/escreve profiles/<id>/ direto no volume compartilhado
       │  HTTP (Bearer VYA_API_KEY) — só para restart e conexão WhatsApp/QR
       ▼
vyadigital_api  (proxy fino, FastAPI, porta 8000, container "hermes-interaction-api")
       │  HTTP (Bearer VYA_API_KEY)
       ▼
hermes-api / vya-workforce-api  (FastAPI, porta 8700 — plano de controle real)
       │  lê/escreve profiles/<id>/ no filesystem, gerencia PIDs, subprocess
       ▼
gateway do agente Hermes (fora do escopo desta pasta)
```

Pasta ignorada nesta análise por ser um backup: `src/hermes_agent/skills.bak-20260710/`.
Pasta ignorada por restrição de permissão do sistema de arquivos: `src/docker_hermes/`.

## Componentes Principais

### 1. `app-vya-digital/` — Dashboard operacional

- **Responsabilidade**: interface (SPA server-rendered, `index.html` + API JSON) para
  operadores acompanharem e administrarem os agentes — métricas, conversas, leads,
  agenda, configuração de produto, cron de follow-up, logs, pareamento de WhatsApp
  (QR code).
- **Tecnologia**: `aiohttp.web` puro (não FastAPI). Entrypoint único `server.py`,
  função `make_app()` monta a `web.Application` com dois middlewares
  (`rate_limit_middleware`, `authz_middleware`). Roda via `web.run_app(...)`,
  porta padrão `9119` (env `HERMES_DASH_PORT`). Empacotado em `python:3.12-slim`,
  **sem** o venv do hermes-agent — não executa código do agente, só lê/escreve
  arquivos do perfil.
- **Dependências**: lê diretamente o volume compartilhado `HERMES_ROOT`
  (SQLite: `state.db`, `appointments.db`, `leads.db`; JSON/YAML/MD:
  `gateway_state.json`, `channel_directory.json`, `sessions/sessions.json`,
  `cron/jobs.json`, `produto.yaml`, `SOUL.md`). Delega ao `vyadigital_api`
  (via `lib/vya_api_client.py`) apenas o que exige atravessar container: restart
  de agente e status/connect/disconnect/QR do canal WhatsApp.

**Principais rotas** (registradas em `make_app()`, `server.py` linhas ~1990–2027):

| Método | Path | Descrição |
|---|---|---|
| GET | `/` | serve `index.html` (SPA) |
| GET | `/api/me` | identidade resolvida (admin/client), tabs visíveis, logout URL (Authelia) |
| GET | `/api/profiles` | lista perfis (filtrado por perfil se identidade for "client") |
| GET | `/api/profiles/{id}/overview` | métricas agregadas: custo, tokens, mensagens, funil de leads, agenda do dia |
| GET | `/api/profiles/{id}/conversations` | lista conversas com preview |
| GET | `/api/profiles/{id}/conversations/{sid}/messages` | mensagens de uma sessão (+ mensagens de cron) |
| GET/POST | `/api/base/{fname}`, `/api/profiles/{id}/soul`, `/produto` | leitura/escrita crua de `SOUL.md`/`produto.md` |
| GET/POST | `/api/profiles/{id}/produto-config` | configuração estruturada de negócio (`produto.yaml`) |
| GET/DELETE | `/api/profiles/{id}/cron[/{job_id}]` | jobs e histórico de execução do follow-up |
| GET | `/api/profiles/{id}/logs` | tail de logs (`gateway`, `bridge`, `errors`, `agent`, `leads`, `appointments`) |
| GET | `/api/profiles/{id}/contacts` | contatos (merge diretório + sessões) |
| GET/POST/DELETE | `/api/profiles/{id}/leads...` | kanban de leads |
| GET/POST/PATCH/DELETE | `/api/profiles/{id}/appointments...` | agenda |
| GET/POST | `/api/profiles/{id}/contact/memory`, `/contact/delete` | memórias e exclusão de contato |
| POST | `/api/profiles/{id}/restart` | delega ao `vyadigital_api` |
| GET/POST/GET | `/api/profiles/{id}/qr`, `/qr/generate`, `/qr/events` | pareamento WhatsApp (proxy; `qr/events` é SSE) |

> O próprio código (`server.py`, linhas ~2018–2020) documenta rotas do projeto
> original ("cr:ux") que **não foram portadas** para esta infraestrutura:
> group/members, contact/avatar, contact/pause/resume, suspend/resume,
> db/tables/table/query. É um gap de plataforma conhecido, não um bug.

**Principais entidades de dados** (SQLite/YAML ad-hoc, sem ORM):

- `appointments` (`lib/appointments.py`): `id, contact_phone, scheduled_at (unix ts),
  title, notes, status ∈ {scheduled, confirmed, completed, cancelled}, created_at,
  updated_at`.
- `leads` / `lead_phase_history` (`lib/leads.py`): `contact_phone (PK),
  phase ∈ {phase_one..five}, qualification_score (0–100), phase_entered_at,
  updated_at`; histórico com `from_phase/to_phase/timestamp`.
- `produto.yaml` (`lib/produto.py`): fonte única de verdade do negócio —
  `negocio`, `agenda.{expediente, slot_min, lembretes, politicas}`, `categorias`,
  `servicos[{nome, categoria, preco, duracao_min}]`,
  `profissionais[{nome, dias, horario, servicos}]`, `pagamento`, `conhecimento[]`.
  Toda escrita segue `load → mutate → validate → _atomic_save` (arquivo temporário
  + `os.replace`).

**Autenticação**: `authz_middleware` resolve identidade via headers de proxy
(Authelia), com papéis `admin` (acesso total) e `client` (restrito a perfis próprios
e a uma allowlist de métodos/paths). `rate_limit_middleware` limita requisições por
IP (`X-Forwarded-For`) em memória.

---

### 2. `hermes_agent/hermes-api/` — "vya-workforce-api" (plano de controle)

- **Responsabilidade**: API REST determinística de **provisionamento e gestão** de
  agentes Hermes — cria/edita/deleta perfis, gerencia conhecimento, skills, conexão
  WhatsApp, Google Calendar, follow-ups (cron), contatos, memórias, logs/execuções.
  O código documenta explicitamente no topo de `app.py`: este serviço **nunca invoca
  LLM, agente Root ou qualquer canal de conversa** — é puramente infraestrutural.
- **Tecnologia**: FastAPI, porta **8700**, `docs_url=/docs`, `redoc_url=/redoc`.
  Rodado via `start.sh` com `uvicorn app:app --host 0.0.0.0 --port 8700 --reload`,
  usando o **venv do próprio hermes-agent** (`$VYA_HERMES_DIR/venv`) — este serviço
  depende do código-fonte vendorizado do agente (ex.: importa `toolsets.py` em
  `skills.py`). Autenticação: `HTTPBearer` obrigatório em toda rota exceto
  `/health`, comparando contra `VYA_API_KEY` de ambiente.
- **Dependências externas**: Google Calendar (OAuth por perfil, credenciais em
  `profiles/<id>/google_token.json` / `google_client_secret.json`, chamado via
  subprocess a `~/.hermes/skills/productivity/google-workspace/scripts/google_api.py`);
  WhatsApp via Baileys bridge (Node, subprocess, sessão em `session/creds.json`);
  provedores LLM (Anthropic/OpenAI/Ollama) — a chave fica no `.env` do perfil, mas
  este serviço **nunca chama** o LLM diretamente.

**Principais rotas** (arquivo único `server/app.py`, ~30 endpoints, todas sob
`/agents...` exceto `/health`):

| Recurso | Rotas |
|---|---|
| Agentes | `GET /agents`, `GET/PUT/DELETE /agents/{id}`, `POST /agents`, `POST /agents/{id}/restart` |
| Conhecimento | `GET/POST /agents/{id}/knowledge`, `POST .../knowledge/upload` (PDF/DOCX/MD/TXT) |
| Skills | `GET/POST /agents/{id}/skills` (habilita/desabilita toolsets via `.env`) |
| Canal WhatsApp | `GET/POST/DELETE /agents/{id}/channels/whatsapp`, `GET .../whatsapp/qr` (PNG) |
| Calendário | `GET/POST /agents/{id}/calendar/connect`, `GET .../auth-url`, `POST .../auth-code`, `POST .../schedule` |
| Follow-up | `GET/POST /agents/{id}/followup`, `DELETE .../followup/{job_id}` |
| Contatos | `GET/POST/DELETE /agents/{id}/contacts[/{phone}]` |
| Memória | `GET/POST /agents/{id}/memory/{contact_uid}` |
| Observabilidade | `GET /agents/{id}/logs`, `GET /agents/{id}/runs` |

Módulos auxiliares (`server/*.py`): `hermes_fs.py` (I/O de filesystem com
`locked_json`/flock), `provision.py` (criação determinística de perfil),
`lifecycle.py` (edição/deleção, kill de PID SIGTERM→SIGKILL), `knowledge.py`,
`skills.py`, `calendar_wrap.py`, `followup.py`, `contacts.py`, `whatsapp.py`.

**Principais modelos** (Pydantic, inline em `app.py`): `CreateAgentBody` /
`UpdateAgentBody` (agent_id, name, description, objective, personality, language,
model, temperature, initial_prompt, provider, provider_api_key,
`whatsapp_mode ∈ {bot, self-chat, mixed}`, whatsapp_owner_number),
`KnowledgeUrlBody`, `SkillsBody`, `CalendarEventBody`, `CalendarClientSecretBody`,
`CalendarAuthCodeBody`, `FollowupBody`, `ContactBody`, `WriteMemoryBody`.

> Plugin `whatsapp-mixed` (hook `pre_gateway_dispatch`): permite que o mesmo número
> atenda dono (self-chat) e clientes (bot), com silêncio de 10 min e auto-flush via
> cron job one-shot. Instalado globalmente em `~/.hermes/plugins/`, habilitado por
> `config.yaml` de cada perfil. O README do módulo marca esse recurso como
> **"🔶 em validação"** — falta confirmar o auto-flush disparando sozinho em produção.

---

### 3. `vyadigital_api/` — Proxy fino (container "hermes-interaction-api")

- **Responsabilidade**: camada de borda pública — proxy/wrapper HTTP para o
  `hermes-api`. README documenta explicitamente `agents`/`health` como cobertos;
  os demais recursos (`calendar`, `channels`, `contacts`, `followup`, `knowledge`,
  `memory`, `observability`, `skills`) já existem em código (um router por
  recurso), espelhando quase 1:1 as rotas do `hermes-api`.
- **Tecnologia**: FastAPI. O pacote Python interno chama-se **`docker_api`**
  (não `vyadigital_api` — o nome do diretório difere do nome do pacote; ver
  `Dockerfile`: `COPY __init__.py main.py docker_api/`). `main.py` monta a app e
  inclui todos os routers sob o prefixo `settings.api_prefix` (`/api/v1`). Roda via
  `uvicorn docker_api.main:app --host 0.0.0.0 --port 8000`; porta externa mapeada
  `8701` no compose de produção.
- **Configuração** (`core/config.py`, Pydantic Settings, prefixo `DOCKER_API_`):
  `vya_api_base_url` (default `http://vya-workforce-api:8700`), `vya_api_key`
  (lido sem prefixo, de `VYA_API_KEY` — secret compartilhado com o `hermes-api`),
  `vya_api_timeout_seconds`.
- **Cliente** (`clients/vya_client.py`): `VyaClient` sobre `httpx.AsyncClient`
  com `Authorization: Bearer <key>`, singleton via `lru_cache`, fechado no evento
  `shutdown`. Métodos espelham 1:1 as rotas do `hermes-api`.

**Rotas por arquivo em `routers/`**:

| Arquivo | Prefixo | Rotas |
|---|---|---|
| `health.py` | — | `GET /health`, `GET /health/upstream` |
| `agents.py` | `/agents` | `GET ""`, `GET/PUT/DELETE /{agent_id}`, `POST ""`, `POST /{agent_id}/restart` |
| `skills.py` | `/agents/{id}/skills` | `GET`, `POST` |
| `knowledge.py` | `/agents/{id}/knowledge` | `GET`, `POST`, `POST /upload` |
| `calendar.py` | `/agents/{id}/calendar` | `GET/POST /connect`, `GET /connect/auth-url`, `POST /connect/auth-code`, `POST /schedule` |
| `followup.py` | `/agents/{id}/followup` | `GET`, `POST`, `DELETE /{job_id}` |
| `contacts.py` | `/agents/{id}/contacts` | `GET`, `GET/POST/DELETE /{phone}` |
| `memory.py` | `/agents/{id}/memory` | `GET/POST /{contact_uid}` |
| `channels.py` | `/agents/{id}/channels/whatsapp` | `GET`, `POST`, `GET /qr`, `DELETE` |
| `observability.py` | `/agents/{id}` | `GET /logs`, `GET /runs` |

**Modelos** (`models/*.py`): réplicas em arquivos próprios dos schemas Pydantic
embutidos no `app.py` do `hermes-api` — `CreateAgentRequest`/`UpdateAgentRequest`,
`CalendarEventRequest`, `GoogleOAuthClientDetails`, `CalendarClientSecretRequest`,
`CalendarAuthCodeRequest`, `ContactRequest`, `FollowupRequest`,
`KnowledgeUrlRequest`, `WriteMemoryRequest`, `SkillsRequest`.

**Packaging**: `Dockerfile` (Python 3.13-slim, expõe 8000), compose de produção
com Traefik (roteamento `hermes-api.vya.digital`, TLS Let's Encrypt, HSTS, CORS
restrito a `https://hermes-api.vya.digital`).

## Fluxo de Comunicação Entre os Módulos

1. **`app-vya-digital` → `vyadigital_api`**: via `lib/vya_api_client.py`, HTTP para
   `VYA_API_BASE_URL` (default `http://hermes-interaction-api:8000`), prefixo
   `/api/v1`; usado só para `restart_agent` e `whatsapp_status/connect/disconnect/qr`.
2. **`vyadigital_api` → `hermes-api`**: via `clients/vya_client.py`, HTTP para
   `VYA_API_BASE_URL` (default `http://vya-workforce-api:8700`), rotas cruas
   `/agents/...`.
3. **`app-vya-digital` não fala diretamente com o `hermes-api`** — só indiretamente
   via `vyadigital_api`. Toda leitura de dados de negócio (conversas, leads, agenda,
   produto) é feita lendo o volume compartilhado, não por chamada de API.
4. Os três serviços compartilham a mesma credencial `VYA_API_KEY`.

## Decisões Arquiteturais

Nenhum ADR formal foi encontrado para estas decisões — candidatos a registrar em
`docs/decisions/` caso o time queira formalizar:

- Separação em 3 serviços HTTP (em vez de monólito) com comunicação por volume de
  disco + HTTP, não por biblioteca Python compartilhada.
- `hermes-api` como único serviço com permissão de mutar o filesystem de perfis
  ("plano de controle"); `app-vya-digital` só lê o volume e escreve arquivos de
  configuração de negócio (não específicos do agente).

## Qualidade e Não-Funcionais

- **Persistência**: majoritariamente arquivo-baseada (`.env`, `.md`, `.yaml`, `.json`
  com escrita atômica tmp+`os.replace`, e SQLite por perfil) — não há banco de
  dados relacional único; cada `profiles/<id>/` é a unidade de isolamento.
- **Padrões arquiteturais**: nenhum dos três módulos segue DDD/camadas formais
  (Presentation/Application/Domain/Infrastructure). São scripts organizados por
  recurso (routers/handlers + módulos utilitários "flat"), sem repositórios/serviços
  como camadas explícitas — diverge do padrão mínimo de arquitetura definido no
  `CLAUDE.md` do usuário para projetos novos; vale avaliar se um refactor estrutural
  faz sentido ou se o padrão atual é aceito como legado.
- **Segurança**: `.env` e segredos (`VYA_API_KEY`) **não estão versionados** — o
  `.gitignore` do repositório cobre `.env`, `.env.*` e `secrets/` corretamente
  (verificado via `git ls-files`). O agente de exploração inicial sinalizou isso
  como risco por observar os arquivos no disco, mas o histórico do git não os
  contém — falso positivo, sem ação necessária.

## Riscos e Dívida Técnica Identificados

- **Duplicação de lógica de filesystem** entre `app-vya-digital/server.py`
  (funções `_gateway_state`, `_safe_profile_path`, `_write_atomic`,
  `_read_base_file`) e `hermes_agent/hermes-api/server/hermes_fs.py` — código
  comentado explicitamente com marcadores `# SYNC:`, pois os dois serviços têm
  build contexts Docker isolados e não compartilham módulo Python. Referenciado em
  `docs/bugs/2026-07-22_duplicidade-app-vya-digital.md` (hardening de path
  aparentemente não retroportado entre os dois lados).
- **Duplicação de schemas Pydantic** entre `hermes-api/server/app.py` (inline) e
  `vyadigital_api/models/*.py` (arquivos separados) — mesma forma, implementações
  independentes; risco de drift se um dos dois evoluir sem o outro.
- **Nomenclatura inconsistente** em `vyadigital_api`: diretório chama-se
  `vyadigital_api`, mas o pacote Python interno chama-se `docker_api` — pode
  confundir quem só olha `Dockerfile`/`main.py`.
- **Rotas não portadas** no dashboard (`app-vya-digital`) em relação ao projeto
  original: group/members, contact/avatar, contact/pause/resume,
  suspend/resume, db/tables/table/query.
- **Pendência funcional**: plugin `whatsapp-mixed` (auto-flush de mensagens após
  silêncio) está marcado como "🔶 em validação" — falta confirmar comportamento
  em produção.
- **Race condition documentada** em `handle_contact_delete` (`app-vya-digital`):
  não há mais mecanismo de sinalizar o gateway porque roda em outro
  container/namespace de PID.

## Ver também

- [decisions/](../decisions/) — ADRs (nenhum ainda cobre estas decisões)
- [bugs/2026-07-22_duplicidade-app-vya-digital.md](../bugs/) — detalhe da
  duplicação de lógica de filesystem, se o arquivo existir
