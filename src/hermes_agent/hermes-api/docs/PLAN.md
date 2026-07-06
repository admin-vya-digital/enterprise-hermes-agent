# Plano — POC Vya Digital Workforce sobre Hermes

> **Repositório:** TODO o código vive dentro de
> `/home/praxislatina/.hermes/project-vya-workforce/` — é o **repositório final** que será
> entregue. Deve ser **auto-contido**: nada de depender de `~/Code/hermes-dash` em runtime;
> os helpers reaproveitados são **portados (copiados)** para dentro do repo.

---

## Context

A Vya quer validar (POC) o uso do **Hermes** como motor de execução de agentes
inteligentes, controlando **todo o ciclo de vida do agente por REST API** (operado via
Postman, sem frontend). O agente-alvo é um SDR comercial: tem identidade própria, segue
instruções de atendimento, consulta base de conhecimento, conversa com leads no WhatsApp,
qualifica o lead, agenda reunião e faz follow-up automático.

A exploração do `.hermes` mostrou que **6 das 7 capacidades já existem** com boa
maturidade; o que falta é uma **camada REST estável e desacoplada** (adapter) que entregue
o contrato de endpoints do doc e amarre as peças. Decisões que guiam o plano:

1. **Arquitetura:** novo serviço dedicado `vya-workforce-api` (não estender o hermes-dash).
2. **Base de conhecimento:** abordagem por arquivo + consulta sob demanda (sem RAG/vetores).
3. **Escopo:** caminho crítico ponta-a-ponta; os 18 endpoints existem (núcleo funcional,
   secundários como stub/somente-leitura).
4. **Prioridade (crítico):** o foco desta entrega é o **framework de criação e manutenção
   de agentes** — o **plano de configuração/gestão**, todo via API. **Conversar com o
   agente não importa agora** (nem WhatsApp, nem canal REST `/v1/runs`): a validação é que
   cada configuração seja aplicada e persistida corretamente, não que o agente responda.
   O **WhatsApp e qualquer canal de conversa são as últimas etapas**, fora do caminho
   crítico.
5. **CRUD completo via Postman:** o ciclo de vida do agente — **criação, edição e
   deleção** — deve ser 100% operável pelo Postman, de ponta a ponta. A **única exceção
   tolerada** (a discutir depois) é o **scan do QRCode** na conexão WhatsApp, por ser um
   ato humano inerente.
6. **Repositório auto-contido** em `project-vya-workforce/` (ver bloco acima).
7. **Plano de controle é código puro — NUNCA aciona a IA Host.** Nenhuma operação de gestão
   (criar/editar/deletar/configurar agente) pode invocar a LLM nem o agente **Root** que
   provisiona perfis conversando — isso é o **projeto passado** (o Hermes Root
   multi-tenant). Aqui, todas as operações são **Python determinístico**: `mkdir`, escrever
   arquivos, symlink, `subprocess` para iniciar/parar processos, `kill` por PID. Os skills
   `whatsapp-profiles` (`create-profile`/`edit-profile`/`delete-profile`) são **apenas
   referência da sequência de passos** — serão **reimplementados em código**, não
   executados por um agente. A única LLM que roda é a **do próprio agente provisionado**,
   e só quando ele conversa (Fase 5) — fora do plano de controle.

---

## Arquitetura alvo

Um único serviço **`vya-workforce-api`**, **versionado dentro de
`project-vya-workforce/`** (FastAPI, executado pelo venv do Hermes que já tem FastAPI —
`~/.hermes/hermes-agent/venv`, via `start.sh`), expõe o contrato estável do doc e **delega**
para a infra existente. "Agente" = **perfil** Hermes (`~/.hermes/profiles/<id>/`). Os
helpers de leitura são **portados** para o repo (auto-contido).

```
Postman ──HTTP──▶  vya-workforce-api  (FastAPI, :8700, Bearer auth, OpenAPI/Swagger)
                    (em project-vya-workforce/server/)
                        │
   POST /agents ........├─▶ provisionador determinístico (código; deriva do create-profile)
   GET/PUT/DELETE ......├─▶ leitura: helpers portados de hermes-dash/server.py
   /knowledge .........├─▶ extrai texto → grava profiles/<id>/knowledge/*.md
   /skills ............├─▶ habilita/lista toolsets no config do perfil
   /channels/whatsapp .├─▶ bridge + QR  (ÚLTIMA etapa)
   /calendar ..........├─▶ google-workspace/scripts/google_api.py (calendar)
   /messages, /runs ...├─▶ Hermes api_server :8642 (/v1/runs, /api/sessions) — só leitura
   /followup ..........├─▶ Hermes api_server /api/jobs (cron) + script detector-de-silêncio
   /memory ............├─▶ read: memories/contacts/<uid>/*.md ; write: memory_tool
   /logs ..............└─▶ profiles/<id>/logs/*.log
```

