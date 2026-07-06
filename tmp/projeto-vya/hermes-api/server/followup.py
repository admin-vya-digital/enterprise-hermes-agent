"""
followup.py — criação e gestão de jobs de follow-up no cron do Hermes.
Escreve diretamente em <profile>/cron/jobs.json — o mesmo caminho que o
gateway do próprio perfil lê (get_hermes_home() / "cron" / "jobs.json",
resolvido via HERMES_HOME). Cron é por-perfil, não global.

Formato do arquivo: `{"jobs": [...], "updated_at": "..."}` — o mesmo shape
canônico que `cron/jobs.py` (Hermes) usa via `save_jobs()`. Uma lista solta
`[...]` é tolerada na leitura (o próprio Hermes também aceita e "conserta"
esse formato antigo), mas toda escrita daqui em diante sai sempre no
formato com wrapper, para não divergir do que o scheduler real espera.
"""

import fcntl
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path


def _cron_dir(d: Path) -> Path:
    return d / "cron"


def _jobs_file(d: Path) -> Path:
    return _cron_dir(d) / "jobs.json"


def _jobs_list(data) -> list[dict]:
    """Extrai a lista de jobs de qualquer um dos dois formatos aceitos."""
    if isinstance(data, dict):
        return data.get("jobs", [])
    if isinstance(data, list):
        return data
    return []


def _load_jobs(d: Path) -> list[dict]:
    """Leitura simples (sem lock) — segura porque escritas são sempre atômicas."""
    jobs_file = _jobs_file(d)
    if not jobs_file.exists():
        return []
    try:
        text = jobs_file.read_text().strip()
        return _jobs_list(json.loads(text)) if text else []
    except Exception:
        return []


def _with_locked_jobs(d: Path, fn):
    """Abre/tranca jobs.json (flock exclusivo), deixa `fn(jobs_list)` mutar a
    lista de jobs em memória (append/remove), e grava sempre no formato
    canônico `{"jobs": [...], "updated_at": ...}` — o mesmo que `cron/jobs.py`
    (Hermes) usa, para não divergir entre os dois escritores do arquivo."""
    jobs_file = _jobs_file(d)
    jobs_file.parent.mkdir(parents=True, exist_ok=True)
    jobs_file.touch(exist_ok=True)
    lockfile = jobs_file.with_suffix(jobs_file.suffix + ".lock")
    with open(lockfile, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            try:
                text = jobs_file.read_text(encoding="utf-8").strip()
                raw = json.loads(text) if text else {}
            except Exception:
                raw = {}
            jobs = _jobs_list(raw)

            result = fn(jobs)

            payload = {
                "jobs": jobs,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            tmp = jobs_file.with_suffix(jobs_file.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(jobs_file)
            return result
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def _parse_schedule(schedule: str) -> dict:
    """Converte expressão de schedule no formato interno do Hermes."""
    import re
    # Expressão cron (5 campos)
    if len(schedule.split()) == 5:
        return {"kind": "cron", "expr": schedule, "display": schedule}
    # Duração: 30m, 2h, 1d
    m = re.fullmatch(r"(\d+)(m|h|d)", schedule)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        minutes = n if unit == "m" else n * 60 if unit == "h" else n * 1440
        return {"kind": "interval", "minutes": minutes, "display": f"a cada {schedule}"}
    # every 30m
    m2 = re.fullmatch(r"every (\d+)(m|h|d)", schedule)
    if m2:
        n, unit = int(m2.group(1)), m2.group(2)
        minutes = n if unit == "m" else n * 60 if unit == "h" else n * 1440
        return {"kind": "interval", "minutes": minutes, "display": f"a cada {n}{unit}"}
    # ISO datetime one-shot
    return {"kind": "once", "run_at": schedule, "display": f"em {schedule}"}


def create_followup(
    d: Path,
    agent_id: str,
    name: str,
    schedule: str,
    prompt: str,
    repeat: int | None = None,
) -> dict:
    """
    Cria um job de follow-up no cron do perfil (profiles/<agent_id>/cron/jobs.json).
    Retorna o job criado.
    """
    job_id = secrets.token_hex(6)
    now = datetime.now(timezone.utc).isoformat()

    job = {
        "id": job_id,
        "name": name,
        "schedule": _parse_schedule(schedule),
        "prompt": prompt,
        "deliver": "local",
        "skills": [],
        "enabled": True,
        "state": "scheduled",
        "last_run_at": None,
        "next_run_at": None,
        "created_at": now,
        "profile": agent_id,
        "tags": ["followup", f"agent:{agent_id}"],
    }
    if repeat is not None:
        job["repeat"] = repeat
    job["last_output"] = None

    def op(jobs: list[dict]) -> None:
        jobs.append(job)
    _with_locked_jobs(d, op)
    return job


def _last_output(d: Path, job_id: str) -> dict | None:
    """
    Retorna o conteúdo do último arquivo de output do job, se existir.
    O Hermes salva em <profile>/cron/output/{job_id}/{YYYYMMDD_HHMMSS}.md
    """
    output_dir = _cron_dir(d) / "output" / job_id
    if not output_dir.is_dir():
        return None
    files = sorted(output_dir.glob("*.md"), reverse=True)
    if not files:
        return None
    latest = files[0]
    try:
        return {
            "filename": latest.name,
            "ran_at": latest.stem,  # nome do arquivo é o timestamp
            "content": latest.read_text(encoding="utf-8"),
        }
    except Exception:
        return None


def list_followups(d: Path, agent_id: str) -> list[dict]:
    """Lista jobs de follow-up do perfil, com o último output de execução embutido."""
    jobs = [
        j for j in _load_jobs(d)
        if j.get("profile") == agent_id or f"agent:{agent_id}" in j.get("tags", [])
    ]
    for job in jobs:
        job["last_output"] = _last_output(d, job["id"])
    return jobs


def delete_followup(d: Path, job_id: str) -> bool:
    """Remove um job pelo ID no cron do perfil. Retorna True se encontrou e removeu."""
    found = False

    def op(jobs: list[dict]) -> None:
        nonlocal found
        new_jobs = [j for j in jobs if j.get("id") != job_id]
        found = len(new_jobs) != len(jobs)
        jobs[:] = new_jobs

    _with_locked_jobs(d, op)
    return found
