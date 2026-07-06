---
name: reset-profile-history
summary: Apagar o histórico Hermes de conversa de UM contato específico em UM perfil WhatsApp/Baileys multi-tenant. Preserva a sessão Baileys e só edita state.db/sessions.json, não apaga creds.json.
description: Use when the Root Admin asks to erase/reset the Hermes conversation history for exactly one WhatsApp contact inside one multi-tenant profile. Requires a specific profile and contact; if the contact is not provided, ask before touching state. Preserves the Baileys WhatsApp login/session.
version: 1.0.0
author: Hermes Root
license: MIT
metadata:
  hermes:
    tags: [whatsapp, multi-tenant, sessions, state-db, reset, history]
    related_skills: [hermes-root-soul, edit-profile, create-profile]
---

# Reset Chat History — Um Contato Específico

## Overview

Use esta skill para apagar o histórico Hermes de conversa de UM contato específico em UM perfil WhatsApp/Baileys multi-tenant.

O alvo é o histórico do agente, não a autenticação WhatsApp.

Arquivos envolvidos:

- `$PROFILE/state.db` — SQLite canônico com tabelas `sessions` e `messages`.
- `$PROFILE/sessions/sessions.json` — índice `chat/JID/LID -> session_id` usado pelo gateway para continuar conversas.
- `$PROFILE/session/` — credenciais Baileys/WhatsApp. NÃO apagar para limpar conversa.

Regra central: apagar somente a sessão daquele contato. Nunca apagar `state.db` inteiro quando a intenção é limpar um único contato.

> **POR QUE PARAR O GATEWAY É OBRIGATÓRIO (não pular Phase 3).** O gateway mantém um
> **cache de sessões em memória** (`SessionManager`). Se você apagar as linhas do
> `state.db` / `sessions.json` com o gateway **rodando**, o cache em memória continua
> apontando para o `session_id` que você removeu. Quando o contato manda a próxima
> mensagem, o gateway usa a sessão cacheada e **recria** a linha de forma corrompida:
> `source='unknown'`, `user_id=NULL`, apenas um `session_meta` placeholder e **nenhuma
> mensagem real persistida** (o agente até responde, usando o contexto em memória, mas
> nada é gravado). Sintoma observado no dashboard: "a conversa aparece mas sem nenhuma
> mensagem". Apagar arquivos **não despeja o cache** — só parar/religar o gateway despeja.
> Por isso: contato **ocioso** (sessão já expirada da memória) tolera delete ao vivo;
> contato **ativo** (mandou mensagem há pouco) exige gateway parado.

> **Equivalente no dashboard (hermes-dash):** a aba Contatos tem uma lixeira por contato
> (`POST /api/profiles/{id}/contact/delete {contact_id, is_group}`) que faz a **mesma
> sequência segura desta skill, automatizada**: para o gateway do perfil (por PID, com
> checagem de `HERMES_HOME`) → backup (`state.db`+wal/shm, `sessions.json`,
> `channel_directory.json`) → DELETE de `sessions`+`messages` (os triggers
> `messages_fts_delete` limpam o FTS) → remove entradas no `sessions.json` → remove a
> linha no `channel_directory.json` → **religa o gateway** com o env do perfil
> (`HERMES_HOME` + `.env`, então `WHATSAPP_REQUIRE_MENTION` etc. continuam valendo).
> Para DM, alvo por `user_id`; para grupo, todas as sessões dos participantes (por
> `chat_id`). Downtime do gateway: **~5s** (o **bridge não é tocado** — mensagens que
> chegam nesse intervalo ficam na fila do bridge e são respondidas quando o gateway
> volta, sem perda). Preserva `creds.json` e `memories/`. Uma versão anterior fazia
> delete "ao vivo" sem parar o gateway e corrompia contatos ativos (ver callout acima);
> isso foi corrigido para parar/religar sempre.

## Quando Usar

Use quando o admin pedir algo como:

- "apague a conversa do contato X"
- "resete o histórico do número 55... no perfil Y"
- "limpa a memória/histórico desse cliente no WhatsApp"
- "zera a conversa só do LID/JID X"

Não use para:

- apagar perfil inteiro → usar `delete-profile`
- deslogar WhatsApp / gerar novo QR → mexe em `session/creds.json`, outro procedimento
- limpar todos os contatos de um perfil → este skill é explicitamente por contato
- editar contexto de negócio (`produto.md`) ou provider → usar `edit-profile`

