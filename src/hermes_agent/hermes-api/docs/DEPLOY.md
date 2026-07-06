# Deploy — Vya Digital Workforce API (hermes-api)

Plano de implantação da API REST de controle de agentes Hermes no container que já roda o
Hermes 0.15.x. A API é um **control plane**: FastAPI que manipula arquivos e processos dos
perfis em `~/.hermes/profiles/` — nunca invoca LLM por conta própria.

---

## 1. O que a API assume que já existe no container

Todos os caminhos são fixos no código (relativos ao `$HOME` do usuário que roda a API):

| Caminho | Uso |
|---|---|
| `~/.hermes/hermes-agent/` | Código-fonte do Hermes (a API importa `toolsets.py` daqui) |
| `~/.hermes/hermes-agent/venv/` | Venv Python do Hermes — a API **roda dentro dele** (`start.sh`) |
| `~/.hermes/hermes-agent/scripts/whatsapp-bridge/bridge.js` | Bridge Baileys (Node.js) que a API sobe por perfil |
| `~/.hermes/profiles/` | Onde os agentes (perfis) são criados/lidos |
| `~/.hermes/profiles/default-profile/` | Perfil-template protegido (não deletável via API) |
| `~/.hermes/skills/` | Skills globais — cada perfil recebe um symlink para cá |
| `~/.hermes/plugins/` | Onde a API instala o plugin `whatsapp-mixed` (global) |

Requisitos de sistema:
- **Python 3.11+** (o venv do Hermes já cobre)
- **Node.js** com as dependências do `whatsapp-bridge` instaladas (`npm install` já feito
  em `scripts/whatsapp-bridge/` — Baileys etc.)
- Utilitário `tail` disponível (usado pelo endpoint `/logs`)
- A API precisa rodar **como o mesmo usuário** dono de `~/.hermes` (ela lê/escreve arquivos
  e mata processos por PID)

## 2. ⚠️ Ponto crítico — usar o Hermes patcheado do pacote de entrega

**Tudo o que o deploy precisa já está empacotado e versionado** no repositório
`github.com/jordaoaq/vya-workforce-interface` (branch `main`, commit `00dc458` —
"Pacote de entrega producao vya"). Ele contém três diretórios:

- `hermes-agent/` — o Hermes **já com os patches** necessários
- `project-vya-workforce/` — esta API (mesmo conteúdo da pasta `hermes-api/`)
- `infra/` — docker-compose de produção (Postgres 17 + Redis 7, bind só em 127.0.0.1)

**O container deve usar o `hermes-agent/` desse repo — não um Hermes baixado do upstream.**
A API depende de extensões aditivas que não existem no código stock 0.15.2:

1. **`scripts/whatsapp-bridge/bridge.js`** — nova branch de modo `WHATSAPP_MODE=mixed`
   (encaminha toda mensagem `fromMe`) e campo `fromMe` no evento enviado ao gateway.
   Sem isso, o modo mixed (dono + clientes no mesmo número) não funciona.
2. **`gateway/platforms/whatsapp.py`** — leitura da porta do bridge via variável de
   ambiente `BRIDGE_PORT` (a API aloca uma porta única por perfil no `.env`).
   Sem isso, todos os gateways tentam falar com o bridge na porta default (3000) e
   **múltiplos agentes com WhatsApp colidem**.
3. Verificar que o comando `hermes channel set` existe na versão do container (usado para
   definir o WhatsApp como home channel após o pareamento).

Como conferir rapidamente no container:
```bash
grep -n "mixed" ~/.hermes/hermes-agent/scripts/whatsapp-bridge/bridge.js
grep -n "BRIDGE_PORT" ~/.hermes/hermes-agent/gateway/platforms/whatsapp.py
```
Se os dois greps retornarem resultados, está tudo pronto. Se não, substituir o
`~/.hermes/hermes-agent` do container pelo `hermes-agent/` do repo
`vya-workforce-interface` (e recriar o venv + `npm install` no `scripts/whatsapp-bridge/`).

## 3. Subir a API

