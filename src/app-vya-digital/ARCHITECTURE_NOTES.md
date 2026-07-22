# app-vya-digital — notas de port (crux → enterprise-hermes-agent)

Dashboard adaptado do `crux/dashboard` (SaaS pessoal) para rodar na infra da
empresa, consumindo a estrutura do `enterprise-hermes-agent`. Portado em
2026-07-15. Ler isto antes de mexer no código — explica por que várias
features do original não estão aqui.

## Princípio do port

Igual ao crux: leitura/escrita **direta** de arquivo no volume compartilhado
de `profiles/<agent_id>/` (`state.db`, `produto.yaml`, `appointments.db`,
`SOUL.md`, `channel_directory.json`, `cron/jobs.json` etc.) — não uma API
intermediária, porque essas features nunca foram expostas como API nem no
crux nem no `vyadigital_api`/`vya-workforce-api` da empresa.

Só uma exceção vai por API: **canal WhatsApp** (connect/disconnect/QR),
porque no crux esse controle já dependia de estar no mesmo container do
bridge/gateway — na empresa o gateway roda dentro do container
`vya-workforce-api`, não deste. Ver `lib/vya_api_client.py`.

## Por que várias features do crux não foram portadas

O crux e a empresa usam o mesmo hermes-agent upstream (patches quase
idênticos em cima do mesmo commit — confirmado comparando os dois `.diff`),
então o schema de `state.db` bate. Mas o crux tem código **adicional** que
não existe no hermes-agent nem no fork da empresa:

| Feature removida | Por quê |
|---|---|
| `suspend`/`resume` de perfil | Dependiam de `supervisorctl`/`profile_state.py` (crux-api), sem equivalente hoje — não há conceito de "perfil desligado sem apagar sessão" no hermes-api da empresa. `restart` **não está mais nesta lista** — ver abaixo, gap fechado. |
| `contact/pause`/`resume` | O gateway do crux (patch próprio) checa um arquivo `paused/<chat_id>` antes de responder. **Conferido**: esse trecho não existe no patch da empresa (`hermes-agent-patches.diff`). Escrever a flag aqui não pausaria nada do outro lado — por isso os handlers de escrita foram removidos (só ficou a leitura, usada por `handle_conversations`, sempre vazia hoje). |
| `group/members`, `contact/avatar` | Dependiam de chamar o bridge Node/Baileys em `http://127.0.0.1:{port}` — mesmo container no crux, inalcançável daqui. O frontend já degrada bem sozinho nesses dois casos (fallback pra letra/nome cru), então não quebram a UI, só ficam sem essa informação extra. |
| Painel "Banco de dados" (SQL de leitura livre) | Decisão deliberada, não limitação técnica: é uma porta de admin sobre dados de clientes de terceiros (outros agentes na mesma infra). Não é feature de produto. A aba "DB & Logs" abre direto em Logs (isso sim portado 100%). |
| `leads` (kanban) | O endpoint lê `leads.db` diretamente — **portável e já ligado**, mas a tabela só existe se o plugin `leads-auto-create` (que cria e popula o schema) também for instalado no gateway da empresa. Sem isso, a aba abre e funciona, só fica sempre vazia. Fase 2. |

## O que está 100% portado e funcional

Overview, Conversas/Mensagens, Contatos, Agenda (`appointments.py`),
Produto/SOUL, Cron (histórico + jobs), Logs, Contact/memory, Contact/delete
(sem o stop/relaunch de gateway — ver abaixo), QR/connect/disconnect via
vyadigital_api, Restart de gateway via vyadigital_api.

### Gap do restart fechado (2026-07-16)

`restart` **não tinha** como ser feito daqui (processo em outro container),
mas o restante do stack sim tem acesso — `hermes_fs.py`, dentro do
`hermes-api` real (roda no mesmo container/namespace de PID do gateway), já
tinha `stop_gateway`/`start_gateway` prontos (usados por `update_profile` pra
aplicar mudanças de config com o gateway no ar). Fechado assim:

1. `hermes_fs.restart_gateway(d)` novo em `src/hermes_agent/hermes-api/server/hermes_fs.py`
   (só `stop_gateway` + `start_gateway`).
2. `POST /agents/{agent_id}/restart` novo em `src/hermes_agent/hermes-api/server/app.py`.
3. Proxy em `src/vyadigital_api/routers/agents.py` + `clients/vya_client.py`
   (`restart_agent`).
4. `handle_restart` de volta em `server.py` (chama `vya_api_client.restart_agent`)
   e o botão "Reiniciar" de volta em `index.html` (aba Ações).

Isso mexe em **três arquivos fora de `app-vya-digital`** (`hermes_fs.py`,
`app.py` do hermes-api real, e `routers/agents.py`+`clients/vya_client.py` do
vyadigital_api) — código que já está em produção, não a pasta nova isolada.
Só testado por leitura/`ast.parse` aqui (sem Docker neste ambiente) — precisa
subir a stack real (ou pelo menos o `hermes-api`) e bater no endpoint antes
de confiar nele em produção.

### Risco aceito em `contact/delete`

No crux, antes de apagar sessões do `state.db` o dashboard para o gateway
(evita que o cache em memória da sessão sobrescreva o delete) e religa depois.
Aqui isso foi removido — não alcança o processo no outro container. Risco:
numa janela pequena logo após o delete, uma mensagem em trânsito pode
recriar a sessão com dado ainda em cache. Documentado em `server.py` no
handler. Se incomodar na prática, é caso de pedir um endpoint de restart de
agente no `hermes-api`/`vyadigital_api`.

## Deploy

Ver `docker-compose.snippet.yaml` — não é um compose standalone, é um bloco
de serviço para colar em `src/hermes_agent/docker-compose.yaml` (mesmo
arquivo que já monta `./data/profiles` em api/dashboard/gateway). Precisa
ser bind mount (não named volume) e estar na mesma stack pra apontar pro
mesmo diretório no host.

Variáveis de ambiente novas: `VYA_API_BASE_URL`, `VYA_API_PREFIX`,
`VYA_API_KEY` (secret, mesma chave que os outros serviços já usam pra falar
com a vya-workforce-api), `HERMES_HOME_ROOT=/app`.

## Pendências antes de produção

1. Confirmar o valor real que `gateway_state.json` usa pro estado "rodando"
   no fork da empresa (assumi `running`/`online`/`active` em
   `_profile_status`/`handle_overview` — ver `TODO(verificar)` no código).
2. Rodar `pip install -r requirements.txt` num venv e validar o servidor de
   pé contra um `profiles/<id>/` real da empresa antes de publicar a imagem
   (isso ainda não foi testado rodando — só revisado estaticamente).
3. Decidir se/quando portar leads (plugin no gateway) e o gap de
   suspend/resume/restart (endpoint novo no hermes-api).
