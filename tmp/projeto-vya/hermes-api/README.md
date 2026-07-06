# Vya Digital Workforce API

Plano de controle REST para agentes Hermes — criação, edição e manutenção de agentes via API.
Operado 100% pelo Postman ou qualquer cliente HTTP. **Nunca invoca LLM ou agente Root.**

Cada agente (perfil) é **100% self-contained**: provedor de LLM, chave de API e `config.yaml`
próprios — não há mais dependência de um `config.yaml`/provider global compartilhado entre agentes.

---

## Subir o servidor

```bash
export VYA_API_KEY=sua-chave-secreta
./start.sh
# → http://localhost:8700
# → Swagger: http://localhost:8700/docs
# → Swagger UI local: docs/swagger.html
```

Porta customizável: `VYA_PORT=9000 ./start.sh`

## Autenticação

Todas as rotas (exceto `/health`) exigem:
```
Authorization: Bearer <VYA_API_KEY>
```

---

## Endpoints

### Infra

#### `GET /health`
Verifica se o servidor está de pé.
- **Recebe:** nada
- **Retorna:** `{"status": "ok", "ts": <unix_timestamp>}`
- **Implementação:** resposta inline em `app.py`

---

### Agentes — `GET /agents`
Lista todos os perfis Hermes existentes.
- **Recebe:** nada
- **Retorna:** array de objetos de agente (ver schema abaixo)
- **Implementação:** `hermes_fs.list_profiles()` → itera `~/.hermes/profiles/`, chama `profile_status()` em cada um

#### `GET /agents/{agent_id}`
Retorna o estado completo de um agente lido dos arquivos do perfil.
- **Recebe:** `agent_id` na URL
- **Retorna:**
```json
{
  "id": "vya-sdr-01",
  "name": "SDR Vya",
  "description": "SDR digital para leads B2B",
  "objective": "Qualificar leads e agendar reuniões",
  "personality": "Consultivo e empático",
  "initial_prompt": "...",
  "model": "claude-haiku-4-5-20251001",
  "language": "pt-BR",
  "temperature": 0.5,
  "enabled_toolsets": ["web", "vision"],
  "knowledge_files": ["produto.md", "faq.md"],
  "bridge_port": 3100,
  "gateway_port": 8810,
  "whatsapp_enabled": false,
  "has_soul": true,
  "has_produto": true,
  "online": false,
  "pid": null,
  "gateway_state": "stopped",
  "whatsapp_state": "unknown",
  "updated_at": null
}
```
- **Implementação:** `hermes_fs.profile_info(d)` — lê `.env` (identidade, runtime, toolsets), conta `knowledge/`, chama `profile_status()` (lê `gateway.pid` + `gateway_state.json`)

