"""
hermes_fs.py — helpers de leitura do filesystem do Hermes.
Portado de ~/Code/hermes-dash/server.py para manter o repo auto-contido.
"""

import fcntl
import json
import os
import re
import signal
import sqlite3
import subprocess
import time
from pathlib import Path

# Estrutura padrão do projeto: <raiz>/hermes-agent, <raiz>/hermes-api,
# <raiz>/profiles e <raiz>/skills. As env vars VYA_PROFILES_DIR,
# VYA_HERMES_DIR e VYA_SKILLS_DIR permitem sobrepor cada caminho
# individualmente (ex.: layout antigo em ~/.hermes).
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
HERMES_ROOT = Path(os.environ.get("VYA_PROFILES_DIR", PROJECT_ROOT / "profiles")).expanduser()
HERMES_DIR = Path(os.environ.get("VYA_HERMES_DIR", PROJECT_ROOT / "hermes-agent")).expanduser()
SKILLS_DIR = Path(os.environ.get("VYA_SKILLS_DIR", PROJECT_ROOT / "skills")).expanduser()
SAFE_ID = re.compile(r"^[\w\-]+$")


# ─── Read-modify-write de JSON com lock exclusivo ─────────────────────────────
# Protege contra "lost update": duas requisições fazendo read→modify→write no
# mesmo arquivo (contacts.json, cron/jobs.json, estado de silêncio do plugin)
# ao mesmo tempo — sem lock cobrindo o ciclo inteiro, a segunda escrita
# sobrescreve a primeira inteira (o lock só na escrita NÃO resolve isso).
#
# Uso:
#   with locked_json(path, default=[]) as data:
#       data.append(novo_item)
#   # ao sair do `with`, o novo valor de `data` é gravado atomicamente
#   # e o lock só é liberado depois — ninguém mais entra no meio.

import contextlib