## Dados Obrigatórios

Antes de executar, confirme:

1. `CLIENT_ID` / perfil exato, exemplo: `<CLIENT_ID>`.
2. Contato exato a limpar: telefone, JID, LID ou nome exibido.

Se o contato NÃO foi informado, pare e pergunte.

Pergunta padrão:

```
Qual contato devo resetar dentro do perfil <CLIENT_ID>? Pode mandar telefone, JID/LID ou nome exibido como aparece no WhatsApp.
```

Se o perfil não foi informado mas só existe um perfil em `~/.hermes/profiles/`, pode usar esse perfil óbvio e dizer a suposição antes de agir. Se houver múltiplos perfis, pergunte também o perfil.

## Conceitos

Para cada conversa, o gateway mantém um `session_key` em:

```
$PROFILE/sessions/sessions.json
```

Exemplo:

```json
"agent:main:whatsapp:dm:<LID_DO_CONTATO>": {
  "session_id": "20260626_144408_51026621",
  "origin": {
    "platform": "whatsapp",
    "chat_id": "<LID_DO_CONTATO>@lid",
    "user_id": "<LID_DO_CONTATO>@lid",
    "chat_name": "<nome de exibição>"
  }
}
```

O transcript real fica no SQLite:

```
$PROFILE/state.db
  sessions.id = session_id
  messages.session_id = session_id
```

Para resetar só um contato, remova:

1. A entrada desse contato em `sessions/sessions.json`.
2. As linhas `messages` desses `session_id`.
3. As linhas `sessions` desses `session_id`.

Na próxima mensagem do mesmo contato, o gateway cria uma nova sessão limpa.

## Procedimento Seguro

### Regra operacional — dividir ações destrutivas

Não execute descoberta, parada de gateway, edição de `.env`, deleção de SQLite/JSON e restart em um único comando grande. Para este tipo de operação, trabalhe em blocos pequenos e verificáveis:

1. Somente leitura: descobrir home channel e listar candidatos.
2. Confirmar/registrar o(s) `session_id` alvo(s) quando houver ambiguidade.
3. Parar somente o gateway do perfil por PID validado.
4. Criar backup.
5. Editar `.env`, se necessário.
6. Remover histórico do(s) `session_id` autorizado(s).
7. Religar gateway e validar.

Se o admin disser "pare" ou "divida em tarefas menores", interrompa imediatamente o bloco atual, não tente outra variante equivalente, e continue apenas por etapas pequenas.

### Phase 1 — Identificar perfil e contato

```bash
CLIENT_ID="<CLIENT_ID>"
CONTACT_QUERY="<telefone-ou-lid-ou-jid-ou-nome>"
PROFILE="$HOME/.hermes/profiles/$CLIENT_ID"

[ -d "$PROFILE" ] || { echo "ERRO: perfil não existe: $PROFILE"; exit 1; }
[ -n "$CONTACT_QUERY" ] || { echo "ERRO: contato não informado; perguntar ao admin"; exit 1; }
```

### Phase 2 — Encontrar sessões candidatas sem apagar nada

Use Python porque o container pode não ter `sqlite3` CLI.