#### `POST /agents`
Cria um novo agente de forma determinística, sem invocar LLM.
- **Recebe:**
```json
{
  "agent_id": "vya-sdr-01",             // obrigatório, único, só letras/números/hífens
  "name": "SDR Vya",                    // nome de exibição
  "description": "SDR digital...",      // 1-2 frases sobre o papel
  "objective": "Qualificar leads...",   // missão inserida no SOUL.md
  "personality": "Consultivo...",       // tom de comunicação
  "language": "pt-BR",                  // idioma (BCP-47)
  "model": "claude-haiku-4-5-20251001", // modelo de IA
  "temperature": 0.5,                   // criatividade 0.0-1.0
  "initial_prompt": "...",              // instrução extra no SOUL.md
  "provider": "anthropic",              // OBRIGATÓRIO — provedor de LLM deste agente
  "provider_api_key": "sk-ant-...",     // OBRIGATÓRIO — chave do provedor acima
  "whatsapp_mode": "bot",               // "bot" | "self-chat" | "mixed" (padrão: bot)
  "whatsapp_owner_number": ""           // obrigatório na prática se whatsapp_mode="mixed"
}
```
- **Retorna:** objeto completo do agente criado (201)
- **Implementação:** `provision.create_profile()` →
  1. Valida `agent_id` (regex `[\w\-]+`) e `whatsapp_mode` (enum)
  2. Aloca portas únicas (`_next_ports()` — lê todos os `.env` existentes)
  3. Cria estrutura de diretórios em `~/.hermes/profiles/<id>/`
  4. Gera `config.yaml` **próprio do perfil** (não symlink) com o `provider` escolhido
  5. Escreve `.env` com portas, modelo, idioma, campos de persona, chave do provider (mapeada
     para `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/etc.), `WHATSAPP_MODE`, `WHATSAPP_OWNER_NUMBER`
  6. Renderiza `SOUL.md` de `templates/SOUL.sdr.md` substituindo `{{NAME}}`, `{{PERSONALITY}}` etc.
  7. Renderiza `produto.md` de `templates/produto.sdr.md`
  8. Symlink `skills/` → `~/.hermes/skills/` (único symlink compartilhado que resta — toolsets, não config)
  9. Instala o plugin `whatsapp-mixed` em `~/.hermes/plugins/` (global, idempotente entre perfis —
     o Hermes só descobre plugins de usuário nesse diretório, não em `<profile>/plugins/`) e o
     habilita via `plugins.enabled` no `config.yaml` **deste perfil**. Sempre feito, mesmo que
     `whatsapp_mode != "mixed"` — o plugin faz early-return e não interfere nos modos `bot`/`self-chat`;
     assim, um `PUT` que troque o modo pra `"mixed"` depois já funciona sem reprovisionar nada
  10. Se `whatsapp_owner_number` informado, espelha automaticamente um contato `contact_type: "owner"`

> **`default-profile` é protegido** — existe como template base e **não pode ser deletado** via API (403).

#### `PUT /agents/{agent_id}`
Edita campos do agente. Só os campos enviados são alterados.
- **Recebe:** qualquer subconjunto dos campos do POST (exceto `agent_id`), incluindo `provider`,
  `provider_api_key`, `whatsapp_mode`, `whatsapp_owner_number`
- **Retorna:** objeto completo do agente atualizado
- **Implementação:** `lifecycle.update_profile()` →
  1. Se gateway estiver rodando (`gateway.pid` + `os.kill(pid,0)`), para por SIGTERM→SIGKILL
  2. Atualiza os campos no `.env` (fonte de verdade para persona) e, se `provider` mudar, reescreve o `config.yaml` do perfil
  3. Re-renderiza `SOUL.md` do template preservando a seção `## [CONSULTA DE CONHECIMENTO]` já injetada
  4. Escreve `.env` atomicamente (write tmp → rename)
  5. Garante o plugin `whatsapp-mixed` instalado globalmente e habilitado no `config.yaml` deste
     perfil (idempotente — cobre perfis criados antes desta feature); espelha o contato `owner`
     se `whatsapp_owner_number` mudou
  6. Se estava rodando, reinicia o gateway (`hermes gateway run --replace`)

#### `DELETE /agents/{agent_id}`
Remove o agente completamente, sem deixar resíduos.
- **Recebe:** `agent_id` na URL
- **Retorna:** 204 sem body (403 se `agent_id == "default-profile"`)
- **Implementação:** `lifecycle.delete_profile()` →
  1. Para gateway: lê `gateway.pid`, SIGTERM → espera 4s → SIGKILL se ainda vivo
  2. Para bridge: lê `bridge.pid`, mesmo fluxo
  3. `shutil.rmtree(~/.hermes/profiles/<id>/)`

---

### Conhecimento — `GET /agents/{id}/knowledge`
Lista arquivos de conhecimento do agente.
- **Retorna:** array com `name`, `size`, `modified_at` de cada `.md` em `profiles/<id>/knowledge/`
- **Implementação:** `hermes_fs.list_knowledge(d)`

#### `POST /agents/{id}/knowledge`
Adiciona conhecimento a partir de uma URL.
- **Recebe:** `{"url": "https://...", "filename": "nome-base"}`
- **Retorna:** `{"saved": "nome-base.md", "size": <bytes>}`
- **Implementação:** `knowledge.extract_text(url)` → `urllib.request` + strip HTML → `save_knowledge()` → `inject_knowledge_rule()` atualiza `## [CONSULTA DE CONHECIMENTO]` no SOUL.md

#### `POST /agents/{id}/knowledge/upload`
Upload de arquivo (PDF, DOCX, MD, TXT).
- **Recebe:** `multipart/form-data` com campo `file`
- **Retorna:** `{"saved": "<nome>.md", "size": <bytes>}`
- **Implementação:**
  - PDF → `pypdf.PdfReader` extrai texto de todas as páginas
  - DOCX → `docx.Document` extrai parágrafos
  - MD/TXT → salvo direto
  - Após salvar: `inject_knowledge_rule()` reescreve a seção no SOUL.md listando todos os arquivos presentes

---

### Skills — `GET /agents/{id}/skills`
Lista todos os toolsets disponíveis com estado enabled/disabled para este agente.
- **Retorna:** array com `name`, `description`, `tools[]`, `enabled`
- **Implementação:** `skills.list_skills(d)` → importa `TOOLSETS` do `hermes-agent/toolsets.py` (mesmo venv), cruza com `ENABLED_TOOLSETS` do `.env` do perfil. Omite toolsets compostos `hermes-*`.

#### `POST /agents/{id}/skills`
Habilita ou desabilita toolsets.
- **Recebe:** `{"enable": ["web", "vision"], "disable": ["image_gen"]}`
- **Retorna:** lista completa de toolsets com novo estado
- **Implementação:** `skills.set_skills(d, enable, disable)` → valida nomes contra `TOOLSETS`, atualiza `ENABLED_TOOLSETS` no `.env` atomicamente

> **Nota:** estado é lógico — persiste no `.env` e fica disponível como configuração quando o gateway for iniciado.

---

### Canais — WhatsApp — `GET /agents/{id}/channels/whatsapp`
Status do canal WhatsApp do agente.
- **Retorna:** `{"phase": "disconnected|pairing|paired_not_running|starting|connected", "paired": bool, "jid": str|null, "bridge_pid": int|null, "gateway_pid": int|null, "whatsapp_state": str}`
- **Implementação:** `whatsapp.get_status(d)` — lê `session/creds.json` (paired + `jid` via `me.id`), `bridge.pid`/`gateway.pid`, `gateway_state.json`

#### `POST /agents/{id}/channels/whatsapp`
Conecta o WhatsApp — idempotente, único passo humano de todo o control plane (o scan do QR).
- **Recebe:** nada
- **Retorna:** o mesmo shape do `GET` acima
- **Comportamento:**
  - Nunca pareado → sobe `node bridge.js --pair-only` em background (gera QR de forma assíncrona)
  - Já pareado → garante `WHATSAPP_ENABLED=true`, sobe o gateway (reconecta com credenciais salvas,
    sem QR) e configura o WhatsApp como **home channel** (`hermes channel set --id whatsapp://<owner>`)
    — necessário para que follow-ups e mensagens cross-platform tenham para onde entregar
  - Pareamento em andamento → no-op, retorna estado atual
- **Implementação:** `whatsapp.connect(d)` → `_set_home_channel(d)` roda logo após subir o gateway
  (usa `WHATSAPP_OWNER_NUMBER` do `.env`; no-op se não estiver definido)

#### `GET /agents/{id}/channels/whatsapp/qr`
Retorna o QR atual como **imagem PNG real** (`Content-Type: image/png`) — não é base64/JSON.
- **Retorna:** bytes PNG, ou 404 se ainda não gerado / já pareado
- **Implementação:** `whatsapp.get_qr_png(d)` — converte o payload de texto do Baileys (`qr/qr-connect.txt`) em PNG via lib `qrcode`, sob demanda

#### `DELETE /agents/{id}/channels/whatsapp`
Desconecta o WhatsApp.
- **Query params:** `forget=true` também apaga a sessão salva (força novo QR na próxima conexão)
- **Implementação:** `whatsapp.disconnect(d, forget)` — para bridge + gateway por PID

---

### Contatos — `GET /agents/{id}/contacts`
Lista todos os contatos classificados deste agente.
- **Retorna:** array de `{"phone", "contact_type", "name"?, "notes"?, "created_at", "updated_at"}`
- **Implementação:** `contacts.list_contacts(d)` — lê `profiles/<id>/contacts/*.json`

#### `GET /agents/{id}/contacts/{phone}`
Lê um contato específico. `phone` é E.164 sem `+` (ex: `5511999999999`).

#### `POST /agents/{id}/contacts/{phone}`
Cria/atualiza a classificação de um contato.
- **Recebe:** `{"contact_type": "cliente", "name": "João Silva", "notes": "Lead quente"}`
- **`contact_type` aceita apenas `owner` ou `cliente`** (422 se outro valor)
- **Implementação:** `contacts.set_contact()` — write atômico com lock (`hermes_fs.locked_json`)
- O contato `owner` normalmente **não precisa ser criado manualmente** — é espelhado automaticamente quando `whatsapp_owner_number` é definido em `POST`/`PUT /agents`

#### `DELETE /agents/{id}/contacts/{phone}`
Remove a classificação de um contato.

> Ver `~/.hermes/skills/whatsapp-profiles/create-contact-type/SKILL.md` para o passo a passo de referência.

---

### Plugin `whatsapp-mixed` (WHATSAPP_MODE=mixed)

Quando um agente é criado/editado com `whatsapp_mode: "mixed"`, o mesmo número WhatsApp atende
**o dono** (assistente pessoal, self-chat) **e clientes** (bot) ao mesmo tempo. O roteamento é
feito por um plugin Hermes real (hook `pre_gateway_dispatch`) — **não** depende de patch no
`bridge.js`/`whatsapp.py` compartilhados além de uma extensão mínima e aditiva (nova branch de
modo + campo `fromMe` no evento).

**Instalação (automática, todo perfil, independente do modo):** o Hermes só descobre plugins de
usuário em `~/.hermes/plugins/<nome>/` — um plugin copiado apenas em `<profile>/plugins/` **não é
carregado**. Por isso `provision.py`/`lifecycle.py` instalam o `whatsapp-mixed` uma única vez no
diretório global (idempotente entre perfis) e habilitam-no via `plugins.enabled` no `config.yaml`
de **cada** perfil — plugins de usuário são opt-in por padrão no Hermes, então essa chave é
obrigatória mesmo com o plugin já instalado. Isso acontece em todo `POST`/`PUT /agents`,
independente de `whatsapp_mode`: o plugin faz early-return e não interfere nos modos `bot`/
`self-chat`, então trocar o modo pra `"mixed"` depois via `PUT` já funciona sem reprovisionar nada.

Regras do plugin:
1. Dono conversando consigo mesmo (self-chat) → processa normal.
2. Dono responde manualmente um cliente → **silencia** aquele chat por 10 min (janela deslizante:
   cada nova mensagem do dono reseta o timer), pula o LLM, e agenda/reagenda um **cron job
   one-shot** por chat (ver "Auto-flush" abaixo).
3. Cliente manda mensagem durante o silêncio → grava em arquivo (`contacts/_silence/<chat>.json`,
   protegido por `flock`) e pula — sobrevive a restart do gateway, nada se perde.
4. Cliente manda mensagem **depois** que o silêncio já expirou → checa o arquivo de pendências;
   se houver, funde no texto atual (agente responde ao que ficou acumulado); se não houver nada,
   segue a vida normalmente.

**Auto-flush ao expirar o silêncio (sem depender de nova mensagem do cliente):** o sistema de
plugins do Hermes não tem nenhum hook periódico — um plugin só roda reagindo a eventos, nunca
"acorda sozinho" por tempo. Por isso, toda vez que o dono silencia um chat (regra 2), o plugin
agenda um job no cron **do próprio perfil** (mesmo mecanismo do `POST /agents/{id}/followup`),
programado para o instante exato em que o silêncio expira:
- O job roda um script (`~/.hermes/profiles/<id>/scripts/whatsapp_mixed_flush_<chat>.py`,
  gerado automaticamente) que esvazia o arquivo de pendências daquele chat no momento do disparo
  (sempre atual — nunca há uma foto congelada do agendamento)
- Se havia mensagens pendentes, o conteúdo vira contexto do prompt e o agente responde,
  entregando direto pro cliente via `deliver: "whatsapp:<chat_id>"`
- Se não havia nada pendente na hora, o script não imprime nada e o job é pulado **sem** chamar
  o LLM (`cron/scheduler.py`: "script produced no output — skip AI call")
- Reagendar (em vez de criar um job novo a cada mensagem do dono) evita jobs duplicados por chat
  — o nome do job é determinístico (`whatsapp-mixed-flush-<chat_sanitizado>`) e é
  atualizado (`update_job`) se já existir, criado (`create_job`) caso contrário

---

### Calendário — `GET /agents/{id}/calendar/connect`
Verifica o status OAuth do Google Calendar **deste perfil**.
- **Retorna:** `{"connected": true, "has_refresh_token": true, "token_file": "..."}`
- **Implementação:** `calendar_wrap.calendar_status(d)` — verifica existência e estrutura de
  `profiles/<id>/google_token.json`/`google_client_secret.json`. Cada agente tem sua própria
  conexão Google — não há mais token compartilhado globalmente.
- `connected: true` só confirma que os arquivos existem e têm `refresh_token` — não valida o
  token ao vivo contra o Google (isso só é verificado na hora de criar um evento de verdade).

**Fluxo completo de conexão (4 passos):**

#### 1. `POST /agents/{id}/calendar/connect`
Salva as credenciais do app OAuth para este perfil.
- **Recebe:** exatamente o JSON que o Google Cloud Console entrega ao criar um OAuth Client ID
  (**APIs & Services → Credentials → Create Credentials → OAuth client ID → Desktop app** →
  botão de download) — chave `installed` ou `web` na raiz, **sem wrapper**:
```json
{
  "installed": {
    "client_id": "SEU_CLIENT_ID.apps.googleusercontent.com",
    "project_id": "seu-projeto-google-cloud",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "SEU_CLIENT_SECRET",
    "redirect_uris": ["http://localhost"]
  }
}
```
- **Retorna:** status atual (mesmo shape do `GET`)
- **Implementação:** `calendar_wrap.calendar_store_client_secret(d, body)` — grava
  `profiles/<id>/google_client_secret.json`
- **Nota:** o nome exibido na tela de consentimento OAuth vem da config do **projeto** Google
  Cloud (OAuth consent screen), não do Client ID — reutilizar o mesmo projeto para criar um
  Client ID novo mantém o mesmo nome exibido

#### 2. `GET /agents/{id}/calendar/connect/auth-url`
Gera a URL de consentimento OAuth para este perfil.
- **Retorna:** `{"auth_url": "https://accounts.google.com/o/oauth2/auth?..."}`
- **Passo humano:** abra a URL no navegador, faça login com a conta Google desejada e aceite
  as permissões. Você será redirecionado para `http://localhost/?code=...` (a página vai dar
  erro de conexão — é esperado, não sobe nada em `localhost`); copie o `code` da barra de
  endereço (ou a URL inteira)
- **Implementação:** `calendar_wrap.calendar_auth_url(d)` → roda
  `setup.py --auth-url` com `HERMES_HOME=<profile_dir>`

#### 3. `POST /agents/{id}/calendar/connect/auth-code`
Troca o código de autorização pelo token OAuth deste perfil.
- **Recebe:** `{"code": "4/0Adeu5B..."}` (aceita o código puro ou a URL de callback inteira)
- **Retorna:** status atual — `connected: true` se tudo deu certo
- **Implementação:** `calendar_wrap.calendar_exchange_code(d, code)` → roda
  `setup.py --auth-code CODE` com `HERMES_HOME=<profile_dir>`, salva `google_token.json`

#### 4. `POST /agents/{id}/calendar/schedule`
Cria um evento real no Google Calendar.
- **Recebe:**
```json
{
  "summary": "Reunião de apresentação",
  "start": "2026-07-10T14:00:00-03:00",
  "end": "2026-07-10T15:00:00-03:00",
  "location": "https://meet.google.com/...",
  "description": "Demo do produto",
  "attendees": "lead@empresa.com,vendas@vya.digital",
  "calendar": "primary"
}
```
- **Retorna:** `{"status": "created", "id": "...", "htmlLink": "https://calendar.google.com/..."}`
- **Implementação:** `calendar_wrap.calendar_create_event()` → chama via `subprocess` o script `~/.hermes/skills/productivity/google-workspace/scripts/google_api.py calendar create` com os argumentos, captura stdout JSON

---

### Follow-up — `GET /agents/{id}/followup`
Lista jobs de follow-up criados para este agente.
- **Retorna:** array de jobs em `profiles/<id>/cron/jobs.json`
- **Implementação:** `followup.list_followups(d, agent_id)`

#### `POST /agents/{id}/followup`
Cria um job de follow-up automático no cron **do perfil** (não global).
- **Recebe:**
```json
{
  "name": "Follow-up João Silva",
  "schedule": "2h",       // ou "0 9 * * *" ou "2026-07-12T09:00:00"
  "prompt": "Envie follow-up para 5511999999999...",
  "repeat": 3             // máximo de execuções (opcional)
}
```
- **Retorna:** objeto do job criado com `id`, `schedule`, `state`, `created_at`
- **Implementação:** `followup.create_followup()` → gera `id` (hex 6 bytes), converte schedule para `{kind, expr/minutes/run_at}`, escreve atomicamente (com lock) em `profiles/<id>/cron/jobs.json` — o **mesmo caminho que o scheduler do próprio gateway do perfil lê** via `HERMES_HOME`. O scheduler executa quando o gateway do agente estiver ativo.

#### `DELETE /agents/{id}/followup/{job_id}`
Remove um job de follow-up.
- **Retorna:** 204

---

### Memória — `GET /agents/{id}/memory/{contact_uid}`
Lê arquivos de memória de um contato.
- `contact_uid`: número E.164 sem `+`, ex: `5511999999999`
- **Retorna:** array com `name`, `content`, `modified_at` de cada arquivo em `profiles/<id>/memories/contacts/<uid>/`
- **Implementação:** `hermes_fs.list_contact_memories(d, contact_uid)` — **por-perfil**, o mesmo caminho que o `tools/memory_tool.py` do gateway lê via `HERMES_HOME` (isolamento entre agentes garantido — o mesmo telefone pode ter memórias diferentes em agentes diferentes)

#### `POST /agents/{id}/memory/{contact_uid}`
Grava um arquivo de memória para o contato.
- **Recebe:** `{"filename": "perfil.md", "content": "# Lead\n- Nome: João..."}`
- **Retorna:** `{"saved": "<path>", "size": <bytes>}`
- **Implementação:** cria `profiles/<id>/memories/contacts/<uid>/<filename>`. O agente consulta esses arquivos automaticamente em conversas futuras com o contato.

---

### Observabilidade — `GET /agents/{id}/logs`
Retorna as últimas linhas de um log do perfil.
- **Query params:** `source` (gateway|bridge|errors|agent, padrão: gateway), `lines` (padrão: 100)
- **Retorna:** `{"source": "gateway", "lines": [...]}`
- **Implementação:** `hermes_fs.tail_log(d, source, lines)` → `subprocess tail -n <lines> profiles/<id>/logs/<source>.log`

#### `GET /agents/{id}/runs`
Lista sessões de conversa e execuções de cron.
- **Query params:** `limit` (padrão: 50)
- **Retorna:** array de sessões do `state.db` com `id`, `source`, `user_id`, `started_at`, `ended_at`, `message_count`, `input_tokens`, `output_tokens`, `estimated_cost_usd`
- **Implementação:** `hermes_fs.list_runs(d, limit)` → `SELECT` no `state.db` do perfil em modo read-only (`?mode=ro`)

---

## Estrutura do projeto

```
project-vya-workforce/
├── server/
│   ├── app.py            FastAPI: rotas, schemas Pydantic, auth Bearer, CORS, Swagger
│   ├── hermes_fs.py       Helpers de leitura do filesystem do Hermes + locked_json (flock)
│   ├── provision.py       Criação determinística do perfil (dirs, .env, config.yaml próprio,
│   │                      SOUL.md, symlink skills/, instala plugin whatsapp-mixed)
│   ├── lifecycle.py        Edição (re-render SOUL, troca provider/whatsapp_mode) + deleção
│   │                      (kill por PID + rmtree; protege default-profile)
│   ├── knowledge.py        Extração de texto: PDF (pypdf), DOCX (python-docx), URL, MD
│   ├── skills.py           Enable/disable toolsets via ENABLED_TOOLSETS no .env
│   ├── calendar_wrap.py    Wrapper subprocess para google_api.py calendar create
│   ├── followup.py         CRUD de jobs em profiles/<id>/cron/jobs.json (por-perfil)
│   ├── contacts.py         Perfis de contato (contact_type: owner | cliente)
│   └── whatsapp.py         Conexão do canal: pareamento assíncrono, QR→PNG, status, disconnect
├── templates/
│   ├── SOUL.sdr.md         Template de persona ({{NAME}}, {{PERSONALITY}} etc.)
│   ├── produto.sdr.md      Template de portfólio/serviços
│   └── plugins/
│       └── whatsapp-mixed/ Plugin Hermes (hook pre_gateway_dispatch) — fonte para instalação
│           │                global; ver seção "Plugin whatsapp-mixed" acima
│           ├── plugin.yaml
│           └── __init__.py
├── docs/
│   ├── PLAN.md             Plano de execução completo
│   ├── swagger.html        Swagger UI standalone (aponta para :8700)
│   └── Vya.Digital - Digital Workforce.docx
├── start.sh                Inicia via venv do Hermes (~/.hermes/hermes-agent/venv)
├── requirements.txt        pypdf, python-docx, qrcode (resto já está no venv do Hermes)
└── postman_collection.json
```

Skills de referência (fora deste repo, em `~/.hermes/skills/whatsapp-profiles/`):
`create-profile`, `edit-profile`, `delete-profile` (sequência manual original — reimplementada
em código aqui) e `create-contact-type` (classificação `owner`/`cliente`).

## Fases

| Fase | Status | Escopo |
|------|--------|--------|
| 0 — Esqueleto | ✅ | FastAPI, auth, Swagger, helpers portados, Postman |
| 1 — Ciclo de vida | ✅ | POST/GET/PUT/DELETE /agents, provider/config self-contained |
| 2 — Comportamento e conhecimento | ✅ | /knowledge, /skills, /memory (por-perfil) |
| 3 — Agenda e follow-up | ✅ | /calendar, /followup (por-perfil) |
| 4 — Observabilidade | ✅ | /logs, /runs |
| 5 — Canais de conversa | 🔶 | /channels/whatsapp + QR + contacts + home channel automático + plugin whatsapp-mixed (silêncio + auto-flush via cron) validados com número real; **falta confirmar o auto-flush disparando sozinho em produção** (o cron job já foi exercitado, mas sem uma janela completa de 10 min sem interação do cliente) |

---

## Próximo passo

Testar o **auto-flush do modo mixed** de ponta a ponta: o dono responde manualmente um cliente
(silencia o chat), o cliente manda uma mensagem durante a janela de silêncio, e ninguém mais
interage — o cron job (`whatsapp-mixed-flush-<chat>`) deve disparar sozinho ao fim dos 10 min e
entregar a resposta ao cliente sem que ele precise mandar outra mensagem. Depois disso, a Fase 5
fecha e o POC está com as 5 fases completas.