```bash
# 1. Clonar o repo de entrega e usar a pasta project-vya-workforce/
#    git clone git@github.com:jordaoaq/vya-workforce-interface.git

# 2. Definir a chave de autenticação da API (Bearer token exigido em todas as rotas)
export VYA_API_KEY=<chave-secreta-forte>

# 3. (opcional) porta — default 8700
export VYA_PORT=8700

# 4. Iniciar — o script instala as dependências próprias (fastapi, uvicorn,
#    python-multipart, pypdf, python-docx, qrcode) no venv do Hermes e sobe o uvicorn
./start.sh
```

Verificação: `curl http://localhost:8700/health` → `{"status":"ok",...}`.
Swagger em `http://localhost:8700/docs`.

**Para produção**, dois ajustes recomendados no `start.sh` / na forma de execução:
- Remover o flag `--reload` do uvicorn (é modo de desenvolvimento; observa arquivos e
  reinicia sozinho).
- Rodar como serviço supervisionado (systemd, supervisor, ou como processo principal do
  container) para reinício automático, com `VYA_API_KEY` injetada como secret — **não**
  hardcoded em script.

## 4. Rede e portas

| Porta | O quê | Expor? |
|---|---|---|
| 8700 | API REST (única interface externa) | **Sim** — de preferência atrás de TLS (reverse proxy) |
| 3100, 3101, … | Bridges WhatsApp (1 por perfil) | Não — só loopback |
| 8810, 8811, … | Gateways Hermes (1 por perfil) | Não — só loopback |

A API precisa de **saída para a internet**: WhatsApp (Baileys), APIs dos provedores de
LLM (Anthropic/OpenAI/…), Google (Calendar OAuth) e download de conhecimento por URL.

## 5. Credenciais — o que é fornecido em runtime (não no deploy)

Nada de chave de LLM no ambiente do container. Cada agente é self-contained:

- **Chave do provedor de LLM**: enviada no corpo do `POST /agents`
  (`provider` + `provider_api_key`) — fica gravada no `.env` do perfil.
- **Google Calendar**: por perfil, fluxo de 4 passos via API (colar o JSON do OAuth
  Client ID tipo *Desktop app* do Google Cloud Console → abrir a auth-url no navegador →
  colar o código de volta). Único pré-requisito externo: um projeto Google Cloud com a
  Calendar API habilitada e um OAuth Client ID criado.
- **WhatsApp**: `POST /agents/{id}/channels/whatsapp` inicia o pareamento;
  `GET .../whatsapp/qr` devolve o QR como PNG — **escanear o QR é o único passo humano**.

## 6. Smoke test pós-deploy (roteiro de aceite)

A collection `postman_collection.json` (na raiz do repo) cobre tudo. Sequência mínima:

1. `GET /health` — sem auth, deve responder 200.
2. `GET /agents` com `Authorization: Bearer <VYA_API_KEY>` — lista perfis existentes.
3. `POST /agents` — criar um agente de teste (com provider + chave reais).
4. `GET /agents/{id}` — conferir persona, portas alocadas, `online: false`.
5. `POST /agents/{id}/knowledge/upload` — subir um PDF/MD e conferir no `GET`.
6. `POST /agents/{id}/skills` — habilitar/desabilitar um toolset.
7. (se for validar canal) `POST /agents/{id}/channels/whatsapp` + scan do QR.
8. `DELETE /agents/{id}` — remover o agente de teste sem resíduos.

## 7. Pendência conhecida (não bloqueia o deploy)

Fase 5 do POC: falta confirmar em produção o **auto-flush do modo mixed** disparando
sozinho — dono silencia um chat respondendo manualmente, cliente escreve durante a janela
de 10 min, e o cron job `whatsapp-mixed-flush-<chat>` deve entregar a resposta acumulada
ao fim da janela sem nova mensagem do cliente. O mecanismo já foi exercitado; falta o
teste da janela completa. Todo o resto (fases 0–4 e o grosso da fase 5) está validado.

## 8. Resumo executivo

1. Usar o **`hermes-agent/` do repo `vya-workforce-interface`** (já patcheado) — não o
   Hermes stock do upstream. Conferir com os greps da seção 2.
2. Subir a API de `project-vya-workforce/` do mesmo repo: exportar `VYA_API_KEY`,
   rodar `./start.sh` (sem `--reload` em prod).
3. Expor só a porta 8700, com TLS na frente.
4. Rodar o smoke test da seção 6 com a collection Postman.