```bash
python3 - <<'PY'
import json, os, pathlib, sqlite3

profile = pathlib.Path(os.environ['PROFILE'])
q = os.environ['CONTACT_QUERY'].strip().lower()
q_digits = ''.join(ch for ch in q if ch.isdigit())

sessions_json = profile / 'sessions' / 'sessions.json'
state_db = profile / 'state.db'

candidates = []

if sessions_json.exists():
    data = json.loads(sessions_json.read_text() or '{}')
    for key, entry in data.items():
        origin = entry.get('origin') or {}
        fields = [
            key,
            entry.get('session_id'),
            entry.get('display_name'),
            origin.get('chat_id'),
            origin.get('user_id'),
            origin.get('chat_name'),
            origin.get('user_name'),
        ]
        hay = ' '.join(str(x or '') for x in fields).lower()
        hay_digits = ''.join(ch for ch in hay if ch.isdigit())
        if q in hay or (q_digits and q_digits in hay_digits):
            candidates.append({
                'source': 'sessions.json',
                'session_key': key,
                'session_id': entry.get('session_id'),
                'chat_id': origin.get('chat_id'),
                'user_id': origin.get('user_id'),
                'name': origin.get('chat_name') or entry.get('display_name'),
            })

if state_db.exists():
    con = sqlite3.connect(state_db)
    con.row_factory = sqlite3.Row
    for row in con.execute('SELECT id, source, user_id, title, message_count FROM sessions'):
        fields = [row['id'], row['source'], row['user_id'], row['title']]
        hay = ' '.join(str(x or '') for x in fields).lower()
        hay_digits = ''.join(ch for ch in hay if ch.isdigit())
        if q in hay or (q_digits and q_digits in hay_digits):
            candidates.append({
                'source': 'state.db',
                'session_key': None,
                'session_id': row['id'],
                'chat_id': None,
                'user_id': row['user_id'],
                'name': row['title'],
                'message_count': row['message_count'],
            })

# agrupar por session_id; a mesma conversa pode aparecer em sessions.json e state.db
by_session = {}
for c in candidates:
    sid = c.get('session_id') or '<missing-session-id>'
    by_session.setdefault(sid, []).append(c)

print(json.dumps(by_session, ensure_ascii=False, indent=2))
print(f"TOTAL_UNIQUE_SESSION_IDS={len(by_session)}")
PY
```

Interpretação:

- Agrupe candidatos por `session_id` antes de decidir ambiguidade. A mesma conversa costuma aparecer duas vezes: uma entrada em `sessions.json` e outra em `state.db` com o mesmo `session_id`. Isso é um único alvo lógico, não dois.
- `TOTAL_UNIQUE_SESSION_IDS=0`: não apagar; pedir contato mais específico ou listar contatos conhecidos.
- `TOTAL_UNIQUE_SESSION_IDS=1`: pode seguir para aquele `session_id`, preservando o `session_key` correspondente se existir.
- `TOTAL_UNIQUE_SESSION_IDS>1`: não apagar no automático; mostrar os grupos por `session_id` e pedir qual é o correto. Se o admin responder "todos", trate como autorização explícita para apagar todos os `session_id` listados.

Importante para reset repetido: depois de um reset, qualquer nova mensagem do mesmo contato cria um novo `session_id`. Se o admin pedir "apague novamente o mesmo contato", rode a Phase 2 outra vez e use o novo `session_id`; nunca reutilize o `session_id` antigo salvo em conversa anterior.

### Phase 3 — Parar somente o gateway do perfil

Nunca usar `pkill -f`.

```bash
PID=""
if [ -f "$PROFILE/gateway.pid" ]; then
  # gateway.pid pode ser PID puro ou JSON: {"pid": 123, ...}
  PID=$(python3 - <<'PY'
import json, os, pathlib
p = pathlib.Path(os.environ['PROFILE']) / 'gateway.pid'
raw = p.read_text().strip() if p.exists() else ''
if raw:
    try:
        print(int(raw))
    except ValueError:
        print(int(json.loads(raw)['pid']))
PY
)
fi

if [ -n "$PID" ] && ps -p "$PID" >/dev/null 2>&1; then
  ENV_HOME=$(tr '\0' '\n' < "/proc/$PID/environ" 2>/dev/null | awk -F= '$1=="HERMES_HOME"{print substr($0,13)}' || true)
  if [ -n "$ENV_HOME" ] && [ "$ENV_HOME" != "$PROFILE" ]; then
    echo "ERRO: PID $PID não pertence ao perfil alvo ($ENV_HOME != $PROFILE)" >&2
    exit 20
  fi
  kill -TERM "$PID" 2>/dev/null || true
  sleep 3
  if ps -p "$PID" >/dev/null 2>&1; then
    kill -9 "$PID" 2>/dev/null || true
  fi
fi
```

O bridge pode continuar vivo. O alvo é evitar que o gateway escreva no `state.db` enquanto a limpeza seletiva acontece.

### Phase 4 — Backup antes de editar

