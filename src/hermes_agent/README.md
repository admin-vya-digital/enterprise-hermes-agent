<!--
Criado em: 06/07/2026 11:20
Modificado em: 06/07/2026 11:20
-->

# docker_hermes — Vya Digital Workforce (hermes-agent + vya-workforce-api)

Build a partir do código-fonte do `hermes-agent` (patchado) + a API própria
de provisionamento (`vya-workforce-api`, FastAPI). Vendorizado a partir de
`tmp/projeto-vya/`.

O `Dockerfile` é multi-stage: uma base comum (`hermes-base`, com o
hermes-agent + venv + bridge do WhatsApp + build do dashboard web) e dois
alvos finais que geram **duas imagens/containers separados**:

- **`hermes-agent`** (serviço `dashboard`) — só o hermes-agent, sem o código
  da API.
- **`api`** (serviço `api`) — reusa o venv da base e adiciona o
  `vya-workforce-api` por cima.

`skills/` e `profiles/` **não são copiados para a imagem** — são sempre
volumes (bind mounts graváveis), já que mudam constantemente em runtime
(novas skills instaladas, novos agentes provisionados).

```
src/docker_hermes/
├── hermes-agent/              # hermes-agent (upstream + patches, ver hermes-agent-patches.diff)
├── hermes-api/                # vya-workforce-api (FastAPI de provisionamento/gestão)
├── skills/                    # skills compartilhadas — volume gravável, NÃO copiado para a imagem
├── data/profiles/             # dados de runtime dos agentes (git-ignored) — volume gravável
├── Dockerfile                 # multi-stage: hermes-base → hermes-agent | api
├── docker-compose.yaml
├── entrypoint.sh              # injeta Docker secrets como env vars antes do comando real
├── .env.example                # config não sensível
├── .env.example.original       # env real do hermes-agent, referência completa
└── hermes-agent-patches.diff  # diff histórico entre hermes-agent vanilla e a versão vendorizada
```

## Segredos (Docker secrets)

`VYA_API_KEY` (chave de acesso à API), `ANTHROPIC_API_KEY` (provider usado ao
provisionar agentes) e `GROQ_API_KEY` (STT/Whisper do hermes-agent) **não**
vão no `.env` — vêm de arquivos em `.secrets/hermes/` (na raiz do projeto):

```
.secrets/hermes/
├── VYA_API_KEY
├── ANTHROPIC_API_KEY
└── GROQ_API_KEY
```

> Nota: `.secrets/config.yaml` também tem chaves de outros providers usados
> em `custom_providers` (Maritaca, um segundo Groq para `llama-3.3-70b`) —
> essas são lidas diretamente do `config.yaml` do perfil, não de variáveis
> de ambiente, então já foram salvas em `.secrets/hermes/MARITACA_API_KEY` e
> `.secrets/hermes/GROQ_API_KEY_LLAMA33` como referência, mas não precisam
> (nem fazem sentido) estar no `secrets:` deste compose.

Cada arquivo contém, em texto puro (sem `export`, sem aspas), o valor de uma
única variável — o nome do arquivo é exatamente o nome da variável de
ambiente. `.secrets/` inteiro é ignorado pelo git (permissão `700`); mantenha
os arquivos individuais em `600`.

O `docker-compose.yaml` declara os dois em `secrets:` (nível raiz), o
`entrypoint.sh` lê cada arquivo montado em `/run/secrets/<NOME>`, exporta
como variável de ambiente e só então executa o comando real (`start.sh` no
serviço `api`, `hermes dashboard ...` no serviço `dashboard`). Para adicionar
um novo segredo, siga o mesmo padrão: criar o arquivo em `.secrets/hermes/`,
registrar em `secrets:` e listar no serviço que precisa dele — o
`entrypoint.sh` exporta automaticamente qualquer arquivo presente em
`/run/secrets/`.

## Uso (Docker)

```bash
cd src/docker_hermes
cp .env.example .env   # ajustar portas se necessário

# preencher os segredos (nunca versionados)
printf '%s' "<sua-chave-vya>" > ../../.secrets/hermes/VYA_API_KEY
printf '%s' "<sua-chave-anthropic>" > ../../.secrets/hermes/ANTHROPIC_API_KEY
chmod 600 ../../.secrets/hermes/VYA_API_KEY ../../.secrets/hermes/ANTHROPIC_API_KEY

docker compose up -d --build
```

- API: http://localhost:8700 (swagger em `/docs`)
- Dashboard: http://localhost:9119 (login usuário/senha — ver "Controle de
  acesso" abaixo)
- Dados dos agentes persistem em `./data/profiles` (volume, git-ignored).
- `./skills` é montado como volume gravável nos dois containers — skills
  instaladas/atualizadas em runtime gravam direto nesse diretório do host
  (que é versionado no git como seed data). Revise o `git status` antes de
  commitar se não quiser incluir mudanças feitas em runtime.

## Customizar novos agentes (`config.base.yaml`)

`./config.base.yaml` é montado (read-only) em `/app/config.base.yaml` **só
no serviço `api`**. Quando existe, `hermes-api/server/provision.py` usa esse
arquivo como base do `config.yaml` de **todo agente novo** criado via
`POST /agents` — o campo `provider` é sempre sobrescrito pelo valor do
request, o resto (toolsets, `agent.*`, etc.) vem daqui.

