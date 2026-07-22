<!--
Criado em: 22/07/2026 15:01
Modificado em: 22/07/2026 15:01
-->

# Bug Report — Duplicidade de código em `src/app-vya-digital/`

**Status**: Corrigido parcialmente (ver seção "Pendências")
**Severidade**: Média (drift silencioso entre implementações; um caso confirmado de
critério divergente para o mesmo dado)
**Origem**: código adicionado por programador júnior da empresa, portado do
projeto pessoal `crux` (ver `src/app-vya-digital/ARCHITECTURE_NOTES.md`)

## Contexto

A pasta `src/app-vya-digital/` (dashboard aiohttp) foi revisada para
verificar duplicidade de lógica com as demais pastas de `src/`,
especificamente `src/hermes_agent/hermes-api/server/hermes_fs.py` (plano de
controle REST real do hermes-agent). A verificação foi feita **lendo o
código-fonte diretamente**, não a documentação (`ARCHITECTURE_NOTES.md`
afirma que não há sobreposição de lógica de negócio — parcialmente
impreciso: há, sim, duplicação de helpers de baixo nível).

## Duplicações encontradas

| # | Função | `hermes_fs.py` (fonte) | `app-vya-digital/server.py` (cópia) | Situação |
|---|---|---|---|---|
| 1 | Leitura de `gateway_state.json` | `gateway_state(d)` | `_gateway_state(d)` | Cópia idêntica byte-a-byte |
| 2 | Cálculo de status "online" do agente | `profile_status(d)` | `_profile_status(d)` | **Divergiu** — ver detalhe abaixo |
| 3 | Validação de path de perfil (`profile_id` → `Path`) | `safe_profile_path(d)` | `_safe_profile_path(d)` | Cópia com hardening extra (`resolve()+relative_to()`) não retroportado para o original |
| 4 | Leitura/escrita de `SOUL.md` | `read_soul(d)` | inline em `handle_get_soul`/`handle_set_soul` | Lógica idêntica, reescrita à mão |
| 5 | Leitura/escrita de `produto.md` | `read_produto(d)` | inline em `handle_get_produto`/`handle_set_produto` | Lógica idêntica, reescrita à mão |
| 6 | Escrita atômica de arquivo (`tmp` + `replace`) | padrão usado em `hermes_fs.py` (`_write_env`, `locked_json`) | `_write_atomic(path, content)` | Mesmo padrão, implementação paralela |

### Detalhe do item #2 (o único com risco funcional real)

- `hermes_fs.py.profile_status`: considera o agente `online` se o PID salvo
  em `gateway.pid` está vivo (`pid_alive(pid)`), **independente** do campo
  `gateway_state`.
- `app-vya-digital/server.py._profile_status`: considera `online` se
  `gateway_state in ("running", "online", "active")` — **não checa PID**.
- O código tinha um `TODO(verificar)` no `server.py:52` porque o autor não
  conseguiu confirmar contra o fork real quais valores `gateway_state`
  realmente assume.

**Investigação** (busca nos escritores reais de `gateway_state.json` em
`gateway/status.py`, `hermes_cli/container_boot.py`,
`hermes_cli/web_server.py`): os únicos valores literais gravados são
`"starting"`, `"running"` e `"stopped"`. Ou seja, `"online"`/`"active"` no
tuple do `app-vya-digital` são mortos (nunca ocorrem) — mas não causam falso
positivo, só ruído.

**Por que não copiar a lógica de `pid_alive` do original**: o
`hermes_fs.py` roda no **mesmo container/namespace de PID** do gateway
(documentado em `ARCHITECTURE_NOTES.md`), então `os.kill(pid, 0)` enxerga o
processo. O `app-vya-digital` roda em **container separado** — o mesmo PID
não existe no seu namespace, então `pid_alive()` sempre retornaria `False`
ali, mesmo com o gateway rodando. A checagem por string
(`gateway_state`) é, portanto, a única viável nesse contexto — **não é um
bug de implementação, é uma adaptação necessária à arquitetura de
containers separados**. O `TODO(verificar)` foi resolvido: `"running"` é o
valor correto a checar; `"online"`/`"active"` foram removidos por serem
mortos, e `"starting"` foi mantido fora do conjunto "online" (agente ainda
não está pronto nesse estado).

## Causa raiz

`app-vya-digital` tem Dockerfile e `docker-compose` com **build context
isolado** (`context: ../app-vya-digital`, sem acesso a arquivos fora da
própria pasta) — não roda nenhum código do hermes-agent
(`Sem venv do hermes-agent`, comentário no Dockerfile). Extrair essas
funções para um módulo verdadeiramente compartilhado exigiria mudar o
build context de ambos os serviços para a raiz de `src/` e reestruturar os
Dockerfiles — mudança de infraestrutura fora do escopo desta correção
pontual.

## Correções aplicadas

1. `server.py._profile_status`: `TODO(verificar)` resolvido com evidência
   (ver acima); removidos os valores mortos `"online"`/`"active"`;
   comentário adicionado explicando a decisão e por que diverge de
   `hermes_fs.py.profile_status`.
2. Comentário `# SYNC` adicionado em cada função duplicada (`_gateway_state`,
   `_safe_profile_path`, `_write_atomic`, leitura de `SOUL.md`/`produto.md`)
   apontando a função-fonte em `hermes_fs.py` e alertando para manter em
   sincronia manualmente até uma eventual extração real.

## Pendências (fora do escopo desta correção)

- Decidir se vale a pena investir na extração real (mudar build context de
  `app-vya-digital` e `hermes-api` para compartilhar um pacote comum) —
  eliminaria os itens #1, #3, #4, #5, #6 da tabela permanentemente.
- Item #3 (`safe_profile_path`): o hardening extra feito no
  `app-vya-digital` (`resolve()+relative_to()`) não foi retroportado para
  `hermes_fs.py` — o original continua com a versão mais fraca (ainda
  segura, pela regex `SAFE_ID`, mas sem a defesa em profundidade).