O `vya-workforce-api` é um **plano de controle (control plane)**: cria, configura e mantém
perfis Hermes por API com **código determinístico**, **sem invocar a IA Host** (nem LLM, nem
agente Root) e **sem precisar conversar com o agente**. Toda operação é manipulação direta
de arquivos/processos do perfil. A validação é de configuração (arquivos escritos, estado
do perfil, endpoints `GET` retornando o estado correto), não de diálogo nem de "o agente
fez".

Plataformas de **conversa** ficam **fora do caminho crítico**:
- **`api_server`** (`gateway/platforms/api_server.py`) e **`whatsapp`** só entram nas
  etapas finais, quando/se for preciso exercitar o agente falando. O monitoramento de
  execução (`/runs`, `/logs`) não exige conversa — lê `state.db`/logs do perfil.

---

## Mapa do contrato (18 endpoints → implementação)

| Endpoint do doc | Implementação no adapter | Backing existente | Status |
|---|---|---|---|
| `POST /agents` | **código** que cria o perfil (dirs, `.env`, symlink `config.yaml`, replica chaves, SOUL/produto template) — sem LLM/agente | passos **reimplementados** de `create-profile/SKILL.md` (referência, não execução) | **núcleo** |
| `GET /agents`, `GET /agents/{id}` | descobre perfis + estado derivado dos arquivos | padrão `hermes-dash/server.py:handle_profiles/overview` | **núcleo** |
| `PUT /agents/{id}` | edita SOUL/produto/.env/modelo + restart escopado (se runtime viva) | `handle_set_soul/produto` + lógica `edit-profile` | **núcleo** |
| `DELETE /agents/{id}` | mata processos por PID + remove diretório | `skills/.../delete-profile` (reimplementado) | núcleo |
| `POST /knowledge`, `POST /knowledge/upload` | extrai texto (PDF/DOCX/URL/MD) → `profiles/<id>/knowledge/*.md`; injeta regra no SOUL | python-docx/pypdf + SOUL edit | **núcleo** |
| `POST /skills` | liga/desliga toolsets no `config`/`.env` do perfil | `api_server /v1/toolsets`, `hermes_cli/tools_config.py` | stub→núcleo |
| `POST /channels/whatsapp` (+ `/qr`) | sobe bridge, gera/serve QR, valida creds pós-scan | QR endpoints `hermes-dash` + bridge | etapa final |
| `POST /calendar/connect` | status/refresh OAuth Google | `google_token.json` já existe | núcleo (config) |
| `POST /calendar/schedule` | configura/dispara criação de evento (+ `htmlLink`) | `google-workspace/scripts/google_api.py calendar create` | núcleo |
| `POST /messages/send` | envia mensagem ao contato | bridge HTTP `/send` ou MCP `messages_send` | **secundário/stub** (conversa) |
| `GET /messages/history` | histórico por sessão/contato | `api_server /api/sessions/{id}/messages` ou `state.db` | leitura |
| `POST /followup` | cria cron job + registra detector de silêncio | `api_server /api/jobs` (POST/PATCH/run) | **núcleo (config)** |
| `GET /memory`, `POST /memory` | lê/escreve memória por contato | `memories/contacts/<uid>/*.md` + `tools/memory_tool.py` | núcleo |
| `GET /logs` | tail de logs do perfil | `profiles/<id>/logs/*.log` | leitura |
| `GET /runs` | lista execuções/eventos (sessões + cron) | `api_server /v1/runs`, `state.db sessions` | núcleo (observabilidade) |

---

## Plano de execução (fases — foco: framework de configuração/manutenção)

### Fase 0 — Esqueleto do serviço
- Criar a estrutura `server/` dentro de `project-vya-workforce/` (`app.py`, `start.sh` que
  usa o venv do Hermes, `README.md`).
- FastAPI + auth Bearer (header `Authorization: Bearer <VYA_API_KEY>`), Swagger em `/docs`.
- Portar para `hermes_fs.py` os helpers de leitura já provados no `hermes-dash/server.py`
  (descoberta de perfis, status por `gateway.pid`/`gateway_state.json`, `_bridge_port`,
  conexão `state.db` `?mode=ro`). **Reusar, não reescrever.**
- Coleção Postman versionada com todos os endpoints.

### Fase 1 — Ciclo de vida do agente por API ⬅ prioridade máxima
- **Provisionador determinístico** (`provision.py`): **reimplementa em Python** a parte
  determinística do `create-profile` (Phases 0–2, 4.4–4.5) — **sem invocar LLM/agente
  Root** e **pulando qualquer canal de conversa (bridge/QR e api_server)**: dirs isolados →
  `.env` (chaves replicadas do global, políticas) → symlink `config.yaml` →
  SOUL.md/produto.md a partir de template SDR. **Escrever a config NÃO sobe a runtime** do
  agente; iniciar/parar o gateway é uma ação de runtime **desacoplada** (só necessária
  quando for conectar um canal — Fase 5). O plano de controle valida pelos arquivos, não
  por processo vivo.
