#!/usr/bin/env python3
"""
app-vya-digital — dashboard adaptado do cr:ux para a infra da enterprise-hermes-agent.

Portado de crux/dashboard/server.py. Diferenças de arquitetura em relação ao
original (ver ARCHITECTURE_NOTES.md nesta pasta para o detalhe completo):

  - Sem supervisord/PID control neste container: os gateways por agente rodam
    dentro do container `vya-workforce-api`, em outro namespace de processo.
    Tudo que era start/stop/restart por PID ou supervisorctl foi removido ou
    substituído por chamadas ao vyadigital_api (ver vya_api_client.py).
  - HERMES_ROOT aponta para o volume compartilhado (`/app/profiles` no
    docker-compose da empresa), não mais `~/.hermes/profiles`.
  - Módulos locais (produto.py, appointments.py) vêm de ./lib, copiados
    verbatim do crux-api/server — são puros (só recebem um Path do perfil,
    sem dependência de container).
"""

import asyncio
import json
import os
import re
import sqlite3
import sys
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
from aiohttp import web

_LIB_DIR = Path(__file__).resolve().parent / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

import vya_api_client  # noqa: E402 — cliente HTTP para o vyadigital_api (whatsapp/QR)

HERMES_ROOT = Path(os.environ.get("HERMES_HOME_ROOT", "/app")) / "profiles"
PORT = int(os.environ.get("HERMES_DASH_PORT", "9119"))
SAFE_ID = re.compile(r"^[\w\-]+$")
LOG_SOURCES = {"gateway": "gateway.log", "bridge": "bridge.log",
               "errors": "errors.log", "agent": "agent.log", "leads": "leads.log",
               "appointments": "appointments.log"}


# ─── Helpers ──────────────────────────────────────────────────────────────────

# Sem PID/kill(pid, 0) aqui: o gateway roda em outro container (namespace de
# PID isolado), então "vivo" não pode ser checado por sinal local — só pelo
# que o próprio gateway escreve em gateway_state.json (arquivo no volume
# compartilhado, comum aos dois forks do hermes-agent) ou pela API.
# TODO(verificar): confirmar o valor exato que gateway_state.json usa pra
# "rodando" no fork da empresa antes de confiar neste campo em produção.

def _gateway_state(d: Path) -> dict:
    f = d / "gateway_state.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text())
    except Exception:
        return {}


def _profile_status(d: Path) -> dict:
    gstate = _gateway_state(d)
    online = str(gstate.get("gateway_state", "")).lower() in ("running", "online", "active")
    wa = gstate.get("platforms", {}).get("whatsapp", {})
    return {
        "online": online,
        "gateway_state": gstate.get("gateway_state", "stopped"),
        "active_agents": gstate.get("active_agents", 0),
        "whatsapp_state": wa.get("state", "unknown"),
        "updated_at": gstate.get("updated_at"),
    }


def _load_lid_phone_map(d: Path) -> dict[str, str]:
    """Read lid-mapping-{LID}_reverse.json files from session dir → {lid: phone}.

    Baileys writes one file per contact: the filename encodes the LID, the
    content is a JSON string with the E.164 phone number (no + prefix).
    Example: lid-mapping-<ROOT_ADMIN_LID>_reverse.json → "<NUMERO_EXEMPLO>"
    """
    session_dir = d / "session"
    if not session_dir.is_dir():
        return {}
    result: dict[str, str] = {}
    try:
        for f in session_dir.iterdir():
            m = re.match(r'^lid-mapping-(\d+)_reverse\.json$', f.name)
            if not m:
                continue
            lid = m.group(1)
            try:
                phone = json.loads(f.read_text().strip())
                if phone:
                    result[lid] = str(phone)
            except Exception:
                pass
    except Exception:
        pass
    return result


def _resolve_phone(user_id: str, lid_phone: dict[str, str]) -> str:
    """Given a user_id (LID or JID) and the LID→phone map, return the best
    displayable phone number.

    Precedence:
      1. LID → reverse-map file → E.164 phone (most accurate)
      2. @s.whatsapp.net → strip suffix → E.164-ish number
      3. Raw stripped ID (LID number or whatever Baileys sent)
    """
    if not user_id:
        return ""
    raw = user_id.split("@")[0] if "@" in user_id else user_id
    suffix = user_id.split("@")[1] if "@" in user_id else ""
    if suffix == "lid":
        return lid_phone.get(raw, raw)
    # @s.whatsapp.net — the raw part IS the phone (strip device suffix like :10)
    return raw.split(":")[0]


def _load_contacts(d: Path) -> dict[str, str]:
    f = d / "channel_directory.json"
    if not f.exists():
        return {}
    try:
        data = json.loads(f.read_text())
        out: dict[str, str] = {}
        for contacts in data.get("platforms", {}).values():
            for c in contacts:
                if isinstance(c, dict) and "id" in c:
                    out[c["id"]] = c.get("name") or c["id"]
        return out
    except Exception:
        return {}


def _safe_profile_path(profile_id: str) -> Path | None:
    # SAFE_ID (\w e -, sem / nem ..) já impede travessia de diretório, mas o
    # CodeQL não reconhece checagem por regex como sanitizador de path — todo
    # `d / "algo"` feito a partir do valor de retorno aparecia como "path
    # depends on a user-provided value" (dezenas de alertas, uma única causa
    # raiz). Reforça com contenção explícita via caminho resolvido +
    # relative_to(), padrão que a análise de path-injection reconhece.
    if not SAFE_ID.match(profile_id):
        return None
    root = HERMES_ROOT.resolve()
    d = (root / profile_id).resolve()
    try:
        d.relative_to(root)
    except ValueError:
        return None
    if not d.is_dir():
        return None
    return d


def _write_atomic(path: Path, content: str) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def _db_connect(db_path: Path):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _session_origins(d: Path) -> dict:
    """Map state.db session_id → origin metadata from sessions/sessions.json.

    The state.db `sessions` table stores only the sender `user_id`; whether a
    session is a group and which group/chat it belongs to lives in the on-disk
    session map (`sessions/sessions.json`). Returns {session_id: {chat_type,
    chat_id, chat_name, user_id}}.
    """
    f = d / "sessions" / "sessions.json"
    if not f.exists():
        return {}
    try:
        data = json.loads(f.read_text())
    except Exception:
        return {}
    out: dict = {}
    for entry in (data.values() if isinstance(data, dict) else []):
        if not isinstance(entry, dict):
            continue
        sid = entry.get("session_id")
        if not sid:
            continue
        origin = entry.get("origin") or {}
        out[sid] = {
            "chat_type": entry.get("chat_type") or origin.get("chat_type") or "dm",
            "chat_id": origin.get("chat_id"),
            "chat_name": entry.get("display_name") or origin.get("chat_name"),
            "user_id": origin.get("user_id"),
        }
    return out


# NOTA: crux tinha aqui _gateway_owns_profile/_stop_profile_gateway/
# _relaunch_profile_gateway — param+kill(pid)/supervisorctl pra evitar que o
# cache em memória do gateway sobrescrevesse um delete feito direto no
# state.db (ver handle_contact_delete). Removidos: o gateway roda em outro
# container aqui, sinal de PID não alcança. handle_contact_delete segue sem
# esse passo, com um risco pequeno e documentado de race (ver nota lá).
# Se a empresa expuser um endpoint de restart de agente no vyadigital_api,
# dá pra chamar ele aqui antes/depois do delete pra fechar o gap.

def _sync_cron_origins(d: Path) -> None:
    """Read jobs.json and add any new job_id → chat_id mappings to origin_map.json."""
    jobs_file = d / "cron" / "jobs.json"
    if not jobs_file.exists():
        return
    origin_map_file = d / "cron" / "origin_map.json"
    try:
        jobs = json.loads(jobs_file.read_text()).get("jobs", [])
        origin_map: dict = {}
        if origin_map_file.exists():
            origin_map = json.loads(origin_map_file.read_text())
        changed = False
        for job in jobs:
            jid = job.get("id")
            origin = job.get("origin") or {}
            chat_id = origin.get("chat_id") or origin.get("user_id") or ""
            if jid and chat_id and origin_map.get(jid) != chat_id:
                origin_map[jid] = chat_id
                changed = True
        if changed:
            _write_atomic(origin_map_file, json.dumps(origin_map, ensure_ascii=False, indent=2))
    except Exception:
        pass


def _repair_cron_user_ids(d: Path) -> None:
    """Set user_id on cron sessions with user_id=NULL using origin_map.json."""
    origin_map_file = d / "cron" / "origin_map.json"
    if not origin_map_file.exists():
        return
    try:
        origin_map = json.loads(origin_map_file.read_text())
    except Exception:
        return
    if not origin_map:
        return
    db_path = d / "state.db"
    if not db_path.exists():
        return
    try:
        conn = sqlite3.connect(str(db_path), timeout=5)
        conn.execute("PRAGMA busy_timeout=4000")
        rows = conn.execute(
            "SELECT id FROM sessions WHERE source='cron' AND user_id IS NULL"
        ).fetchall()
        repaired = 0
        for (sid,) in rows:
            parts = sid.split("_")
            job_id = parts[1] if len(parts) >= 2 else None
            if job_id:
                chat_id = origin_map.get(job_id)
                if chat_id:
                    conn.execute("UPDATE sessions SET user_id=? WHERE id=?", (chat_id, sid))
                    repaired += 1
        if repaired:
            conn.commit()
        conn.close()
    except Exception:
        pass


async def _cron_background_maintenance() -> None:
    """Every 15s: capture job origins before once-jobs auto-delete, then repair NULL user_ids."""
    while True:
        await asyncio.sleep(15)
        try:
            if HERMES_ROOT.exists():
                for d in HERMES_ROOT.iterdir():
                    if d.is_dir():
                        _sync_cron_origins(d)
                        _repair_cron_user_ids(d)
        except Exception:
            pass


