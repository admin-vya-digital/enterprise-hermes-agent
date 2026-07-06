"""
whatsapp-mixed plugin — roteamento para WHATSAPP_MODE=mixed.

Instalado por perfil em <profile>/plugins/whatsapp-mixed/ (copiado por
provision.py). No-op completo se WHATSAPP_MODE != "mixed" — não interfere
em perfis "bot" ou "self-chat".

Regras (via hook pre_gateway_dispatch, roda ANTES do LLM):

1. Mensagem fromMe no próprio self-chat do dono (chat_id == WHATSAPP_OWNER_NUMBER)
   -> deixa passar normal (assistente pessoal).
2. Mensagem fromMe em QUALQUER outro chat (dono respondendo manualmente um
   cliente) -> silencia aquele chat por SILENCE_SECONDS (janela deslizante:
   cada mensagem manual do dono reseta o timer) e pula o LLM (o dono já
   respondeu, o bot não deve responder de novo).
3. Mensagem de cliente (!fromMe) enquanto o chat está silenciado -> NÃO
   processa agora; grava em arquivo (pending) e pula o LLM.
4. Mensagem de cliente depois que o silêncio expirou -> checa o arquivo de
   pendências daquele chat; se houver mensagem(ns) acumulada(s), funde no
   texto atual (o agente responde ao que ficou pra trás); se não houver
   nada pendente, segue a vida normalmente.

Estado persistido em <profile>/contacts/_silence/<chat_id_sanitizado>.json,
protegido por flock — sobrevive a restart do gateway (backlog não se perde
se o processo cair no meio da janela de silêncio).

Auto-flush ao expirar o silêncio: como o sistema de plugins do Hermes não
tem nenhum hook periódico (só reage a eventos), o silêncio nunca "acorda
sozinho" por conta própria. Por isso, a cada mensagem manual do dono
(_refresh_silence), agendamos/reagendamos um cron job "once" por-perfil
que dispara exatamente quando o silêncio expira: um script apara as
pendências daquele chat (esvazia o arquivo) e, se houver algo, o agente
responde usando esse conteúdo como contexto e entrega via
`deliver=whatsapp:<chat_id>` — sem depender de uma nova mensagem do
cliente para acordar o fluxo. Se não houver nada pendente na hora, o
script não imprime nada e o job é pulado sem chamar o LLM.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SILENCE_SECONDS = 600  # 10 min, janela deslizante a partir da última msg do dono
FLUSH_JOB_NAME_PREFIX = "whatsapp-mixed-flush"

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9_.-]")


def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))


def _safe_chat_name(chat_id: str) -> str:
    return _SAFE_CHARS.sub("_", chat_id) or "unknown"


def _state_path(chat_id: str) -> Path:
    d = _hermes_home() / "contacts" / "_silence"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{_safe_chat_name(chat_id)}.json"


def _with_locked_state(chat_id: str, fn):
    """Abre, tranca (flock exclusivo), deixa `fn(data)` mutar `data` em
    memória, grava atomicamente e destranca. `fn` pode retornar um valor
    para o chamador."""
    path = _state_path(chat_id)
    path.touch(exist_ok=True)
    lockfile = path.with_suffix(".lock")
    with open(lockfile, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            try:
                text = path.read_text(encoding="utf-8").strip()
                data = json.loads(text) if text else {}
            except Exception:
                data = {}
            data.setdefault("silence_until", 0.0)
            data.setdefault("pending", [])

            result = fn(data)

            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data), encoding="utf-8")
            tmp.replace(path)
            return result
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def _refresh_silence(chat_id: str) -> None:
    silence_until = time.time() + SILENCE_SECONDS

    def op(data: dict) -> None:
        data["silence_until"] = silence_until
    _with_locked_state(chat_id, op)
    _schedule_flush_job(chat_id, silence_until)


def _flush_script_path(chat_id: str) -> Path:
    d = _hermes_home() / "scripts"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"whatsapp_mixed_flush_{_safe_chat_name(chat_id)}.py"


def _ensure_flush_script(chat_id: str) -> str:
    """Garante o script (idempotente) que esvazia as pendências desse chat.
    Usado como `script=` do cron job — roda no fire-time, não no schedule-time,
    então sempre reflete o pending mais atual. Retorna o nome do arquivo
    (relativo a HERMES_HOME/scripts/, como o cron exige)."""
    path = _flush_script_path(chat_id)
    if not path.exists():
        safe_chat = _safe_chat_name(chat_id)
        script = (
            '"""Gerado por whatsapp-mixed — esvazia pendências do chat '
            f'{chat_id!r} para o cron job de flush."""\n'
            "import fcntl, json, os\n"
            "from pathlib import Path\n\n"
            'STATE = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes")) '
            f'/ "contacts" / "_silence" / "{safe_chat}.json"\n\n\n'
            "def main():\n"
            "    if not STATE.exists():\n"
            "        return\n"
            '    lockfile = STATE.with_suffix(".lock")\n'
            "    lockfile.touch(exist_ok=True)\n"
            '    with open(lockfile, "w") as lf:\n'
            "        fcntl.flock(lf, fcntl.LOCK_EX)\n"
            "        try:\n"
            "            try:\n"
            '                data = json.loads(STATE.read_text(encoding="utf-8") or "{}")\n'
            "            except Exception:\n"
            "                data = {}\n"
            '            pending = data.get("pending") or []\n'
            "            if not pending:\n"
            "                return\n"
            '            data["pending"] = []\n'
            '            tmp = STATE.with_suffix(".tmp")\n'
            '            tmp.write_text(json.dumps(data), encoding="utf-8")\n'
            "            tmp.replace(STATE)\n"
            "        finally:\n"
            "            fcntl.flock(lf, fcntl.LOCK_UN)\n"
            '    print("\\n".join(pending))\n\n\n'
            'if __name__ == "__main__":\n'
            "    main()\n"
        )
        path.write_text(script, encoding="utf-8")
    return path.name