- **CRUD completo** (`lifecycle.py`), todo por Postman:
  - `POST /agents` — nome, descrição, objetivo, personalidade, idioma, modelo, temperatura,
    prompt inicial → escreve SOUL.md + `.env` + estrutura do perfil (código, sem LLM).
  - `GET /agents`, `GET /agents/{id}` — lista/estado **derivado dos arquivos** do perfil
    (config + se há runtime viva, opcional via `gateway.pid`).
  - `PUT /agents/{id}` — edição completa (persona, modelo, temperatura, políticas)
    reescrevendo os arquivos; se a runtime estiver de pé, restart escopado (regra do
    `edit-profile`, reimplementada em código).
  - `DELETE /agents/{id}` — deleção **completa**: se houver processos, mata por **PID**;
    remove o diretório do perfil e limpa estado — sem passo manual.
- **Critério da fase:** criar, listar, editar e **remover** um agente **inteiramente por
  Postman**, cada mudança refletida nos **arquivos do perfil**, sem acionar a IA Host e sem
  deixar processos órfãos/resíduos na deleção. Sem conversar com o agente.

### Fase 2 — Configuração de comportamento e conhecimento
- `PUT /agents/{id}` consolida edição de SOUL.md/produto.md/.env/modelo (restart escopado).
- `POST /knowledge[/upload]`: extração de texto (PDF/DOCX/URL/MD) → `profiles/<id>/knowledge/*.md`
  + injeção da regra de consulta no SOUL. `GET` confirma os arquivos gravados.
- `POST /skills`: liga/desliga toolsets no `config`/`.env` do perfil.
- `GET/POST /memory`: lê/escreve memória por contato (semear/inspecionar perfis de lead).
- **Critério:** todo o comportamento + base de conhecimento + skills configuráveis e
  verificáveis por API (estado persistido), sem diálogo.

### Fase 3 — Automação: Agenda + Follow-up (configuração)
- `POST /calendar/connect` (valida/refresca OAuth Google) e `POST /calendar/schedule`
  (cria evento real, devolve `htmlLink`).
- `POST /followup`: cria cron job (`api_server /api/jobs`) + script detector-de-silêncio
  (consulta `state.db`/memória pelo `last_message`; limita tentativas; encerra; padrão
  `[SILENT]`). Disparo manual via `/api/jobs/{id}/run` para validar sem esperar o cron.
- **Critério:** agendamento e follow-up configurados e disparáveis por API; resultado
  observável em `GET /runs`/`GET /logs`.

### Fase 4 — Observabilidade
- `GET /logs`, `GET /runs` (sessões + histórico de cron do `state.db`), status detalhado de
  agente. Fecha o requisito "monitorar todas as execuções e eventos via API".

### Fase 5 — Canais de conversa (etapa final, fora do caminho crítico)
- Só quando for preciso exercitar o agente falando: `POST /channels/whatsapp` (sobe bridge,
  QR/SSE reusando `hermes-dash`, valida creds pós-scan, health-check E2E) e/ou habilitar o
  `api_server` para chat REST. `POST /messages/send` + `GET /messages/history` passam a
  apontar para o canal ativo. Aqui sim valida-se o fluxo conversacional do diagrama.

---

## Arquivos a criar

**Repositório `~/.hermes/project-vya-workforce/` (entregável, auto-contido):**
```
project-vya-workforce/
├── docs/                       # Vya.Digital - Digital Workforce.docx + PLAN.md
├── server/
│   ├── app.py                  # FastAPI, rotas do contrato, auth Bearer, Swagger
│   ├── hermes_fs.py            # helpers de leitura PORTADOS do hermes-dash/server.py
│   ├── provision.py            # provisionamento determinístico de perfil (create)
│   ├── lifecycle.py            # edit + delete completos (restart escopado, kill por PID)
│   ├── knowledge.py            # extração de texto (PDF/DOCX/URL/MD)
│   ├── calendar.py             # wrapper de google_api.py calendar
│   └── followup.py             # criação de cron + script detector-de-silêncio
├── templates/                  # SOUL.sdr.md, produto.sdr.md
├── start.sh                    # usa o venv do Hermes
├── requirements.txt            # deps próprias (python-docx, pypdf, ...) p/ ser auto-contido
├── README.md                   # como subir + referência de endpoints
└── postman_collection.json     # coleção completa (create/edit/delete + tudo)
```