def _cron_job_ids_for_user(profile_dir: Path, user_id: str) -> list[str]:
    """Return job_ids whose origin.chat_id matches user_id.

    Reads origin_map.json first (persistent — survives job deletion), then
    falls back to the current jobs.json for jobs not yet in the map.
    """
    raw_uid = user_id.split("@")[0]
    result: list[str] = []
    seen: set[str] = set()

    def _maybe_add(oid: str, jid: str) -> None:
        if jid and jid not in seen and (oid == user_id or oid.split("@")[0] == raw_uid):
            result.append(jid)
            seen.add(jid)

    origin_map_file = profile_dir / "cron" / "origin_map.json"
    if origin_map_file.exists():
        try:
            for jid, chat_id in json.loads(origin_map_file.read_text()).items():
                _maybe_add(chat_id, jid)
        except Exception:
            pass

    jobs_file = profile_dir / "cron" / "jobs.json"
    if jobs_file.exists():
        try:
            for job in json.loads(jobs_file.read_text()).get("jobs", []):
                origin = job.get("origin") or {}
                oid = origin.get("chat_id") or origin.get("user_id") or ""
                _maybe_add(oid, job.get("id", ""))
        except Exception:
            pass

    return result


# ─── /api/profiles ────────────────────────────────────────────────────────────

async def handle_profiles(request: web.Request) -> web.Response:
    ident = request.get("identity") or {}
    allowed = ident.get("profiles")  # None = all (admin)
    profiles = []
    if HERMES_ROOT.exists():
        for d in sorted(HERMES_ROOT.iterdir()):
            if d.is_dir():
                if allowed is not None and d.name not in allowed:
                    continue
                profiles.append({
                    "id": d.name,
                    "has_db": (d / "state.db").exists(),
                    **_profile_status(d),
                })
    return web.json_response(profiles)


# ─── /api/profiles/{id}/overview ──────────────────────────────────────────────

async def handle_overview(req: web.Request) -> web.Response:
    d = _safe_profile_path(req.match_info["profile_id"])
    if not d:
        raise web.HTTPNotFound()

    gstate = _gateway_state(d)
    online = str(gstate.get("gateway_state", "")).lower() in ("running", "online", "active")
    wa = gstate.get("platforms", {}).get("whatsapp", {})

    stats = {
        "new_contacts_today": 0, "cost_today": 0.0,
        "contacts_total": 0, "cost_total": 0.0,
        "tokens_in_total": 0, "tokens_out_total": 0,
        "received_today": 0, "sent_today": 0,
        "received_total": 0, "sent_total": 0,
        "waiting_reply": 0,
        "chart": [],
    }

    db_path = d / "state.db"
    if db_path.exists():
        try:
            conn = _db_connect(db_path)
            cur = conn.cursor()

            # Session-level aggregates + new contacts today
            cur.execute("""
                SELECT
                  COALESCE(SUM(estimated_cost_usd) FILTER (WHERE date(started_at,'unixepoch','localtime')=date('now','localtime')),0) AS c_today,
                  COALESCE(SUM(estimated_cost_usd),0) AS c_total,
                  COALESCE(SUM(input_tokens),0) AS ti_total,
                  COALESCE(SUM(output_tokens),0) AS to_total
                FROM sessions WHERE archived=0 OR archived IS NULL
            """)
            r = cur.fetchone()
            if r:
                stats.update({
                    "cost_today": round(r[0], 6),
                    "cost_total": round(r[1], 4),
                    "tokens_in_total": r[2], "tokens_out_total": r[3],
                })

            # Contatos novos hoje = user_ids cuja primeira sessão foi hoje
            cur.execute("""
                SELECT
                  COUNT(*) FILTER (WHERE date(first_seen,'unixepoch','localtime')=date('now','localtime')) AS new_today,
                  COUNT(*) AS total
                FROM (
                  SELECT user_id, MIN(started_at) AS first_seen
                  FROM sessions
                  WHERE (archived=0 OR archived IS NULL) AND user_id IS NOT NULL
                  GROUP BY user_id
                )
            """)
            rc = cur.fetchone()
            if rc:
                stats.update({
                    "new_contacts_today": rc[0],
                    "contacts_total": rc[1],
                })

            # Message counts by role — "sent" só conta respostas reais
            # (assistant com conteúdo e sem tool_calls; notas internas ficam de fora)
            cur.execute("""
                SELECT
                  COALESCE(SUM(CASE WHEN m.role='user'
                    AND date(s.started_at,'unixepoch','localtime')=date('now','localtime') THEN 1 END),0) AS mr_today,
                  COALESCE(SUM(CASE WHEN m.role='assistant'
                    AND m.content IS NOT NULL AND m.content != ''
                    AND (m.tool_calls IS NULL OR m.tool_calls = '')
                    AND date(s.started_at,'unixepoch','localtime')=date('now','localtime') THEN 1 END),0) AS ms_today,
                  COALESCE(SUM(CASE WHEN m.role='user' THEN 1 END),0) AS mr_total,
                  COALESCE(SUM(CASE WHEN m.role='assistant'
                    AND m.content IS NOT NULL AND m.content != ''
                    AND (m.tool_calls IS NULL OR m.tool_calls = '') THEN 1 END),0) AS ms_total
                FROM messages m
                JOIN sessions s ON s.id=m.session_id
                WHERE (s.archived=0 OR s.archived IS NULL)
                  AND (m.active=1 OR m.active IS NULL)
            """)
            mr = cur.fetchone()
            if mr:
                stats.update({
                    "received_today": mr[0], "sent_today": mr[1],
                    "received_total": mr[2], "sent_total": mr[3],
                })

            # Clientes esperando resposta: última mensagem real da conversa é
            # do usuário e chegou nas últimas 24h (agente pode ter travado)
            cur.execute("""
                SELECT COUNT(*) FROM (
                  SELECT s.id, MAX(m.timestamp) AS ts,
                         (SELECT role FROM messages
                          WHERE session_id=s.id AND (active=1 OR active IS NULL)
                            AND (role='user'
                                 OR (role='assistant'
                                     AND content IS NOT NULL AND content != ''
                                     AND (tool_calls IS NULL OR tool_calls = '')))
                          ORDER BY timestamp DESC, id DESC LIMIT 1) AS last_role
                  FROM sessions s JOIN messages m ON m.session_id=s.id
                  WHERE (s.archived=0 OR s.archived IS NULL) AND s.source != 'cron'
                  GROUP BY s.id
                ) WHERE last_role='user' AND ts >= strftime('%s','now','-24 hours')
            """)
            wr = cur.fetchone()
            stats["waiting_reply"] = wr[0] if wr else 0

            # Chart: last 7 days — received vs sent
            cur.execute("""
                SELECT
                  date(m.timestamp,'unixepoch','localtime') AS day,
                  SUM(CASE WHEN m.role='user' THEN 1 ELSE 0 END) AS received,
                  SUM(CASE WHEN m.role='assistant'
                    AND m.content IS NOT NULL AND m.content != ''
                    AND (m.tool_calls IS NULL OR m.tool_calls = '') THEN 1 ELSE 0 END) AS sent
                FROM messages m
                JOIN sessions s ON s.id=m.session_id
                WHERE (s.archived=0 OR s.archived IS NULL)
                  AND (m.active=1 OR m.active IS NULL)
                  AND m.timestamp >= strftime('%s', date('now','localtime','-6 days'))
                GROUP BY day ORDER BY day
            """)
            stats["chart"] = [{"day": r["day"], "received": r["received"], "sent": r["sent"]}
                               for r in cur.fetchall()]

            conn.close()
        except Exception:
            pass

    # ── Métricas de negócio: agenda, funil de leads, lembretes ────────────────
    biz = {
        "appt_today": 0, "appt_today_confirmed": 0, "appt_tomorrow": 0,
        "appt_week": 0, "appt_next": None, "agenda": [],
        "appt_pending_upcoming": 0, "appt_completed_week": 0, "appt_cancelled_week": 0,
        "leads_funnel": {}, "leads_active": 0, "leads_new_today": 0,
        "crons_active": 0, "cron_next": None,
    }

    # Nome de exibição por telefone resolvido (mesma resolução das outras abas)
    name_by_phone: dict[str, str] = {}
    try:
        lid_phone = _load_lid_phone_map(d)
        for cid, cname in _load_contacts(d).items():
            ph = _resolve_phone(cid, lid_phone)
            if ph and cname and cname != cid:
                name_by_phone[ph] = cname
    except Exception:
        pass

    appt_db = d / "appointments.db"
    if appt_db.exists():
        try:
            conn = _db_connect(appt_db)
            cur = conn.cursor()
            cur.execute("""
                SELECT
                  COUNT(*) FILTER (WHERE status IN ('scheduled','confirmed')
                                     AND date(scheduled_at,'unixepoch','localtime')=date('now','localtime')) AS today,
                  COUNT(*) FILTER (WHERE status='confirmed'
                                     AND date(scheduled_at,'unixepoch','localtime')=date('now','localtime')) AS today_conf,
                  COUNT(*) FILTER (WHERE status IN ('scheduled','confirmed')
                                     AND date(scheduled_at,'unixepoch','localtime')=date('now','localtime','+1 day')) AS tomorrow,
                  COUNT(*) FILTER (WHERE status IN ('scheduled','confirmed')
                                     AND scheduled_at >= strftime('%s','now')
                                     AND scheduled_at < strftime('%s','now','+7 days')) AS week,
                  COUNT(*) FILTER (WHERE status='scheduled'
                                     AND scheduled_at >= strftime('%s','now')) AS pending_upcoming,
                  COUNT(*) FILTER (WHERE status='completed'
                                     AND updated_at >= strftime('%s','now','-7 days')) AS completed_week,
                  COUNT(*) FILTER (WHERE status='cancelled'
                                     AND updated_at >= strftime('%s','now','-7 days')) AS cancelled_week
                FROM appointments
            """)
            r = cur.fetchone()
            if r:
                biz.update({"appt_today": r[0], "appt_today_confirmed": r[1],
                            "appt_tomorrow": r[2], "appt_week": r[3],
                            "appt_pending_upcoming": r[4],
                            "appt_completed_week": r[5], "appt_cancelled_week": r[6]})

            # Agendamentos de HOJE por profissional — só relevante quando há +1
            # profissional na escala (senão o Overview mantém os cards padrão).
            try:
                _profs = [p.get("nome", "") for p in (_produto.load(d).get("profissionais") or []) if p.get("nome")]
            except Exception:
                _profs = []
            biz["professional_count"] = len(_profs)
            if len(_profs) > 1:
                cur.execute("""
                    SELECT resource,
                           COUNT(*) AS total,
                           COUNT(*) FILTER (WHERE status='confirmed') AS conf
                    FROM appointments
                    WHERE status IN ('scheduled','confirmed')
                      AND date(scheduled_at,'unixepoch','localtime')=date('now','localtime')
                    GROUP BY resource
                """)
                _counts = {(row[0] or ""): (row[1], row[2]) for row in cur.fetchall()}
                by_prof = []
                for _name in _profs:
                    t, c = _counts.get(_name, (0, 0))
                    by_prof.append({"name": _name, "resource": _name, "total": t, "confirmed": c})
                if _counts.get("", (0, 0))[0]:  # agendamentos hoje sem profissional (legado)
                    t, c = _counts[""]
                    by_prof.append({"name": "Sem profissional", "resource": "", "total": t, "confirmed": c})
                biz["appt_today_by_professional"] = by_prof

            cur.execute("""
                SELECT id, scheduled_at, title, contact_phone, status
                FROM appointments
                WHERE status IN ('scheduled','confirmed') AND scheduled_at >= strftime('%s','now')
                ORDER BY scheduled_at ASC LIMIT 7
            """)
            agenda_all = [{
                "id": row[0],
                "ts": row[1], "title": row[2] or "Atendimento",
                "phone": row[3], "name": name_by_phone.get(row[3]),
                "status": row[4],
            } for row in cur.fetchall()]
            biz["appt_next"] = agenda_all[0] if agenda_all else None
            biz["agenda"] = agenda_all[1:]
            conn.close()
        except Exception:
            pass

    leads_db = d / "leads.db"
    if leads_db.exists():
        try:
            conn = _db_connect(leads_db)
            cur = conn.cursor()
            cur.execute("SELECT phase, COUNT(*) FROM leads GROUP BY phase")
            funnel = {row[0]: row[1] for row in cur.fetchall()}
            biz["leads_funnel"] = funnel
            biz["leads_active"] = sum(funnel.get(p, 0) for p in ("phase_one", "phase_two", "phase_three"))
            cur.execute("""
                SELECT COUNT(*) FROM (
                  SELECT contact_phone, MIN(timestamp) AS first_seen
                  FROM lead_phase_history GROUP BY contact_phone
                ) WHERE date(first_seen,'unixepoch','localtime')=date('now','localtime')
            """)
            rn = cur.fetchone()
            biz["leads_new_today"] = rn[0] if rn else 0
            conn.close()
        except Exception:
            pass

    jobs_file = d / "cron" / "jobs.json"
    if jobs_file.exists():
        try:
            jobs = json.loads(jobs_file.read_text()).get("jobs", [])
            active = [j for j in jobs
                      if j.get("enabled", True) and j.get("state") != "done"
                      and (j.get("next_run_at") or j.get("next_run"))]
            biz["crons_active"] = len(active)
            nexts = sorted(str(j.get("next_run_at") or j.get("next_run")) for j in active)
            biz["cron_next"] = nexts[0] if nexts else None
        except Exception:
            pass

    return web.json_response({
        "online": online,
        "gateway_state": gstate.get("gateway_state", "stopped"),
        "active_agents": gstate.get("active_agents", 0),
        "whatsapp_state": wa.get("state", "unknown"),
        "whatsapp_error": wa.get("error_message"),
        "updated_at": gstate.get("updated_at"),
        **stats,
        **biz,
    })


