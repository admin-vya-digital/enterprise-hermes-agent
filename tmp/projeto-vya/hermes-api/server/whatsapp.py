"""
whatsapp.py — conexão do canal WhatsApp (Baileys) por agente.
Fase 5: única etapa que exige um ato humano (scan do QR). Todo o resto
(subir/derrubar processos, ler estado) é código determinístico — o
control plane nunca conversa com o agente nem invoca a LLM aqui.
"""

import os
import subprocess
import time
from pathlib import Path

from hermes_fs import HERMES_DIR, gateway_state, load_env, pid_alive, read_pid, start_gateway, stop_gateway
from lifecycle import _write_env

BRIDGE_DIR = HERMES_DIR / "scripts" / "whatsapp-bridge"
BRIDGE_JS = BRIDGE_DIR / "bridge.js"


# ─── Caminhos ──────────────────────────────────────────────────────────────────

def _session_dir(d: Path) -> Path:
    """Sessão real do bridge — o gateway lê via symlink em platforms/whatsapp/session."""
    return d / "session"


def _creds_path(d: Path) -> Path:
    return _session_dir(d) / "creds.json"


def _bridge_pid_file(d: Path) -> Path:
    return d / "bridge.pid"


def _ensure_gateway_session_symlink(d: Path) -> None:
    """
    O gateway Python resolve a sessão WhatsApp em `<profile>/platforms/whatsapp/session`
    (padrão do hermes-agent). O bridge grava em `<profile>/session`. Sem este symlink,
    o gateway nunca encontra o `creds.json` gerado no pareamento e recusa subir o canal.
    Idempotente — não recria se já existir.
    """
    link_parent = d / "platforms" / "whatsapp"
    link_parent.mkdir(parents=True, exist_ok=True)
    link = link_parent / "session"
    if link.is_symlink() or link.exists():
        return
    link.symlink_to(_session_dir(d))


# ─── Estado ────────────────────────────────────────────────────────────────────

def get_status(d: Path) -> dict:
    paired = _creds_path(d).exists()

    bridge_pid = read_pid(_bridge_pid_file(d)) if _bridge_pid_file(d).exists() else None
    bridge_alive = bool(bridge_pid and pid_alive(bridge_pid))

    gateway_pid = read_pid(d / "gateway.pid") if (d / "gateway.pid").exists() else None
    gateway_alive = bool(gateway_pid and pid_alive(gateway_pid))

    gstate = gateway_state(d)
    wa_state = gstate.get("platforms", {}).get("whatsapp", {}).get("state", "unknown")

    jid = None
    if paired:
        try:
            import json
            creds = json.loads(_creds_path(d).read_text())
            jid = (creds.get("me") or {}).get("id")
        except Exception:
            pass

    if not paired:
        phase = "pairing" if bridge_alive else "disconnected"
    elif gateway_alive and wa_state == "connected":
        phase = "connected"
    elif gateway_alive:
        phase = "starting"
    else:
        phase = "paired_not_running"

    return {
        "phase": phase,
        "paired": paired,
        "jid": jid,
        "bridge_pid": bridge_pid,
        "gateway_pid": gateway_pid,
        "whatsapp_state": wa_state,
    }


# ─── Conexão ───────────────────────────────────────────────────────────────────

def connect(d: Path) -> dict:
    """
    Idempotente. Três casos:
    - Já pareado: garante WHATSAPP_ENABLED=true e sobe o gateway (se não estiver rodando).
    - Pareamento já em andamento (bridge --pair-only vivo): não faz nada, aponta pro /qr.
    - Nunca pareado: sobe o bridge em modo --pair-only para gerar o QR.
    """
    if not BRIDGE_JS.exists():
        raise RuntimeError(f"Bridge não encontrado em {BRIDGE_JS}.")

    status = get_status(d)

    if status["paired"]:
        env = load_env(d)
        if env.get("WHATSAPP_ENABLED", "").lower() != "true":
            env["WHATSAPP_ENABLED"] = "true"
            _write_env(d, env)
        if not status["gateway_pid"] or not pid_alive(status["gateway_pid"]):
            start_gateway(d)
            time.sleep(1)
            _set_home_channel(d)
        return get_status(d)

    if status["bridge_pid"] and pid_alive(status["bridge_pid"]):
        return status

    _ensure_gateway_session_symlink(d)
    session_dir = _session_dir(d)
    session_dir.mkdir(parents=True, exist_ok=True)

    if not (BRIDGE_DIR / "node_modules").exists():
        raise RuntimeError(
            f"Dependências do bridge não instaladas. Rode 'npm install' em {BRIDGE_DIR} "
            "uma vez no servidor antes de conectar o primeiro agente."
        )

    env = load_env(d)
    mode = env.get("WHATSAPP_MODE", "bot")

    log_path = d / "logs" / "bridge.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fh = open(log_path, "a", encoding="utf-8")

    proc = subprocess.Popen(
        ["node", str(BRIDGE_JS), "--pair-only", "--session", str(session_dir), "--mode", mode],
        cwd=str(BRIDGE_DIR),
        stdout=log_fh,
        stderr=log_fh,
        start_new_session=True,
    )
    _bridge_pid_file(d).write_text(str(proc.pid))

    return get_status(d)


def _set_home_channel(d: Path) -> None:
    """Configura o WhatsApp como home channel (destino de cron jobs e mensagens cross-platform)."""
    try:
        env = load_env(d)
        owner_number = env.get("WHATSAPP_OWNER_NUMBER", "").strip()
        if not owner_number:
            return
        channel_id = f"whatsapp://{owner_number}"
        subprocess.run(
            ["hermes", "channel", "set", "--id", channel_id],
            cwd=str(d),
            timeout=10,
            capture_output=True,
        )
    except Exception:
        pass


def get_qr_png(d: Path) -> Path | None:
    """Converte o payload cru do Baileys (texto) em PNG e retorna o caminho, se existir."""
    qr_dir = d / "qr"
    txt = qr_dir / "qr-connect.txt"
    png = qr_dir / "qr-connect.png"
    if not txt.exists():
        return None

    txt_mtime = txt.stat().st_mtime
    png_mtime = png.stat().st_mtime if png.exists() else 0
    if txt_mtime > png_mtime:
        import qrcode

        payload = txt.read_text().strip()
        if not payload:
            return None
        q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
        q.add_data(payload)
        q.make(fit=True)
        img = q.make_image(fill_color="black", back_color="white")
        img.save(str(png))

    return png if png.exists() else None


def disconnect(d: Path, forget: bool = False) -> dict:
    """
    Para o canal. `forget=True` também apaga a sessão (creds) — necessário
    um novo scan de QR na próxima conexão.
    """
    stop_gateway(d)

    bridge_pid = read_pid(_bridge_pid_file(d)) if _bridge_pid_file(d).exists() else None
    if bridge_pid and pid_alive(bridge_pid):
        try:
            os.kill(bridge_pid, 15)
        except OSError:
            pass
        for _ in range(8):
            time.sleep(0.25)
            if not pid_alive(bridge_pid):
                break
        if pid_alive(bridge_pid):
            try:
                os.kill(bridge_pid, 9)
            except OSError:
                pass
    _bridge_pid_file(d).unlink(missing_ok=True)

    if forget:
        import shutil

        shutil.rmtree(_session_dir(d), ignore_errors=True)
        shutil.rmtree(d / "platforms" / "whatsapp", ignore_errors=True)
        for f in (d / "qr").glob("qr-connect.*"):
            f.unlink(missing_ok=True)
        env = load_env(d)
        env["WHATSAPP_ENABLED"] = "false"
        _write_env(d, env)

    return get_status(d)