```bash
TS=$(date +%Y%m%d-%H%M%S)
BACKUP="$PROFILE/backups/reset-profile-history-$TS"
mkdir -p "$BACKUP"

[ -f "$PROFILE/state.db" ] && cp -a "$PROFILE/state.db" "$BACKUP/"
[ -f "$PROFILE/state.db-wal" ] && cp -a "$PROFILE/state.db-wal" "$BACKUP/"
[ -f "$PROFILE/state.db-shm" ] && cp -a "$PROFILE/state.db-shm" "$BACKUP/"
[ -f "$PROFILE/sessions/sessions.json" ] && cp -a "$PROFILE/sessions/sessions.json" "$BACKUP/"

echo "backup=$BACKUP"
```

### Phase 5 — Apagar só o contato selecionado

Defina o alvo exato encontrado na Phase 2:

```bash
TARGET_SESSION_ID="<session_id>"
TARGET_SESSION_KEY="<session_key-ou-vazio>"
```

Execute a limpeza:

```bash
python3 - <<'PY'
import json, os, pathlib, sqlite3

profile = pathlib.Path(os.environ['PROFILE'])
target_session_id = os.environ['TARGET_SESSION_ID'].strip()
target_session_key = os.environ.get('TARGET_SESSION_KEY', '').strip()

if not target_session_id:
    raise SystemExit('ERRO: TARGET_SESSION_ID vazio')

sessions_json = profile / 'sessions' / 'sessions.json'
state_db = profile / 'state.db'

removed_json = 0
if sessions_json.exists():
    data = json.loads(sessions_json.read_text() or '{}')
    new_data = {}
    for key, entry in data.items():
        sid = entry.get('session_id')
        remove = sid == target_session_id or (target_session_key and key == target_session_key)
        if remove:
            removed_json += 1
        else:
            new_data[key] = entry
    tmp = sessions_json.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(new_data, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(sessions_json)

removed_messages = 0
removed_sessions = 0
if state_db.exists():
    con = sqlite3.connect(state_db)
    con.execute('PRAGMA foreign_keys=ON')
    with con:
        cur = con.execute('DELETE FROM messages WHERE session_id = ?', (target_session_id,))
        removed_messages = cur.rowcount
        cur = con.execute('DELETE FROM sessions WHERE id = ?', (target_session_id,))
        removed_sessions = cur.rowcount
    # Rebuild/compact opportunistic. If VACUUM fails due to WAL/lock, the deletion already happened.
    try:
        con.execute('VACUUM')
    except Exception as e:
        print(f'WARN: VACUUM falhou: {e}')
    con.close()

print(json.dumps({
    'target_session_id': target_session_id,
    'target_session_key': target_session_key,
    'removed_sessions_json_entries': removed_json,
    'removed_messages': removed_messages,
    'removed_sessions': removed_sessions,
}, ensure_ascii=False, indent=2))
PY
```

Resultado esperado:

- `removed_sessions_json_entries >= 1`
- `removed_sessions = 1`
- `removed_messages >= 0`

Se `removed_sessions = 0` mas havia `sessions.json`, a próxima mensagem ainda criará sessão nova porque a entrada do índice foi removida. Porém investigue por que o `state.db` não tinha a sessão.

### Phase 6 — Subir gateway novamente

```bash
set -a
source "$PROFILE/.env"
set +a
export HERMES_HOME="$PROFILE"
export VIRTUAL_ENV="$HOME/.hermes/hermes-agent/venv"
export PATH="$VIRTUAL_ENV/bin:$PATH"

# Em execução via Hermes tool, iniciar como background process rastreado.
hermes gateway run --replace >> "$PROFILE/logs/gateway.log" 2>&1
```

Quando usar ferramenta `terminal`, prefira `background=true` para manter o processo rastreável. Depois corrija/valide `gateway.pid` se necessário, usando `gateway.lock` se houver lock real ativo.

### Phase 7 — Verificação