def _schedule_flush_job(chat_id: str, run_at_epoch: float) -> None:
    """Agenda (ou reagenda) um cron job one-shot que entrega ao cliente a
    resposta às mensagens pendentes assim que o silêncio expira — mesmo sem
    uma nova mensagem dele para disparar o fluxo."""
    try:
        from cron.jobs import create_job, list_jobs, update_job
    except Exception:
        return

    run_at_iso = datetime.fromtimestamp(run_at_epoch, tz=timezone.utc).isoformat()
    job_name = f"{FLUSH_JOB_NAME_PREFIX}-{_safe_chat_name(chat_id)}"
    script_name = _ensure_flush_script(chat_id)
    prompt = (
        "Enquanto você (o dono) respondia manualmente esta conversa, o cliente "
        "enviou mensagem(ns) que ficaram represadas. O texto delas está no "
        "'Script Output' acima. Responda a essas mensagens agora, como se "
        "tivesse acabado de recebê-las."
    )

    try:
        existing = next(
            (j for j in list_jobs(include_disabled=True) if j.get("name") == job_name),
            None,
        )
    except Exception:
        existing = None

    try:
        if existing:
            update_job(existing["id"], {
                "schedule": run_at_iso,
                "next_run_at": run_at_iso,
                "state": "scheduled",
                "enabled": True,
                "repeat": {"times": 1, "completed": 0},
            })
        else:
            create_job(
                prompt=prompt,
                schedule=run_at_iso,
                name=job_name,
                deliver=f"whatsapp:{chat_id}",
                script=script_name,
            )
    except Exception:
        pass


def _get_silence_until(chat_id: str) -> float:
    def op(data: dict) -> float:
        return float(data.get("silence_until", 0.0))
    return _with_locked_state(chat_id, op)


def _append_pending(chat_id: str, text: str) -> None:
    if not text:
        return

    def op(data: dict) -> None:
        data["pending"].append(text)
    _with_locked_state(chat_id, op)


def _pop_pending(chat_id: str) -> list[str]:
    def op(data: dict) -> list[str]:
        items = list(data.get("pending", []))
        data["pending"] = []
        return items
    return _with_locked_state(chat_id, op)


def _handle_pre_gateway_dispatch(
    event: Any = None,
    gateway: Any = None,
    session_store: Any = None,
    **_: Any,
) -> Optional[dict]:
    try:
        if event is None or getattr(event, "source", None) is None:
            return None

        platform = getattr(event.source.platform, "value", str(event.source.platform))
        if platform != "whatsapp":
            return None

        mode = os.environ.get("WHATSAPP_MODE", "bot")
        if mode != "mixed":
            return None

        owner_number = os.environ.get("WHATSAPP_OWNER_NUMBER", "").strip()
        if not owner_number:
            # Modo mixed sem dono configurado — nada pra rotear, deixa passar.
            return None

        raw = event.raw_message if isinstance(event.raw_message, dict) else {}
        from_me = bool(raw.get("fromMe"))
        chat_id = event.source.chat_id or ""
        chat_number = chat_id.split("@", 1)[0].split(":", 1)[0]
        is_self_chat = chat_number == owner_number

        if from_me:
            if is_self_chat:
                # Dono conversando com o próprio assistente — processa normal.
                return None
            # Dono respondeu manualmente um cliente: silencia essa conversa
            # (janela deslizante) e não deixa o LLM responder de novo.
            _refresh_silence(chat_id)
            return {"action": "skip", "reason": "owner-manual-message"}

        if is_self_chat:
            # Não deveria acontecer (cliente não fala "como" o próprio dono),
            # mas por segurança deixa passar sem tratamento especial.
            return None

        now = time.time()
        if now < _get_silence_until(chat_id):
            # Conversa silenciada — guarda a mensagem do cliente pra depois,
            # não aciona o LLM agora.
            _append_pending(chat_id, event.text or "")
            return {"action": "skip", "reason": "owner-silenced-window"}

        # Silêncio expirado (ou nunca existiu). Se sobrou mensagem pendente
        # de quando estava silenciado, funde com a atual antes de responder.
        pending = _pop_pending(chat_id)
        if pending:
            merged = "\n".join([*pending, event.text or ""]).strip()
            return {"action": "rewrite", "text": merged}

        return None
    except Exception:
        # Nunca derruba o gateway por causa do plugin.
        return None


def register(ctx) -> None:
    ctx.register_hook("pre_gateway_dispatch", _handle_pre_gateway_dispatch)