@contextlib.contextmanager
def locked_json(path: Path, default):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    lockfile = path.with_suffix(path.suffix + ".lock")
    with open(lockfile, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            text = path.read_text(encoding="utf-8").strip()
            data = json.loads(text) if text else json.loads(json.dumps(default))
        except Exception:
            data = json.loads(json.dumps(default))
        yield data
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
        fcntl.flock(lf, fcntl.LOCK_UN)


# ─── Leitura de PID / processo ────────────────────────────────────────────────

def read_pid(pid_file: Path) -> int | None:
    try:
        text = pid_file.read_text().strip()
        try:
            return json.loads(text)["pid"]
        except (json.JSONDecodeError, KeyError, TypeError):
            return int(text)
    except Exception:
        return None


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


# ─── Estado do perfil ─────────────────────────────────────────────────────────

def gateway_state(d: Path) -> dict:
    f = d / "gateway_state.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text())
    except Exception:
        return {}


def profile_status(d: Path) -> dict:
    gstate = gateway_state(d)
    pid = read_pid(d / "gateway.pid") if (d / "gateway.pid").exists() else None
    online = pid is not None and pid_alive(pid)
    wa = gstate.get("platforms", {}).get("whatsapp", {})
    return {
        "online": online,
        "pid": pid,
        "gateway_state": gstate.get("gateway_state", "stopped"),
        "whatsapp_state": wa.get("state", "unknown"),
        "updated_at": gstate.get("updated_at"),
    }


def bridge_port(d: Path) -> int:
    env = d / ".env"
    if env.exists():
        try:
            for line in env.read_text().splitlines():
                line = line.strip()
                if line.startswith("BRIDGE_PORT="):
                    return int(line.split("=", 1)[1].strip())
        except Exception:
            pass
    return 3000


def gateway_port(d: Path) -> int:
    env = d / ".env"
    if env.exists():
        try:
            for line in env.read_text().splitlines():
                line = line.strip()
                if line.startswith("GATEWAY_PORT="):
                    return int(line.split("=", 1)[1].strip())
        except Exception:
            pass
    return 8800


def load_env(d: Path) -> dict[str, str]:
    """Parse o .env do perfil em um dict."""
    env: dict[str, str] = {}
    envfile = d / ".env"
    if not envfile.exists():
        return env
    try:
        for line in envfile.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    except Exception:
        pass
    return env


# ─── Validação / caminhos ─────────────────────────────────────────────────────

def safe_profile_path(profile_id: str) -> Path | None:
    if not SAFE_ID.match(profile_id):
        return None
    d = HERMES_ROOT / profile_id
    if not d.is_dir():
        return None
    return d


def list_profiles() -> list[dict]:
    profiles = []
    if HERMES_ROOT.exists():
        for d in sorted(HERMES_ROOT.iterdir()):
            if d.is_dir() and SAFE_ID.match(d.name):
                profiles.append({"id": d.name, **profile_status(d)})
    return profiles


# ─── Leitura de SOUL / produto / config ───────────────────────────────────────

def read_soul(d: Path) -> str:
    f = d / "SOUL.md"
    return f.read_text(encoding="utf-8") if f.exists() else ""


def read_produto(d: Path) -> str:
    f = d / "produto.md"
    return f.read_text(encoding="utf-8") if f.exists() else ""


def profile_info(d: Path) -> dict:
    """Retorna todos os campos configurados do perfil lidos dos arquivos."""
    env = load_env(d)
    soul = read_soul(d)
    status = profile_status(d)

    kdir = d / "knowledge"
    knowledge_files = (
        [f.name for f in sorted(kdir.iterdir()) if f.suffix == ".md"]
        if kdir.is_dir() else []
    )

    enabled_toolsets_raw = env.get("ENABLED_TOOLSETS", "")
    enabled_toolsets = [t.strip() for t in enabled_toolsets_raw.split(",") if t.strip()]

    temp_raw = env.get("AGENT_TEMPERATURE")
    temperature = float(temp_raw) if temp_raw else None

    return {
        "id": d.name,
        # Identidade
        "name":        env.get("AGENT_NAME", d.name),
        "description": env.get("AGENT_DESCRIPTION", ""),
        "objective":   env.get("AGENT_OBJECTIVE", ""),
        "personality": env.get("AGENT_PERSONALITY", ""),
        "initial_prompt": env.get("AGENT_INITIAL_PROMPT", ""),
        # Runtime
        "model":       env.get("AGENT_MODEL", ""),
        "language":    env.get("AGENT_LANGUAGE", "pt-BR"),
        "temperature": temperature,
        # Skills / conhecimento
        "enabled_toolsets": enabled_toolsets,
        "knowledge_files":  knowledge_files,
        # Configuração de canal
        "bridge_port":      int(env.get("BRIDGE_PORT", 3000)),
        "gateway_port":     int(env.get("GATEWAY_PORT", 8800)),
        "whatsapp_enabled": env.get("WHATSAPP_ENABLED", "false").lower() == "true",
        # Estado dos arquivos
        "has_soul":    bool(soul),
        "has_produto": (d / "produto.md").exists(),
        # Estado do processo (gateway/bridge)
        **status,
    }


# ─── Base de conhecimento ──────────────────────────────────────────────────────

def list_knowledge(d: Path) -> list[dict]:
    kdir = d / "knowledge"
    if not kdir.is_dir():
        return []
    result = []
    for f in sorted(kdir.iterdir()):
        if f.is_file():
            result.append({
                "name": f.name,
                "size": f.stat().st_size,
                "modified_at": int(f.stat().st_mtime),
            })
    return result


# ─── Memória de contatos ──────────────────────────────────────────────────────

def list_contact_memories(d: Path, contact_uid: str) -> list[dict]:
    """Memória por contato do PERFIL — o próprio gateway (HERMES_HOME=d) lê daqui."""
    mem_dir = d / "memories" / "contacts" / contact_uid
    if not mem_dir.is_dir():
        return []
    result = []
    for f in sorted(mem_dir.iterdir()):
        if f.is_file():
            result.append({
                "name": f.name,
                "content": f.read_text(encoding="utf-8"),
                "modified_at": int(f.stat().st_mtime),
            })
    return result


# ─── Logs ─────────────────────────────────────────────────────────────────────

LOG_SOURCES = {
    "gateway": "gateway.log",
    "bridge": "bridge.log",
    "errors": "errors.log",
    "agent": "agent.log",
}


def tail_log(d: Path, source: str = "gateway", lines: int = 100) -> list[str]:
    fname = LOG_SOURCES.get(source, f"{source}.log")
    log_file = d / "logs" / fname
    if not log_file.exists():
        return []
    try:
        result = subprocess.run(
            ["tail", "-n", str(lines), str(log_file)],
            capture_output=True, text=True,
        )
        return result.stdout.splitlines()
    except Exception:
        return []


# ─── DB (state.db) ───────────────────────────────────────────────────────────

def db_connect(db_path: Path):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def list_runs(d: Path, limit: int = 50) -> list[dict]:
    db_path = d / "state.db"
    if not db_path.exists():
        return []
    try:
        conn = db_connect(db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, source, user_id, title, started_at, ended_at,
                   message_count, input_tokens, output_tokens, estimated_cost_usd
            FROM sessions
            WHERE (archived = 0 OR archived IS NULL)
            ORDER BY started_at DESC LIMIT ?
        """, (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception:
        return []


# ─── Stop / restart gateway ──────────────────────────────────────────────────

def _gateway_owns_profile(pid: int, d: Path) -> bool:
    try:
        for kv in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0"):
            if kv.startswith(b"HERMES_HOME="):
                return Path(kv.split(b"=", 1)[1].decode()) == d
    except Exception:
        return False
    return False


def stop_gateway(d: Path) -> bool:
    """Para o gateway do perfil por PID (TERM→KILL). Retorna True se havia um vivo."""
    pid_file = d / "gateway.pid"
    pid = read_pid(pid_file) if pid_file.exists() else None
    if not (pid and pid_alive(pid)):
        return False
    if not _gateway_owns_profile(pid, d):
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
    for _ in range(16):
        time.sleep(0.25)
        if not pid_alive(pid):
            break
    if pid_alive(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
        time.sleep(0.5)
    return True


def start_gateway(d: Path) -> int | None:
    """Inicia o gateway do perfil. Usado apenas na Fase 5 (canais de conversa)."""
    env = dict(os.environ)
    envfile = d / ".env"
    if envfile.exists():
        try:
            for line in envfile.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
        except Exception:
            pass
    venv = HERMES_DIR / "venv"
    env["HERMES_HOME"] = str(d)
    env["VIRTUAL_ENV"] = str(venv)
    env["PATH"] = f"{venv}/bin:" + env.get("PATH", "")
    try:
        (d / "gateway.lock").unlink()
    except Exception:
        pass
    argv = [str(venv / "bin" / "hermes"), "gateway", "run", "--replace"]
    bridge_dir = HERMES_DIR / "scripts" / "whatsapp-bridge"
    cwd = str(bridge_dir) if bridge_dir.exists() else str(d)
    proc = subprocess.Popen(
        argv, env=env, cwd=cwd, start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        (d / "gateway.pid").write_text(str(proc.pid))
    except Exception:
        pass
    return proc.pid


def restart_gateway(d: Path) -> int | None:
    """Reinicia só o gateway do perfil (stop_gateway + start_gateway), sem
    mexer no bridge/sessão WhatsApp. Mesmo par usado por update_profile()
    (lifecycle.py) para aplicar mudanças de persona/config com o gateway no
    ar — aqui exposto direto para o operador pedir um restart avulso."""
    stop_gateway(d)
    return start_gateway(d)