# ─── /api/profiles/{id}/conversations ─────────────────────────────────────────

async def handle_conversations(req: web.Request) -> web.Response:
    d = _safe_profile_path(req.match_info["profile_id"])
    if not d:
        raise web.HTTPNotFound()

    db_path = d / "state.db"
    if not db_path.exists():
        return web.json_response([])

    contacts = _load_contacts(d)
    lid_phone = _load_lid_phone_map(d)
    origins = _session_origins(d)
    try:
        conn = _db_connect(db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT s.id, s.source, s.user_id, s.title,
                   s.started_at, s.ended_at,
                   (SELECT COUNT(*) FROM messages mc
                    WHERE mc.session_id = s.id
                      AND (mc.active = 1 OR mc.active IS NULL)
                      AND (mc.role = 'user'
                           OR (mc.role = 'assistant'
                               AND mc.content IS NOT NULL AND mc.content != ''
                               AND (mc.tool_calls IS NULL OR mc.tool_calls = '')))
                   ) AS message_count,
                   s.input_tokens, s.output_tokens, s.estimated_cost_usd,
                   m.content AS last_content, m.role AS last_role, m.timestamp AS last_ts
            FROM sessions s
            LEFT JOIN messages m ON m.id = (
                SELECT id FROM messages
                WHERE session_id = s.id
                  AND (active = 1 OR active IS NULL)
                  AND (role = 'user'
                       OR (role = 'assistant'
                           AND content IS NOT NULL AND content != ''
                           AND (tool_calls IS NULL OR tool_calls = '')))
                ORDER BY timestamp DESC, id DESC LIMIT 1
            )
            WHERE (s.archived = 0 OR s.archived IS NULL)
              AND s.source != 'cron'
            ORDER BY COALESCE(m.timestamp, s.started_at) DESC LIMIT 200
        """)
        rows = cur.fetchall()
        conn.close()
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

    def _preview(raw):
        if not raw:
            return ""
        text = raw
        if raw.startswith("[") or raw.startswith("{"):
            try:
                p = json.loads(raw)
                if isinstance(p, list):
                    text = " ".join(b.get("text", "") for b in p if isinstance(b, dict) and b.get("type") == "text")
                elif isinstance(p, dict) and "output" in p:
                    text = str(p["output"])
            except Exception:
                pass
        return (text or "")[:80].replace("\n", " ")

    paused_ids = _paused_chat_ids(d)

    result = []
    for r in rows:
        origin = origins.get(r["id"]) or {}
        uid = r["user_id"] or origin.get("user_id") or ""
        phone = _resolve_phone(uid, lid_phone)
        participant_name = contacts.get(uid) or origin.get("chat_name") or phone or "(automação)"
        is_group = origin.get("chat_type") == "group"
        chat_id = origin.get("chat_id")
        group_name = origin.get("chat_name") if is_group else None
        name = group_name or participant_name
        safe_chat = re.sub(r'[^\w\-]', '_', str(chat_id or uid or ""))
        result.append({
            "id": r["id"], "source": r["source"], "user_id": uid,
            "contact_name": name, "phone": phone,
            "is_group": is_group, "chat_type": origin.get("chat_type") or "dm",
            "chat_id": chat_id, "group_name": group_name,
            "participant_name": participant_name,
            "started_at": r["started_at"], "ended_at": r["ended_at"],
            "last_interaction_at": r["last_ts"] or r["started_at"],
            "last_message": _preview(r["last_content"]),
            "last_role": r["last_role"],
            "message_count": r["message_count"], "input_tokens": r["input_tokens"],
            "output_tokens": r["output_tokens"], "estimated_cost_usd": r["estimated_cost_usd"],
            "paused": safe_chat in paused_ids,
        })
    return web.json_response(result)


# ─── /api/profiles/{id}/conversations/{sid}/messages ──────────────────────────

async def handle_messages(req: web.Request) -> web.Response:
    d = _safe_profile_path(req.match_info["profile_id"])
    sid = req.match_info["session_id"]
    if not d or not SAFE_ID.match(sid):
        raise web.HTTPNotFound()

    db_path = d / "state.db"
    if not db_path.exists():
        return web.json_response([])

    try:
        conn = _db_connect(db_path)
        cur = conn.cursor()

        # Regular session messages
        cur.execute("""
            SELECT id, role, content, tool_name, tool_call_id,
                   timestamp, token_count, finish_reason,
                   CASE WHEN tool_calls IS NOT NULL AND tool_calls != ''
                        THEN 1 ELSE 0 END AS has_tool_calls
            FROM messages
            WHERE session_id=? AND (active=1 OR active IS NULL)
              AND role NOT IN ('session_meta')
            ORDER BY timestamp ASC, id ASC
        """, (sid,))
        msgs = [dict(r) for r in cur.fetchall()]

        # Merge cron-delivered assistant messages into this conversation.
        # Two strategies (both run; dedup by message id):
        #   1. job_id LIKE patterns via origin_map/jobs.json (handles user_id=NULL cron sessions)
        #   2. direct s.user_id match (handles sessions repaired with explicit user_id)
        cur.execute("SELECT user_id FROM sessions WHERE id=?", (sid,))
        sess_row = cur.fetchone()
        user_id = sess_row["user_id"] if sess_row else None
        if user_id:
            seen_ids: set = {m["id"] for m in msgs}

            # Job name lookup for wrapper display in the dashboard
            job_names: dict[str, str] = {}
            jobs_file = d / "cron" / "jobs.json"
            if jobs_file.exists():
                try:
                    for job in json.loads(jobs_file.read_text()).get("jobs", []):
                        jid = job.get("id", "")
                        if jid:
                            job_names[jid] = job.get("name") or ""
                except Exception:
                    pass

            def _enrich_cron(row) -> dict:
                msg = dict(row)
                msg["_cron"] = True
                cron_sid = msg.pop("cron_session_id", "") or ""
                parts = cron_sid.split("_")
                job_id = parts[1] if len(parts) >= 2 else ""
                msg["_cron_job_name"] = job_names.get(job_id, "")
                return msg

            cron_job_ids = _cron_job_ids_for_user(d, user_id)
            if cron_job_ids:
                like_clauses = " OR ".join("s.id LIKE ?" for _ in cron_job_ids)
                patterns = [f"cron_{jid}_%" for jid in cron_job_ids]
                cur.execute(f"""
                    SELECT m.id, m.role, m.content, m.tool_name, m.tool_call_id,
                           m.timestamp, m.token_count, m.finish_reason,
                           s.id AS cron_session_id
                    FROM messages m
                    JOIN sessions s ON s.id = m.session_id
                    WHERE ({like_clauses})
                      AND s.source='cron'
                      AND m.role='assistant'
                      AND (m.active=1 OR m.active IS NULL)
                      AND (m.content IS NOT NULL AND m.content != '')
                """, patterns)
                for row in cur.fetchall():
                    if row["id"] not in seen_ids:
                        msgs.append(_enrich_cron(row))
                        seen_ids.add(row["id"])

            # Fallback: cron sessions with user_id set explicitly.
            cur.execute("""
                SELECT m.id, m.role, m.content, m.tool_name, m.tool_call_id,
                       m.timestamp, m.token_count, m.finish_reason,
                       s.id AS cron_session_id
                FROM messages m
                JOIN sessions s ON s.id = m.session_id
                WHERE s.user_id = ?
                  AND s.source = 'cron'
                  AND m.role = 'assistant'
                  AND (m.active=1 OR m.active IS NULL)
                  AND (m.content IS NOT NULL AND m.content != '')
            """, (user_id,))
            for row in cur.fetchall():
                if row["id"] not in seen_ids:
                    msgs.append(_enrich_cron(row))
                    seen_ids.add(row["id"])

        conn.close()
        msgs.sort(key=lambda m: (m.get("timestamp") or 0, m.get("id", "")))
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

    return web.json_response(msgs)


# ─── /api/profiles/{id}/soul ──────────────────────────────────────────────────

async def handle_get_soul(req: web.Request) -> web.Response:
    d = _safe_profile_path(req.match_info["profile_id"])
    if not d:
        raise web.HTTPNotFound()
    f = d / "SOUL.md"
    return web.json_response({"content": f.read_text("utf-8") if f.exists() else ""})


async def handle_set_soul(req: web.Request) -> web.Response:
    d = _safe_profile_path(req.match_info["profile_id"])
    if not d:
        raise web.HTTPNotFound()
    body = await req.json()
    _write_atomic(d / "SOUL.md", body.get("content", ""))
    return web.json_response({"ok": True})


# ─── /api/profiles/{id}/produto ───────────────────────────────────────────────

async def handle_get_produto(req: web.Request) -> web.Response:
    d = _safe_profile_path(req.match_info["profile_id"])
    if not d:
        raise web.HTTPNotFound()
    f = d / "produto.md"
    return web.json_response({"content": f.read_text("utf-8") if f.exists() else ""})


async def handle_set_produto(req: web.Request) -> web.Response:
    d = _safe_profile_path(req.match_info["profile_id"])
    if not d:
        raise web.HTTPNotFound()
    body = await req.json()
    _write_atomic(d / "produto.md", body.get("content", ""))
    return web.json_response({"ok": True})


# ─── /api/profiles/{id}/produto-config (produto.yaml estruturado) ─────────────
# Fonte única do negócio. Mesmo módulo (produto.py) usado pela skill do agente
# e pelo motor de agendamento — dashboard, agente e capacidade nunca divergem.

async def handle_get_produto_config(req: web.Request) -> web.Response:
    d = _safe_profile_path(req.match_info["profile_id"])
    if not d:
        raise web.HTTPNotFound()
    return web.json_response({"config": _produto.load(d)})


async def handle_set_produto_config(req: web.Request) -> web.Response:
    d = _safe_profile_path(req.match_info["profile_id"])
    if not d:
        raise web.HTTPNotFound()
    body = await req.json()
    data = body.get("config")
    if not isinstance(data, dict):
        return web.json_response({"ok": False, "errors": ["payload sem 'config'"]}, status=400)
    errs = _produto.validate(data)
    if errs:
        return web.json_response({"ok": False, "errors": errs}, status=400)
    try:
        _produto._atomic_save(d, data)
    except ValueError as e:
        return web.json_response({"ok": False, "errors": [str(e)]}, status=400)
    return web.json_response({"ok": True, "config": _produto.load(d)})


# ─── /api/base/{fname} ────────────────────────────────────────────────────────

_BASE_FILES = {"soul": "SOUL.md", "produto": "produto.md"}


async def handle_get_base(req: web.Request) -> web.Response:
    fname = req.match_info.get("fname", "")
    if fname not in _BASE_FILES:
        raise web.HTTPNotFound()
    root = Path(os.environ.get("HERMES_HOME_ROOT", Path.home() / ".hermes"))
    f = root / "profile-base" / _BASE_FILES[fname]
    return web.json_response({"content": f.read_text("utf-8") if f.exists() else ""})


# ─── /api/profiles/{id}/cron ──────────────────────────────────────────────────

async def handle_cron(req: web.Request) -> web.Response:
    d = _safe_profile_path(req.match_info["profile_id"])
    if not d:
        raise web.HTTPNotFound()

    # Configured jobs — capture origins before once-jobs auto-delete, then repair NULL user_ids
    jobs_file = d / "cron" / "jobs.json"
    jobs = []
    if jobs_file.exists():
        try:
            jobs = json.loads(jobs_file.read_text()).get("jobs", [])
        except Exception:
            pass
    _sync_cron_origins(d)
    _repair_cron_user_ids(d)

    origin_map_file = d / "cron" / "origin_map.json"

    # Enrich origin with resolved phone
    lid_phone = _load_lid_phone_map(d)
    for job in jobs:
        origin = job.get("origin") if isinstance(job.get("origin"), dict) else None
        if origin:
            uid = origin.get("user_id") or origin.get("chat_id") or ""
            if uid:
                origin["phone"] = _resolve_phone(uid, lid_phone)

    # Build job_id → job map for history enrichment
    job_map = {j["id"]: j for j in jobs}

    # Load persistent origin_map (survives job deletion) and contacts for name lookup
    contacts = _load_contacts(d)
    _origin_map: dict = {}
    if origin_map_file.exists():
        try:
            _origin_map = json.loads(origin_map_file.read_text())
        except Exception:
            pass

    # Execution history from state.db
    history = []
    db_path = d / "state.db"
    if db_path.exists():
        try:
            conn = _db_connect(db_path)
            cur = conn.cursor()
            cur.execute("""
                SELECT s.id, s.started_at, s.ended_at,
                       (SELECT COUNT(*) FROM messages mc
                        WHERE mc.session_id = s.id
                          AND (mc.active = 1 OR mc.active IS NULL)
                          AND (mc.role = 'user'
                               OR (mc.role = 'assistant'
                                   AND mc.content IS NOT NULL AND mc.content != ''
                                   AND (mc.tool_calls IS NULL OR mc.tool_calls = '')))
                       ) AS message_count,
                       s.input_tokens, s.output_tokens, s.estimated_cost_usd, s.end_reason,
                       (SELECT m.content
                        FROM messages m WHERE m.session_id = s.id AND m.role='assistant'
                          AND (m.active=1 OR m.active IS NULL)
                          AND m.content IS NOT NULL AND m.content != ''
                        ORDER BY m.id DESC LIMIT 1) AS sent_message
                FROM sessions s WHERE s.source='cron'
                ORDER BY s.started_at DESC LIMIT 100
            """)
            _TRUNC_MARKER = "seguinte mensagem"
            for r in cur.fetchall():
                parts = r["id"].split("_")
                job_id = parts[1] if len(parts) >= 2 else None
                job = job_map.get(job_id) if job_id else None

                # Task name from job name, truncated at verbose preamble markers
                raw_name = (job.get("name") or "") if job else ""
                idx = raw_name.lower().find(_TRUNC_MARKER)
                task_name = raw_name[:idx + len(_TRUNC_MARKER)] if idx != -1 else raw_name

                # Contact info: prefer live job origin, fall back to origin_map
                origin_chat_id = None
                if job:
                    origin = job.get("origin") or {}
                    origin_chat_id = origin.get("chat_id") or origin.get("user_id")
                if not origin_chat_id and job_id:
                    origin_chat_id = _origin_map.get(job_id)
                contact_name = contacts.get(origin_chat_id) if origin_chat_id else None
                contact_phone = _resolve_phone(origin_chat_id, lid_phone) if origin_chat_id else None

                history.append({
                    "session_id": r["id"], "job_id": job_id,
                    "task_name": task_name or None,
                    "sent_message": (r["sent_message"] or "")[:200] or None,
                    "contact_chat_id": origin_chat_id,
                    "contact_name": contact_name,
                    "contact_phone": contact_phone,
                    "started_at": r["started_at"], "ended_at": r["ended_at"],
                    "message_count": r["message_count"],
                    "input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"],
                    "estimated_cost_usd": r["estimated_cost_usd"],
                    "end_reason": r["end_reason"],
                })
            conn.close()
        except Exception:
            pass

    return web.json_response({"jobs": jobs, "history": history})


# ─── /api/profiles/{id}/cron/{job_id} DELETE ─────────────────────────────────

async def handle_delete_cron_job(req: web.Request) -> web.Response:
    d = _safe_profile_path(req.match_info["profile_id"])
    job_id = req.match_info["job_id"]
    if not d or not SAFE_ID.match(job_id):
        raise web.HTTPNotFound()
    jobs_file = d / "cron" / "jobs.json"
    if not jobs_file.exists():
        raise web.HTTPNotFound()
    try:
        data = json.loads(jobs_file.read_text())
        jobs = data.get("jobs", [])
        new_jobs = [j for j in jobs if str(j.get("id", "")) != job_id]
        if len(new_jobs) == len(jobs):
            raise web.HTTPNotFound()
        data["jobs"] = new_jobs
        _write_atomic(jobs_file, json.dumps(data, ensure_ascii=False, indent=2))
    except web.HTTPException:
        raise
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)
    return web.json_response({"ok": True})


# ─── /api/profiles/{id}/logs ──────────────────────────────────────────────────

async def handle_logs(req: web.Request) -> web.Response:
    d = _safe_profile_path(req.match_info["profile_id"])
    if not d:
        raise web.HTTPNotFound()

    source = req.rel_url.query.get("source", "gateway")
    n = min(int(req.rel_url.query.get("n", "300")), 2000)

    if source not in LOG_SOURCES:
        raise web.HTTPBadRequest()

    log_file = d / "logs" / LOG_SOURCES[source]
    if not log_file.exists():
        return web.json_response({"lines": [], "source": source})

    # Read last n lines efficiently
    try:
        with log_file.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            chunk = min(size, n * 200)
            f.seek(max(0, size - chunk))
            raw = f.read().decode("utf-8", errors="replace")
        lines = raw.splitlines()[-n:]
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

    return web.json_response({"lines": lines, "source": source, "file": str(log_file)})


# ─── /api/profiles/{id}/contacts ──────────────────────────────────────────────

async def handle_contacts(req: web.Request) -> web.Response:
    d = _safe_profile_path(req.match_info["profile_id"])
    if not d:
        raise web.HTTPNotFound()

    f = d / "channel_directory.json"
    if not f.exists():
        return web.json_response({"contacts": [], "updated_at": None})

    try:
        data = json.loads(f.read_text())
    except Exception:
        return web.json_response({"contacts": [], "updated_at": None})

    lid_phone = _load_lid_phone_map(d)

    # Build first_seen map from state.db (earliest session per user_id)
    first_seen: dict[str, int] = {}
    db_path = d / "state.db"
    if db_path.exists():
        try:
            import sqlite3 as _sqlite3
            with _sqlite3.connect(str(db_path)) as _conn:
                _conn.row_factory = _sqlite3.Row
                for row in _conn.execute(
                    "SELECT user_id, MIN(started_at) AS first FROM sessions GROUP BY user_id"
                ):
                    if row["user_id"] and row["first"]:
                        first_seen[row["user_id"]] = row["first"]
        except Exception:
            pass

    contacts = []
    seen_ids: set = set()
    for platform, items in data.get("platforms", {}).items():
        for c in items:
            if isinstance(c, dict) and "id" in c:
                uid = c.get("id", "")
                seen_ids.add(uid)
                contacts.append({
                    "platform": platform,
                    "id": uid,
                    "phone": _resolve_phone(uid, lid_phone),
                    "name": c.get("name"),
                    "type": c.get("type", "dm"),
                    "thread_id": c.get("thread_id"),
                    "first_seen": first_seen.get(uid),
                })

    # The gateway only rebuilds channel_directory.json on startup/some events,
    # so a contact who just messaged (new session in sessions.json) may not be
    # in it yet. Merge in contacts derived from sessions.json (its actual
    # source) so they show up immediately — matching the Conversas tab.
    for entry in _session_origins(d).values():
        cid = entry.get("chat_id")
        if not cid or cid in seen_ids:
            continue
        seen_ids.add(cid)
        contacts.append({
            "platform": "whatsapp",
            "id": cid,
            "phone": _resolve_phone(cid, lid_phone),
            "name": entry.get("chat_name"),
            "type": entry.get("chat_type", "dm"),
            "thread_id": None,
            "first_seen": first_seen.get(cid),
        })

    return web.json_response({"contacts": contacts, "updated_at": data.get("updated_at")})


# ─── /api/profiles/{id}/leads (kanban de qualificação) ──────────────────────────

def _leads_db(d: Path) -> Path:
    return d / "leads.db"


def _log_lead_event(d: Path, phone: str, event: str, details: str = "") -> None:
    """Escreve evento de lead no arquivo leads.log"""
    try:
        log_file = d / "logs" / "leads.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).isoformat()
        msg = f"{ts} | {event} | {phone}"
        if details:
            msg += f" | {details}"
        msg += "\n"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(msg)
    except Exception as e:
        print(f"Erro ao escrever log de leads: {e}")


async def handle_leads(req: web.Request) -> web.Response:
    """Lê leads.db do perfil local"""
    d = _safe_profile_path(req.match_info["profile_id"])
    if not d:
        raise web.HTTPNotFound()

    db_path = _leads_db(d)
    if not db_path.exists():
        return web.json_response([])

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        rows = cursor.execute("SELECT * FROM leads ORDER BY phase, qualification_score DESC").fetchall()
        conn.close()
        return web.json_response([dict(row) for row in rows])
    except Exception as e:
        print(f"Erro ao ler leads.db: {e}")
        return web.json_response([])


async def handle_lead_move(req: web.Request) -> web.Response:
    """Move lead no leads.db local"""
    d = _safe_profile_path(req.match_info["profile_id"])
    if not d:
        raise web.HTTPNotFound()

    phone = req.match_info["phone"]
    body = await req.json()
    new_phase = body.get("phase")

    if not new_phase:
        return web.json_response({"error": "phase obrigatória"}, status=400)

    db_path = _leads_db(d)
    if not db_path.exists():
        return web.json_response({"error": "leads.db não existe"}, status=404)

    try:
        now = int(time.time())
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Atualiza lead
        cursor.execute(
            "UPDATE leads SET phase = ?, phase_entered_at = ?, updated_at = ? WHERE contact_phone = ?",
            (new_phase, now, now, phone)
        )

        if cursor.rowcount == 0:
            conn.close()
            return web.json_response({"error": "lead não encontrado"}, status=404)

        # Registra histórico
        cursor.execute(
            "INSERT INTO lead_phase_history (contact_phone, from_phase, to_phase, timestamp) SELECT contact_phone, ?, ?, ? FROM leads WHERE contact_phone = ?",
            (new_phase, new_phase, now, phone)  # from_phase será NULL (ok para primeiro move)
        )

        conn.commit()

        # Retorna lead atualizado
        lead = cursor.execute("SELECT * FROM leads WHERE contact_phone = ?", (phone,)).fetchone()
        conn.close()

        # Registra no log
        if lead:
            old_phase = lead["phase"] if "phase" in lead.keys() else "unknown"
            score = lead["qualification_score"] if "qualification_score" in lead.keys() else 0
            _log_lead_event(d, phone, "MOVED", f"{old_phase} → {new_phase} (score: {score})")

        return web.json_response(dict(lead) if lead else {"error": "não encontrado"})
    except Exception as e:
        print(f"Erro ao mover lead: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def handle_lead_delete(req: web.Request) -> web.Response:
    """Exclui lead do leads.db local (não mexe em conversas, agendamentos ou crons)"""
    d = _safe_profile_path(req.match_info["profile_id"])
    if not d:
        raise web.HTTPNotFound()

    phone = req.match_info["phone"]

    db_path = _leads_db(d)
    if not db_path.exists():
        return web.json_response({"error": "lead não encontrado"}, status=404)

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("DELETE FROM lead_phase_history WHERE contact_phone = ?", (phone,))
        history_deleted = cursor.rowcount

        cursor.execute("DELETE FROM leads WHERE contact_phone = ?", (phone,))
        lead_deleted = cursor.rowcount

        conn.commit()
        conn.close()

        if lead_deleted == 0 and history_deleted == 0:
            return web.json_response({"error": "lead não encontrado"}, status=404)

        _log_lead_event(d, phone, "DELETED", "excluído via dashboard")

        return web.json_response({"ok": True, "contact_phone": phone})
    except Exception as e:
        print(f"Erro ao excluir lead: {e}")
        return web.json_response({"error": str(e)}, status=500)


# ─── /api/profiles/{id}/appointments (agenda) ────────────────────────────────
# CRUD fino sobre appointments.py (crux-api/server) — mesmo módulo usado
# pela skill do agente (leads_cli.py-style), garantindo que dashboard e agente
# nunca divirjam de schema.

import appointments as _appt  # noqa: E402 — de ./lib, copiado verbatim do crux-api/server
import produto as _produto  # noqa: E402 — idem


def _log_appointment_event(d: Path, phone: str, event: str, details: str = "") -> None:
    try:
        log_file = d / "logs" / "appointments.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).isoformat()
        msg = f"{ts} | {event} | {phone}"
        if details:
            msg += f" | {details}"
        msg += "\n"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(msg)
    except Exception as e:
        print(f"Erro ao escrever log de appointments: {e}")


async def handle_appointments(req: web.Request) -> web.Response:
    """Lista compromissos do perfil, opcionalmente filtrando por janela de tempo
    (start/end, unix ts) ou por contato (contact_phone)."""
    d = _safe_profile_path(req.match_info["profile_id"])
    if not d:
        raise web.HTTPNotFound()

    contact_phone = req.query.get("contact_phone")
    try:
        start = int(req.query["start"]) if "start" in req.query else None
        end = int(req.query["end"]) if "end" in req.query else None
    except ValueError:
        return web.json_response({"error": "start/end inválidos"}, status=400)

    try:
        if contact_phone:
            appts = _appt.list_appointments_by_contact(d, contact_phone)
        else:
            appts = _appt.list_appointments(d, start, end)
        return web.json_response(appts)
    except Exception as e:
        print(f"Erro ao ler appointments.db: {e}")
        return web.json_response([])


async def handle_appointment_create(req: web.Request) -> web.Response:
    d = _safe_profile_path(req.match_info["profile_id"])
    if not d:
        raise web.HTTPNotFound()
    try:
        body = await req.json()
    except Exception:
        return web.json_response({"error": "JSON inválido"}, status=400)

    phone = (body.get("contact_phone") or "").strip()
    scheduled_at = body.get("scheduled_at")
    if not phone or not isinstance(scheduled_at, int):
        return web.json_response({"error": "contact_phone e scheduled_at (unix ts) obrigatórios"}, status=400)

    try:
        appt = _appt.create_appointment(d, phone, scheduled_at, body.get("title", ""), body.get("notes", ""))
        _log_appointment_event(d, phone, "CREATED", appt.get("title") or "")
        return web.json_response(appt)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def handle_appointment_update(req: web.Request) -> web.Response:
    d = _safe_profile_path(req.match_info["profile_id"])
    if not d:
        raise web.HTTPNotFound()
    try:
        appt_id = int(req.match_info["appt_id"])
    except ValueError:
        return web.json_response({"error": "id inválido"}, status=400)
    try:
        body = await req.json()
    except Exception:
        return web.json_response({"error": "JSON inválido"}, status=400)

    try:
        appt = _appt.update_appointment(
            d, appt_id,
            scheduled_at=body.get("scheduled_at"),
            title=body.get("title"),
            notes=body.get("notes"),
            status=body.get("status"),
        )
        _log_appointment_event(d, appt.get("contact_phone", ""), "UPDATED", f"status={appt.get('status')}")
        return web.json_response(appt)
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=404)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def handle_appointment_delete(req: web.Request) -> web.Response:
    d = _safe_profile_path(req.match_info["profile_id"])
    if not d:
        raise web.HTTPNotFound()
    try:
        appt_id = int(req.match_info["appt_id"])
    except ValueError:
        return web.json_response({"error": "id inválido"}, status=400)

    appt = _appt.get_appointment(d, appt_id)
    _appt.delete_appointment(d, appt_id)
    if appt:
        _log_appointment_event(d, appt.get("contact_phone", ""), "DELETED", appt.get("title") or "")
    return web.json_response({"status": "deleted"})


# ─── /api/profiles/{id}/contact/memory ────────────────────────────────────────

async def handle_contact_memory(req: web.Request) -> web.Response:
    """Return the persisted per-contact memory (memories/contacts/<safe_id>/*.md).

    safe_id mirrors the core (memory_tool.py): the contact user_id with every
    non [a-zA-Z0-9_-] char replaced by '_'. Lock files are skipped.
    """
    d = _safe_profile_path(req.match_info["profile_id"])
    if not d:
        raise web.HTTPNotFound()
    contact_id = (req.query.get("contact_id") or "").strip()
    if not contact_id:
        return web.json_response({"error": "contact_id ausente"}, status=400)
    safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", contact_id)
    mem_dir = d / "memories" / "contacts" / safe
    files = []
    if mem_dir.is_dir():
        for f in sorted(mem_dir.iterdir()):
            if f.is_file() and f.suffix == ".md":
                try:
                    content = f.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    content = ""
                files.append({"name": f.name, "content": content})
    return web.json_response({"contact_id": contact_id, "safe_id": safe, "files": files})


# NOTA: crux tinha aqui um painel de admin (/db/tables, /db/table, /db/query)
# com SQL de leitura livre sobre state.db/leads.db/appointments.db. Decisão
# tomada na análise inicial: não portar — é uma porta de administração direta
# sobre dados de clientes de terceiros (agentes de outras contas na mesma
# infra), não uma feature de produto. Se precisar depurar dado em produção,
# usar acesso de infra (não pelo dashboard).

# ─── /api/profiles/{id}/group/members ─────────────────────────────────────────
# GAP: dependia de chamar o bridge (Node/Baileys) em http://127.0.0.1:{port} no
# mesmo container. Aqui o bridge roda dentro do container `vya-workforce-api` —
# não alcançável deste container. Não portado; ver ARCHITECTURE_NOTES.md.

# ─── /api/profiles/{id}/contact/avatar ────────────────────────────────────────
# GAP: mesmo motivo do group/members acima — dependia do bridge em
# 127.0.0.1:{port}/avatar/{id}. Não portado.

# ─── /api/profiles/{id}/contact/delete ────────────────────────────────────────

async def handle_contact_delete(req: web.Request) -> web.Response:
    """Delete ALL state.db rows for one contact (live, no gateway stop).

    Removes every session that belongs to the contact plus its messages (the
    FTS indexes are cleaned by the messages_fts_delete triggers), and drops the
    matching entries from sessions/sessions.json so the next message starts a
    fresh session. A timestamped backup is taken first. For a DM, the target is
    matched by `user_id`; for a group, by the group `chat_id` across all
    participant sessions.
    """
    d = _safe_profile_path(req.match_info["profile_id"])
    if not d:
        raise web.HTTPNotFound()
    try:
        body = await req.json()
    except Exception:
        return web.json_response({"error": "JSON inválido"}, status=400)
    contact_id = (body.get("contact_id") or "").strip()
    is_group = bool(body.get("is_group"))
    if not contact_id:
        return web.json_response({"error": "contact_id ausente"}, status=400)

    db_path = d / "state.db"
    sessions_json = d / "sessions" / "sessions.json"

    # 1. Collect target session_ids (and sessions.json keys) for this contact.
    target_sids: set = set()
    target_keys: set = set()
    sj: dict = {}
    if sessions_json.exists():
        try:
            sj = json.loads(sessions_json.read_text() or "{}")
        except Exception:
            sj = {}
        for key, entry in (sj.items() if isinstance(sj, dict) else []):
            if not isinstance(entry, dict):
                continue
            origin = entry.get("origin") or {}
            if is_group:
                match = origin.get("chat_id") == contact_id
            else:
                match = origin.get("user_id") == contact_id or origin.get("chat_id") == contact_id
            if match:
                sid = entry.get("session_id")
                if sid:
                    target_sids.add(sid)
                target_keys.add(key)
    # DM sessions may exist in state.db without a sessions.json entry.
    if db_path.exists() and not is_group:
        try:
            conn = _db_connect(db_path)
            for row in conn.execute("SELECT id FROM sessions WHERE user_id = ?", (contact_id,)):
                target_sids.add(row["id"])
            conn.close()
        except Exception:
            pass

    if not target_sids and not target_keys:
        return web.json_response({"ok": True, "removed_sessions": 0,
                                  "removed_messages": 0, "removed_json": 0,
                                  "note": "nada encontrado para este contato"})

    # 1b. crux parava o gateway aqui antes de mutar (evita que o cache em
    # memória da sessão sobrescreva o delete com dado velho — ver nota no
    # topo do arquivo). Não dá pra fazer isso daqui: o gateway roda em outro
    # container. Risco aceito e documentado: numa janela pequena logo após o
    # delete, uma mensagem em trânsito pode recriar uma sessão com os dados
    # antigos ainda em cache. Se isso incomodar na prática, negociar um
    # endpoint de restart de agente no vyadigital_api pra fechar o gap.

    # 2. Backup before mutating.
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = d / "backups" / f"contact-delete-{ts}"
    try:
        backup.mkdir(parents=True, exist_ok=True)
        import shutil
        for fn in ("state.db", "state.db-wal", "state.db-shm"):
            src = d / fn
            if src.exists():
                shutil.copy2(src, backup / fn)
        if sessions_json.exists():
            shutil.copy2(sessions_json, backup / "sessions.json")
        if (d / "channel_directory.json").exists():
            shutil.copy2(d / "channel_directory.json", backup / "channel_directory.json")
    except Exception as e:
        return web.json_response({"error": f"falha no backup, abortado: {e}"}, status=500)

    # 3. Delete from state.db (write connection; triggers clean the FTS index).
    removed_messages = removed_sessions = 0
    if db_path.exists() and target_sids:
        try:
            conn = sqlite3.connect(str(db_path), timeout=10)
            conn.execute("PRAGMA busy_timeout=8000")
            ph = ",".join("?" for _ in target_sids)
            sids = list(target_sids)
            with conn:
                cur = conn.execute(f"DELETE FROM messages WHERE session_id IN ({ph})", sids)
                removed_messages = cur.rowcount
                cur = conn.execute(f"DELETE FROM sessions WHERE id IN ({ph})", sids)
                removed_sessions = cur.rowcount
            conn.close()
        except Exception as e:
            return web.json_response(
                {"error": f"falha ao excluir do state.db (backup em {backup}): {e}"}, status=500)

    # 4. Rewrite sessions.json atomically, dropping the contact's entries.
    removed_json = 0
    if sj:
        new = {k: v for k, v in sj.items()
               if not (k in target_keys or (isinstance(v, dict) and v.get("session_id") in target_sids))}
        removed_json = len(sj) - len(new)
        try:
            tmp = sessions_json.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(new, ensure_ascii=False, indent=2) + "\n")
            tmp.replace(sessions_json)
        except Exception as e:
            return web.json_response(
                {"error": f"state.db limpo mas falhou ao reescrever sessions.json: {e}"}, status=500)

    # 5. Drop the contact from channel_directory.json so the Contacts row
    # disappears. The directory is rebuilt from sessions.json by the gateway,
    # so removing the (now session-less) entry is consistent and durable — it
    # only reappears if the contact messages again (a genuinely new contact).
    removed_dir = 0
    cd = d / "channel_directory.json"
    if cd.exists():
        try:
            data = json.loads(cd.read_text())
            plats = data.get("platforms") or {}
            for plat, items in list(plats.items()):
                if not isinstance(items, list):
                    continue
                kept = [c for c in items if not (isinstance(c, dict) and c.get("id") == contact_id)]
                removed_dir += len(items) - len(kept)
                plats[plat] = kept
            if removed_dir:
                tmp = cd.with_suffix(".json.tmp")
                tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
                tmp.replace(cd)
        except Exception:
            pass  # non-fatal: history is already cleared

    # 5b. Delete the contact's lead (leads.db) and its phase history — a
    # kanban card tracking a conversation that no longer exists is stale by
    # definition. Appointments (appointments.db) are intentionally NOT
    # touched here: a booked service is a business record (the client is
    # still coming in) that must survive even if the chat/lead is wiped.
    removed_lead = 0
    if not is_group:
        phone = _resolve_phone(contact_id, _load_lid_phone_map(d))
        leads_db_path = _leads_db(d)
        if phone and leads_db_path.exists():
            try:
                lconn = sqlite3.connect(str(leads_db_path))
                lcur = lconn.cursor()
                lcur.execute("DELETE FROM lead_phase_history WHERE contact_phone = ?", (phone,))
                lcur.execute("DELETE FROM leads WHERE contact_phone = ?", (phone,))
                removed_lead = lcur.rowcount
                lconn.commit()
                lconn.close()
                if removed_lead:
                    _log_lead_event(d, phone, "DELETED", "contato excluído")
            except Exception:
                pass  # non-fatal: contact history is already cleared

    # 5c. Drop cron jobs whose origin points at this contact — a reminder
    # tied to a chat that was just wiped would only misfire later. Same
    # origin.chat_id/user_id match used for the state.db session cleanup
    # above. Also prunes origin_map.json and the job's output dir so nothing
    # orphaned is left behind (mirrors hermes-agent's own remove_job()).
    removed_crons = 0
    jobs_file = d / "cron" / "jobs.json"
    if jobs_file.exists():
        try:
            jdata = json.loads(jobs_file.read_text() or "{}")
            jobs_list = jdata.get("jobs", [])
            keep, drop_ids = [], []
            for job in jobs_list:
                origin = job.get("origin") or {}
                match = origin.get("chat_id") == contact_id or (
                    not is_group and origin.get("user_id") == contact_id)
                if match:
                    drop_ids.append(job.get("id", ""))
                else:
                    keep.append(job)
            removed_crons = len(jobs_list) - len(keep)
            if removed_crons:
                jdata["jobs"] = keep
                tmp = jobs_file.with_suffix(".json.tmp")
                tmp.write_text(json.dumps(jdata, ensure_ascii=False, indent=2) + "\n")
                tmp.replace(jobs_file)

                origin_map_file = d / "cron" / "origin_map.json"
                if origin_map_file.exists():
                    try:
                        omap = json.loads(origin_map_file.read_text() or "{}")
                        for jid in drop_ids:
                            omap.pop(jid, None)
                        tmp2 = origin_map_file.with_suffix(".json.tmp")
                        tmp2.write_text(json.dumps(omap, ensure_ascii=False, indent=2) + "\n")
                        tmp2.replace(origin_map_file)
                    except Exception:
                        pass

                import shutil as _shutil
                for jid in drop_ids:
                    if not jid:
                        continue
                    out_dir = d / "cron" / "output" / jid
                    if out_dir.exists():
                        _shutil.rmtree(out_dir, ignore_errors=True)
        except Exception:
            pass  # non-fatal: contact history is already cleared

    # 5d. Delete the contact's persisted memory (memories/contacts/<safe_id>/,
    # e.g. user.md) -- a memory snapshot tied to a wiped conversation is stale
    # by definition, same reasoning as the lead in 5b. Backed up first, same
    # as state.db/sessions.json above.
    removed_memory = 0
    if not is_group:
        safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", contact_id)
        mem_dir = d / "memories" / "contacts" / safe
        if mem_dir.is_dir():
            try:
                import shutil as _shutil2
                mem_backup = backup / "memories" / safe
                mem_backup.parent.mkdir(parents=True, exist_ok=True)
                _shutil2.copytree(mem_dir, mem_backup)
                removed_memory = sum(1 for f in mem_dir.iterdir() if f.is_file())
                _shutil2.rmtree(mem_dir)
            except Exception:
                pass  # non-fatal: contact history is already cleared

    return web.json_response({
        "ok": True,
        "contact_id": contact_id,
        "is_group": is_group,
        "removed_sessions": removed_sessions,
        "removed_messages": removed_messages,
        "removed_json": removed_json,
        "removed_directory": removed_dir,
        "removed_lead": removed_lead,
        "removed_crons": removed_crons,
        "removed_memory": removed_memory,
        "backup": str(backup),
    })


# ─── /api/profiles/{id}/contact/pause ────────────────────────────────────────
# GAP: no crux, o gateway (patch próprio) checa um arquivo paused/<chat_id>
# antes de responder. Conferido: esse trecho não existe no patch da empresa
# (hermes-agent-patches.diff) — o gateway deles nunca olha pra esse arquivo.
# Escrever a flag aqui criaria um botão de "pausar" que parece funcionar mas
# não pausa nada. Por isso os handlers de escrita (pause/resume) não foram
# portados. Mantido só o helper de leitura abaixo, usado por handle_conversations
# pra popular o campo "paused" — hoje sempre vazio, sem efeito colateral, e
# pronto pra ativar no dia em que o patch do gateway ganhar esse trecho.

def _paused_chat_ids(profile_dir: Path) -> set:
    paused_dir = profile_dir / "paused"
    if not paused_dir.exists():
        return set()
    return {p.name for p in paused_dir.iterdir() if p.is_file()}


# ─── /api/profiles/{id}/suspend | /api/profiles/{id}/resume ──────────────────
# GAP: dependia de profile_state.py (crux-api), que por baixo usa supervisor_ctl
# — sem equivalente no vyadigital_api/vya-workforce-api hoje (não há endpoint
# de start/stop/suspend de agente, só connect/disconnect do canal WhatsApp).
# Não portado. Se virar bloqueio real, é pauta pra pedir um endpoint de
# lifecycle de agente no hermes-api da empresa.

# ─── /api/profiles/{id}/restart ───────────────────────────────────────────────
# Gap fechado: endpoint novo em hermes-api (POST /agents/{id}/restart, usa
# hermes_fs.stop_gateway+start_gateway, que já rodam no mesmo container do
# gateway) + proxy em vyadigital_api. Ver ARCHITECTURE_NOTES.md.

async def handle_restart(req: web.Request) -> web.Response:
    d = _safe_profile_path(req.match_info["profile_id"])
    if not d:
        raise web.HTTPNotFound()
    try:
        result = await vya_api_client.restart_agent(d.name)
    except vya_api_client.VyaApiError as e:
        return web.json_response({"error": e.detail}, status=e.status_code)
    return web.json_response({"ok": True, **result})

# ─── /api/profiles/{id}/qr ────────────────────────────────────────────────────
# Adaptado para usar o vyadigital_api em vez de ler qr-connect.txt do bridge
# local (que não existe nesse container) — ver vya_api_client.py.

async def handle_qr(req: web.Request) -> web.Response:
    d = _safe_profile_path(req.match_info["profile_id"])
    if not d:
        raise web.HTTPNotFound()
    try:
        content, content_type = await vya_api_client.whatsapp_qr(d.name)
    except vya_api_client.VyaApiError as e:
        if e.status_code == 404:
            raise web.HTTPNotFound()
        return web.json_response({"error": e.detail}, status=e.status_code)
    return web.Response(body=content, content_type=content_type)


async def handle_qr_events(req: web.Request) -> web.StreamResponse:
    """SSE stream: sem arquivo local pra vigiar (QR vem do vyadigital_api),
    então poll no endpoint de QR e compara o hash dos bytes pra detectar
    troca — mais lento que o file-watch do crux (poll a cada 2s em vez de
    reagir instantaneamente à escrita do bridge), mas não depende de
    filesystem compartilhado com o processo que gera o QR."""
    import hashlib
    d = _safe_profile_path(req.match_info["profile_id"])
    if not d:
        raise web.HTTPNotFound()

    resp = web.StreamResponse()
    resp.headers["Content-Type"] = "text/event-stream"
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    await resp.prepare(req)

    last_hash = None
    await resp.write(b"data: {\"event\":\"connected\"}\n\n")

    try:
        for _ in range(150):  # até 5 min (150 x 2s)
            await asyncio.sleep(2)
            try:
                content, _ct = await vya_api_client.whatsapp_qr(d.name)
            except vya_api_client.VyaApiError:
                continue
            h = hashlib.sha256(content).hexdigest()
            if last_hash is not None and h != last_hash:
                await resp.write(b"data: {\"event\":\"new_qr\"}\n\n")
            last_hash = h
    except (asyncio.CancelledError, ConnectionResetError):
        pass

    return resp


# ─── /api/profiles/{id}/qr/generate POST ─────────────────────────────────────

async def handle_qr_generate(req: web.Request) -> web.Response:
    """Força um novo pareamento: disconnect(forget=True) + connect() via
    vyadigital_api (channels/whatsapp), em vez de derrubar bridge/gateway por
    PID como o crux faz — aqui esse controle vive no outro container."""
    d = _safe_profile_path(req.match_info["profile_id"])
    if not d:
        raise web.HTTPNotFound()
    try:
        await vya_api_client.whatsapp_disconnect(d.name, forget=True)
        status = await vya_api_client.whatsapp_connect(d.name)
    except vya_api_client.VyaApiError as e:
        return web.json_response({"error": e.detail}, status=e.status_code)
    return web.json_response({"ok": True, "status": status})


# ─── Frontend ─────────────────────────────────────────────────────────────────

async def handle_index(_req: web.Request) -> web.FileResponse:
    # no-store: o SPA é um arquivo único atualizado com frequência por
    # hotfix (docker cp); sem isso o navegador pode servir versões velhas
    # por freshness heurística (não enviávamos Cache-Control nenhum), o que
    # torna qualquer debugging de frontend não-determinístico.
    resp = web.FileResponse(Path(__file__).parent / "index.html")
    resp.headers["Cache-Control"] = "no-store"
    return resp


# ─── App ──────────────────────────────────────────────────────────────────────

# ─── Authz (Authelia forward-auth) ────────────────────────────────────────────
#
# Behind NPM + Authelia, every request carries identity headers set by the proxy
# (Remote-User / Remote-Groups / ...). Group `admin` => full access; group
# `cliente-<profile>` => scoped to that profile. Locally (no proxy) the default
# `open` mode treats the caller as admin so dev/admin use is unchanged.

# "dblogs" (painel de SQL) removida do original — ver nota na seção /db.
# "acoes" fica: ainda tem o card de QR Code (portado), só perdeu os cards de
# restart/suspend/resume (ver renderAcoes() no index.html e notas de gap).
ALL_TABS = ["overview", "conversas", "agenda", "leads", "contatos", "soul", "produto", "acoes"]
CLIENT_TABS = ["overview", "conversas", "agenda", "leads", "produto", "contatos"]

# Endpoints a client (group cliente-<profile>) may call — always scoped to its
# own profile by the middleware. Everything else is admin-only.
_CLIENT_ALLOWED = [
    ("GET",    r"^/api/profiles/[^/]+/overview$"),
    ("GET",    r"^/api/profiles/[^/]+/conversations$"),
    ("GET",    r"^/api/profiles/[^/]+/conversations/[^/]+/messages$"),
    ("GET",    r"^/api/profiles/[^/]+/produto$"),
    ("POST",   r"^/api/profiles/[^/]+/produto$"),
    ("GET",    r"^/api/profiles/[^/]+/produto-config$"),
    ("POST",   r"^/api/profiles/[^/]+/produto-config$"),
    ("GET",    r"^/api/profiles/[^/]+/contacts$"),
    ("GET",    r"^/api/profiles/[^/]+/contact/memory$"),
    ("POST",   r"^/api/profiles/[^/]+/contact/delete$"),
    ("GET",    r"^/api/profiles/[^/]+/cron$"),
    ("DELETE", r"^/api/profiles/[^/]+/cron/[^/]+$"),
    ("GET",    r"^/api/profiles/[^/]+/appointments$"),
    ("POST",   r"^/api/profiles/[^/]+/appointments$"),
    ("PATCH",  r"^/api/profiles/[^/]+/appointments/[^/]+$"),
    ("DELETE", r"^/api/profiles/[^/]+/appointments/[^/]+$"),
    ("GET",    r"^/api/profiles/[^/]+/leads$"),
    ("POST",   r"^/api/profiles/[^/]+/leads/[^/]+/move$"),
    ("DELETE", r"^/api/profiles/[^/]+/leads/[^/]+$"),
]
_PROFILE_PATH_RE = re.compile(r"^/api/profiles/([^/]+)")


def _resolve_identity(request: web.Request):
    """Role + allowed profiles from proxy headers.

    role ∈ {admin, client, none}; profiles is None (=all) for admin or a set()
    for clients. Returns None when the request must be rejected (bad proxy
    secret). `open` mode (default, no proxy) = admin, unchanged local behaviour.
    """
    mode = (os.environ.get("VYA_AGENT_AUTH_MODE") or "open").lower()
    if mode != "proxy":
        return {"user": "local", "role": "admin", "profiles": None, "groups": ["admin"]}
    secret = os.environ.get("VYA_AGENT_PROXY_SECRET")
    if secret and request.headers.get("X-Vya-Agent-Proxy-Secret") != secret:
        return None
    groups = [g.strip() for g in (request.headers.get("Remote-Groups") or "").split(",") if g.strip()]
    user = request.headers.get("Remote-User") or ""
    if "admin" in groups:
        return {"user": user, "role": "admin", "profiles": None, "groups": groups}
    client_profiles = {g[len("cliente-"):] for g in groups if g.startswith("cliente-")}
    if client_profiles:
        return {"user": user, "role": "client", "profiles": client_profiles, "groups": groups}
    return {"user": user, "role": "none", "profiles": set(), "groups": groups}


# ── Rate limiting ─────────────────────────────────────────────────────────────
# In-memory sliding window per client key (X-Forwarded-For behind NPM, else
# the direct peer IP). No new dependency -- single dashboard process. Not a
# substitute for Authelia's own protections, just a floor against floods/
# scripted abuse hitting the API routes directly.
_RATE_LIMIT_WINDOW_SECONDS = 60
_RATE_LIMIT_MAX_REQUESTS = 120
_rate_limit_hits: dict[str, deque] = defaultdict(deque)


def _client_key(request: web.Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote or "unknown"


@web.middleware
async def rate_limit_middleware(request: web.Request, handler):
    key = _client_key(request)
    now = time.time()
    hits = _rate_limit_hits[key]
    while hits and now - hits[0] > _RATE_LIMIT_WINDOW_SECONDS:
        hits.popleft()

    if len(hits) >= _RATE_LIMIT_MAX_REQUESTS:
        retry_after = int(_RATE_LIMIT_WINDOW_SECONDS - (now - hits[0])) + 1
        return web.json_response(
            {"error": "Muitas requisições. Tente novamente em instantes."},
            status=429,
            headers={"Retry-After": str(retry_after)},
        )

    hits.append(now)
    return await handler(request)


@web.middleware
async def authz_middleware(request: web.Request, handler):
    ident = _resolve_identity(request)
    if ident is None:
        return web.json_response({"error": "proxy não autorizado"}, status=403)
    request["identity"] = ident
    path = request.path
    if path in ("/", "/api/me"):
        return await handler(request)
    role = ident["role"]
    if role == "admin":
        return await handler(request)
    if role != "client":
        return web.json_response({"error": "não autenticado"}, status=401)
    # Client: the profile list is allowed (handler filters to allowed profiles).
    if path == "/api/profiles":
        return await handler(request)
    m = _PROFILE_PATH_RE.match(path)
    if not m:
        return web.json_response({"error": "acesso negado"}, status=403)
    if ident["profiles"] is not None and m.group(1) not in ident["profiles"]:
        return web.json_response({"error": "perfil não autorizado"}, status=403)
    for meth, pat in _CLIENT_ALLOWED:
        if request.method == meth and re.match(pat, path):
            return await handler(request)
    return web.json_response({"error": "ação não permitida para este papel"}, status=403)


async def handle_me(request: web.Request) -> web.Response:
    ident = request.get("identity") or {"role": "admin", "profiles": None, "user": "local"}
    role = ident.get("role", "admin")
    if role == "admin":
        profiles = ([d.name for d in sorted(HERMES_ROOT.iterdir()) if d.is_dir()]
                    if HERMES_ROOT.exists() else [])
        tabs = ALL_TABS
    elif role == "client":
        profiles = sorted(ident.get("profiles") or [])
        tabs = CLIENT_TABS
    else:
        profiles, tabs = [], []
    logout_url = os.environ.get("AUTHELIA_LOGOUT_URL", "")
    return web.json_response({"user": ident.get("user"), "role": role,
                              "profiles": profiles, "tabs": tabs,
                              "logout_url": logout_url})


async def _on_startup(app: web.Application) -> None:
    """Sync cron origins + repair NULL user_ids on all profiles at startup, then keep watching."""
    try:
        if HERMES_ROOT.exists():
            for d in HERMES_ROOT.iterdir():
                if d.is_dir():
                    _sync_cron_origins(d)
                    _repair_cron_user_ids(d)
    except Exception:
        pass
    asyncio.create_task(_cron_background_maintenance())


def make_app() -> web.Application:
    app = web.Application(middlewares=[rate_limit_middleware, authz_middleware])
    app.on_startup.append(_on_startup)
    r = app.router
    r.add_get("/", handle_index)
    r.add_get("/api/me", handle_me)

    # Profiles
    r.add_get("/api/profiles", handle_profiles)

    # Per-profile
    r.add_get("/api/profiles/{profile_id}/overview", handle_overview)
    r.add_get("/api/profiles/{profile_id}/conversations", handle_conversations)
    r.add_get("/api/profiles/{profile_id}/conversations/{session_id}/messages", handle_messages)
    r.add_get("/api/base/{fname}", handle_get_base)
    r.add_get("/api/profiles/{profile_id}/soul", handle_get_soul)
    r.add_post("/api/profiles/{profile_id}/soul", handle_set_soul)
    r.add_get("/api/profiles/{profile_id}/produto", handle_get_produto)
    r.add_post("/api/profiles/{profile_id}/produto", handle_set_produto)
    r.add_get("/api/profiles/{profile_id}/produto-config", handle_get_produto_config)
    r.add_post("/api/profiles/{profile_id}/produto-config", handle_set_produto_config)
    r.add_get("/api/profiles/{profile_id}/cron", handle_cron)
    r.add_get("/api/profiles/{profile_id}/logs", handle_logs)
    r.add_get("/api/profiles/{profile_id}/contacts", handle_contacts)
    r.add_get("/api/profiles/{profile_id}/leads", handle_leads)
    r.add_post("/api/profiles/{profile_id}/leads/{phone}/move", handle_lead_move)
    r.add_delete("/api/profiles/{profile_id}/leads/{phone}", handle_lead_delete)
    r.add_get("/api/profiles/{profile_id}/appointments", handle_appointments)
    r.add_post("/api/profiles/{profile_id}/appointments", handle_appointment_create)
    r.add_route("PATCH", "/api/profiles/{profile_id}/appointments/{appt_id}", handle_appointment_update)
    r.add_delete("/api/profiles/{profile_id}/appointments/{appt_id}", handle_appointment_delete)
    # Não portadas (gap de plataforma, ver comentários nas seções correspondentes
    # mais acima): group/members, contact/avatar, contact/pause, contact/resume,
    # suspend, resume, db/tables, db/table, db/query.
    r.add_get("/api/profiles/{profile_id}/contact/memory", handle_contact_memory)
    r.add_post("/api/profiles/{profile_id}/contact/delete", handle_contact_delete)
    r.add_post("/api/profiles/{profile_id}/restart", handle_restart)
    r.add_get("/api/profiles/{profile_id}/qr", handle_qr)
    r.add_post("/api/profiles/{profile_id}/qr/generate", handle_qr_generate)
    r.add_get("/api/profiles/{profile_id}/qr/events", handle_qr_events)
    r.add_delete("/api/profiles/{profile_id}/cron/{job_id}", handle_delete_cron_job)

    return app


if __name__ == "__main__":
    host = os.environ.get("VYA_AGENT_HOST") or "0.0.0.0"
    mode = os.environ.get("VYA_AGENT_AUTH_MODE") or "open"
    print(f"app-vya-digital dashboard → http://{host}:{PORT}  (auth: {mode})")
    web.run_app(make_app(), host=host, port=PORT, print=None)