**Hermes (config, não patch de core):**
- Habilitar `platforms.api_server` por perfil (chave/host/porta no `.env` do perfil) —
  **somente na Fase 5/observabilidade**, nunca para acionar a IA pelo plano de controle.
  Preferir env do perfil para não quebrar o symlink global do `config.yaml`.

**Templates:**
- `templates/SOUL.sdr.md`, `templates/produto.sdr.md` (persona SDR + rubrica de
  qualificação + REGRA ZERO de isolamento, espelhando os perfis existentes).

---

## Reuso (não reinventar)

- Leitura de perfis/status/DB/logs/QR: `~/Code/hermes-dash/server.py`
  (`handle_profiles`, `handle_overview`, `_bridge_port`, `_db_connect`, QR/SSE,
  `handle_contact_memory`). **Portar** os helpers para `hermes_fs.py`.
- Runs/sessions/jobs (observabilidade/cron): `gateway/platforms/api_server.py` (`/v1/runs`,
  `/api/sessions/*`, `/api/jobs/*`) — leitura/escrita de jobs e leitura de runs; **não** é
  usado para acionar a IA pelo plano de controle.
- Provisionamento: `skills/whatsapp-profiles/create-profile/SKILL.md`,
  `delete-profile`, `edit-profile` são **referência da sequência de passos** —
  **reimplementados em código** (`provision.py`/`lifecycle.py`), **nunca executados por um
  agente**.
- Calendário: `skills/productivity/google-workspace/scripts/google_api.py` +
  `google_token.json`/`google_client_secret.json` já presentes.
- Memória: `tools/memory_tool.py` (write) e `memories/contacts/<safe_uid>/` (layout).
- Isolamento/operacional: `~/Code/hermes-dash/ARCHITECTURE.md` (fonte canônica) — manter
  invariantes (matar só por PID; `config.yaml` symlink; `BRIDGE_PORT` no `.env`).

---

## Riscos / notas

- **Provisionamento por API ≠ wizard:** o `create-profile` é interativo; a fase de QR é
  inerentemente assíncrona e humana. Por isso canais de conversa (WhatsApp/api_server)
  ficam na Fase 5 e o framework de configuração é 100% API das Fases 1–4.
- **Sem RAG:** conhecimento é arquivo + leitura sob demanda; suficiente para a POC, mas
  registrar como limitação conhecida (escala/precisão de recuperação).
- **Config ≠ runtime:** escrever/editar a config do perfil é código puro e **não** sobe a
  runtime do agente. Iniciar o gateway (runtime que carrega a LLM ao receber mensagem) só é
  necessário para conversar (Fase 5). O plano de controle não depende de processo vivo.
- **Sem IA Host no controle:** garantir que nenhuma rota de gestão chame `run_agent`,
  `/v1/runs` ou o agente Root. Revisar o código para que create/edit/delete/config sejam
  só filesystem + processos.
- **Qualificação/score** é lógica de prompt no SOUL.md, não feature nativa — escrever a
  rubrica explicitamente (entra na config, é exercitada só na Fase 5).

---

## Verificação (fluxo Postman — configuração/manutenção)

A validação é de **estado de configuração**, não de conversa: cada chamada deve refletir
nos arquivos do perfil e nos `GET` correspondentes.

1. `POST /agents` → cria perfil SDR (código, sem LLM); `GET /agents/{id}` mostra os campos
   configurados; inspecionar `profiles/<id>/{SOUL.md,produto.md,.env,config.yaml}`.
2. `PUT /agents/{id}` muda persona/modelo → `GET` e os arquivos refletem a mudança (se a
   runtime estiver de pé, restart no escopo certo).
3. `POST /knowledge/upload` envia PDF/DOCX/URL → `GET /knowledge` e o disco confirmam
   `profiles/<id>/knowledge/*.md`; a regra de consulta aparece no SOUL.
4. `POST /skills` liga/desliga toolset → refletido no config do perfil.
5. `POST /memory` semeia um perfil de lead → `GET /memory` lê de
   `memories/contacts/<uid>/*.md`.
6. `POST /calendar/connect` valida OAuth; `POST /calendar/schedule` cria evento real no
   Google Calendar (validar `htmlLink`).
7. `POST /followup` cria o cron job; `/api/jobs/{id}/run` dispara; `GET /runs`/`GET /logs`
   mostram a execução.
8. `DELETE /agents/{id}` remove o perfil (processos por PID + diretório).
9. **Só na etapa final (Fase 5), se desejado:** `POST /channels/whatsapp` → QR → exercitar
   o agente conversando e confirmar os critérios conversacionais do doc.

Health checks (do plano de controle, sem IA): arquivos do perfil consistentes e completos,
`GET` refletindo o que foi escrito, deleção sem órfãos nem resíduos. (Gateway vivo /
`os.kill(pid,0)` / `gateway_state.json` só são relevantes quando há runtime — Fase 5.)