```bash
python3 - <<'PY'
import json, os, pathlib, sqlite3
profile = pathlib.Path(os.environ['PROFILE'])
target_session_id = os.environ['TARGET_SESSION_ID'].strip()
target_session_key = os.environ.get('TARGET_SESSION_KEY', '').strip()

sessions_json = profile / 'sessions' / 'sessions.json'
if sessions_json.exists():
    data = json.loads(sessions_json.read_text() or '{}')
    assert target_session_key not in data, 'session_key ainda existe em sessions.json'
    assert all(v.get('session_id') != target_session_id for v in data.values()), 'session_id ainda referenciado em sessions.json'

state_db = profile / 'state.db'
if state_db.exists():
    con = sqlite3.connect(state_db)
    s = con.execute('SELECT count(*) FROM sessions WHERE id=?', (target_session_id,)).fetchone()[0]
    m = con.execute('SELECT count(*) FROM messages WHERE session_id=?', (target_session_id,)).fetchone()[0]
    assert s == 0, 'sessão ainda existe no state.db'
    assert m == 0, 'mensagens ainda existem no state.db'

print('OK: histórico do contato removido')
PY

PID=$(python3 - <<'PY'
import json, os, pathlib
p = pathlib.Path(os.environ['PROFILE']) / 'gateway.pid'
raw = p.read_text().strip() if p.exists() else ''
if raw:
    try:
        print(int(raw))
    except ValueError:
        print(int(json.loads(raw)['pid']))
PY
)
[ -n "$PID" ] && ps -p "$PID" -o pid=,cmd=
```

Depois, peça ao admin para mandar uma mensagem pelo contato resetado. O comportamento esperado é criar um novo `session_id` limpo.

## Listar contatos conhecidos quando o admin não souber o identificador

```bash
python3 - <<'PY'
import json, os, pathlib
profile = pathlib.Path(os.environ['PROFILE'])
p = profile / 'sessions' / 'sessions.json'
if not p.exists():
    print('Nenhum sessions.json encontrado')
    raise SystemExit(0)

data = json.loads(p.read_text() or '{}')
for key, entry in sorted(data.items()):
    origin = entry.get('origin') or {}
    print('---')
    print('session_key:', key)
    print('session_id: ', entry.get('session_id'))
    print('chat_id:    ', origin.get('chat_id'))
    print('user_id:    ', origin.get('user_id'))
    print('name:       ', origin.get('chat_name') or origin.get('user_name') or entry.get('display_name'))
PY
```

## Common Pitfalls

1. Apagar `state.db` inteiro para um único contato.
   Isso zera todos os contatos do perfil. Não fazer.

2. Apagar só `messages`, deixando `sessions.json` apontando para a sessão antiga.
   O gateway pode continuar tentando retomar uma sessão sem transcript. Remova também a entrada do índice.

3. Apagar `session/` achando que é histórico.
   Isso é Baileys/WhatsApp e pode exigir QR novo.

4. Editar SQLite com gateway rodando.
   Pode gerar lock, estado fantasma, WAL inconsistente ou perda parcial. Pare somente o gateway do perfil por PID.

5. Usar `pkill -f "hermes gateway run"`.
   Derruba todos os perfis. Sempre matar pelo PID em `$PROFILE/gateway.pid` ou validar `gateway.lock` do perfil.

6. Contato ambíguo.
   Se a busca retorna mais de um candidato, não escolha no chute. Pergunte.

7. Não fazer backup.
   Sempre copie `state.db*`, `sessions/sessions.json` e, quando for editar home channel, `.env` antes da limpeza.

8. Comando grande demais em operação destrutiva.
   Evite scripts monolíticos que descobrem alvo, param gateway, editam `.env`, apagam SQLite/JSON e religam tudo de uma vez. Isso dificulta aprovação, auditoria e correção quando aparece ambiguidade. Divida em etapas pequenas e pare no primeiro ponto que exigir decisão.

9. Contar entradas em vez de `session_id` único.
   A mesma conversa pode aparecer como uma entrada em `sessions.json` e outra em `state.db`. Para decidir ambiguidade, agrupe por `session_id`; só trate como múltiplos alvos quando houver múltiplos `session_id` distintos.

## Verification Checklist

- [ ] Perfil confirmado.
- [ ] Contato informado; se ausente, pergunta feita ao admin.
- [ ] Candidatos encontrados e não ambíguos.
- [ ] Gateway do perfil parado por PID, sem `pkill` global.
- [ ] Backup criado em `$PROFILE/backups/reset-profile-history-<timestamp>/` (`state.db*`, `sessions/sessions.json` e `.env` se ele será editado).
- [ ] Entrada do contato removida de `sessions/sessions.json`.
- [ ] Mensagens da sessão removidas de `state.db.messages`.
- [ ] Sessão removida de `state.db.sessions`.
- [ ] `session/` Baileys não foi tocado.
- [ ] Gateway subiu novamente com `HERMES_HOME=$PROFILE`.
- [ ] Próxima mensagem do contato cria nova sessão limpa.