Não afeta:
- Agentes já criados (só é lido no momento da criação).
- O perfil `dashboard` (criado por `hermes dashboard`, não passa por
  `provision.py`).

Não coloque credenciais aqui — chaves de provider vão em `provider_api_key`
no corpo do `POST /agents`, não no `config.base.yaml`.

## Controle de acesso do dashboard

O dashboard usa o provider nativo `dashboard_auth/basic` do hermes-agent
(usuário/senha, sem OAuth) — **não** o pareamento por código. Configurado
via 3 Docker secrets (mesmo mecanismo dos outros):

```
.secrets/hermes/
├── HERMES_DASHBOARD_BASIC_AUTH_USERNAME
├── HERMES_DASHBOARD_BASIC_AUTH_PASSWORD
└── HERMES_DASHBOARD_BASIC_AUTH_SECRET   # chave de assinatura das sessões (HMAC)
```

Importante: o comando do serviço `dashboard` **não** deve ter `--insecure` —
essa flag desativa completamente o gate de autenticação (mesmo com o
provider configurado). Sem `--insecure` e sem usuário/senha configurados, o
hermes-agent se recusa a subir (`Refusing to bind ... no auth providers
registered`) — por isso os três arquivos acima precisam estar preenchidos
antes de remover a flag.

Para trocar a senha:
```bash
printf '%s' "<nova-senha>" > ../../.secrets/hermes/HERMES_DASHBOARD_BASIC_AUTH_PASSWORD
chmod 600 ../../.secrets/hermes/HERMES_DASHBOARD_BASIC_AUTH_PASSWORD
docker compose up -d --force-recreate dashboard
```

`HERMES_DASHBOARD_BASIC_AUTH_SECRET` assina os tokens de sessão — mantenha
estável entre restarts (gerar uma vez com `openssl rand -hex 32` é
suficiente) para não derrubar sessões ativas a cada `docker compose up`.

## Setup manual (sem Docker)

Pré-requisitos: Python ≥ 3.11 (testado com 3.12), Node ≥ 20 (testado com 24).

```bash
cd src/docker_hermes/hermes-agent
python3 -m venv venv
./venv/bin/pip install -e .
./venv/bin/pip install -r ../hermes-api/requirements.txt

cd scripts/whatsapp-bridge && npm install && cd ../..
cd web && npm install && npm run build && cd ..

cd ../hermes-api
export VYA_API_KEY=<chave>
./start.sh          # porta 8700 (VYA_PORT para mudar)

# (opcional) dashboard
HERMES_HOME=<raiz>/data/profiles/dashboard \
  ../hermes-agent/venv/bin/hermes dashboard --no-open   # porta 9119
```

> `hermes-agent/venv/` e `node_modules/` não são portáveis entre máquinas —
> sempre reconstrua no ambiente de destino (o Dockerfile já faz isso na imagem).

## Validação rápida

> ⚠️ Os exemplos abaixo usam `curl` com a chave em texto puro na linha de
> comando — válido só para teste local (localhost), nunca em terminal ou
> logs compartilhados. Para automação dentro deste repositório, prefira
> Python + `requests` lendo a chave de `.secrets/hermes/VYA_API_KEY` (ver
> convenção de credenciais do projeto).

```bash
curl http://localhost:8700/health
# → {"status":"ok",...}

curl -X POST http://localhost:8700/agents \
  -H "Authorization: Bearer $VYA_API_KEY" -H 'Content-Type: application/json' \
  -d '{"agent_id":"sdr-01","name":"SDR","provider":"anthropic","provider_api_key":"<chave-real>"}'
# → 201; cria data/profiles/sdr-01/ com SOUL.md, config.yaml, symlink skills/
```

Swagger completo em `http://localhost:8700/docs`. Todas as rotas (exceto
`/health`) exigem `Authorization: Bearer <VYA_API_KEY>`. Documentação
adicional em `hermes-api/docs/` (PLAN.md, DEPLOY.md, swagger.html).

## Patches sobre o hermes-agent vanilla

`hermes-agent-patches.diff` documenta as modificações Vya sobre o
hermes-agent upstream (11 arquivos, ~112 linhas — threading de
`contact_user_id`, formatação de mensagens WhatsApp/cron, etc.). O código em
`hermes-agent/` já contém essas mudanças mescladas — o diff **não** é
reaplicado no build, serve só como registro histórico.

Para atualizar o hermes-agent vendorizado para uma versão upstream mais
nova: baixar a versão vanilla na tag desejada, gerar um novo diff
(`git diff --no-index vanilla/ hermes-agent/`), revisar as mudanças e
regravar `hermes-agent-patches.diff`.

## Relação com `wfdb01/`

`wfdb01/docker-compose.yaml` roda a imagem pré-buildada
`nousresearch/hermes-agent:latest` atrás de Traefik, para produção. Este
diretório (`src/docker_hermes/`) builda a partir do código-fonte, com a
camada de provisionamento `vya-workforce-api`, voltado a uso local/dev. Não
rode os dois stacks simultaneamente sem ajustar nomes de container e portas
— os nomes já foram escolhidos para não colidir (`vya-workforce-*` aqui vs.
`hermes-agent`/`hermes-dashboard` em `wfdb01/`).
