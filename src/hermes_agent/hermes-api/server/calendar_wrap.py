"""
calendar_wrap.py — wrapper para o google_api.py/setup.py do Hermes, por perfil.
Cada perfil tem seu próprio google_token.json / google_client_secret.json em
profiles/<id>/ — os scripts são chamados com HERMES_HOME apontando pro perfil,
para que get_hermes_home() resolva os caminhos corretos (mesmo mecanismo usado
por config.yaml/plugins per-profile).
"""

import json
import os
import subprocess
from pathlib import Path

from hermes_fs import HERMES_DIR, SKILLS_DIR

GOOGLE_SCRIPTS_DIR = SKILLS_DIR / "productivity" / "google-workspace" / "scripts"
GOOGLE_API = GOOGLE_SCRIPTS_DIR / "google_api.py"
SETUP_SCRIPT = GOOGLE_SCRIPTS_DIR / "setup.py"
VENV_PYTHON = HERMES_DIR / "venv" / "bin" / "python"


def _run(d: Path, script: Path, args: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HERMES_HOME"] = str(d)
    return subprocess.run(
        [str(VENV_PYTHON), str(script)] + args,
        capture_output=True,
        text=True,
        cwd=str(GOOGLE_SCRIPTS_DIR),
        env=env,
    )


def calendar_status(d: Path) -> dict:
    """Verifica se o OAuth do Google está configurado para ESTE perfil."""
    token_file = d / "google_token.json"
    secret_file = d / "google_client_secret.json"
    if not secret_file.exists():
        return {
            "connected": False,
            "reason": "google_client_secret.json não encontrado neste perfil — "
                      "envie via POST /agents/{id}/calendar/connect",
        }
    if not token_file.exists():
        return {
            "connected": False,
            "reason": "google_token.json não encontrado — gere a URL de autorização em "
                      "GET /agents/{id}/calendar/connect/auth-url e finalize em "
                      "POST /agents/{id}/calendar/connect/auth-code",
        }
    try:
        token = json.loads(token_file.read_text())
        has_refresh = bool(token.get("refresh_token"))
        return {
            "connected": True,
            "has_refresh_token": has_refresh,
            "token_file": str(token_file),
        }
    except Exception as e:
        return {"connected": False, "reason": str(e)}


def calendar_store_client_secret(d: Path, client_secret: dict) -> None:
    """Salva o client_secret.json (credenciais do app OAuth) neste perfil."""
    if "installed" not in client_secret and "web" not in client_secret:
        raise ValueError("client_secret inválido — precisa ter a chave 'installed' ou 'web'.")
    (d / "google_client_secret.json").write_text(
        json.dumps(client_secret, indent=2), encoding="utf-8"
    )


def calendar_auth_url(d: Path) -> str:
    """Gera a URL de autorização OAuth para este perfil. Usuário abre no browser."""
    result = _run(d, SETUP_SCRIPT, ["--auth-url"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Falha ao gerar URL de autorização.")
    return result.stdout.strip()


def calendar_exchange_code(d: Path, code: str) -> str:
    """Troca o código de autorização (ou a URL de callback colada) pelo token, salvo neste perfil."""
    result = _run(d, SETUP_SCRIPT, ["--auth-code", code])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Falha ao trocar código por token.")
    return result.stdout.strip()


def calendar_create_event(
    d: Path,
    summary: str,
    start: str,
    end: str,
    location: str = "",
    description: str = "",
    attendees: str = "",
    calendar: str = "primary",
) -> dict:
    """
    Cria um evento no Google Calendar deste perfil.
    start/end: ISO 8601 com timezone, ex: '2026-07-10T14:00:00-03:00'
    attendees: e-mails separados por vírgula
    Retorna dict com htmlLink do evento criado.
    """
    args = [
        "calendar", "create",
        "--summary", summary,
        "--start", start,
        "--end", end,
        "--calendar", calendar,
    ]
    if location:
        args += ["--location", location]
    if description:
        args += ["--description", description]
    if attendees:
        args += ["--attendees", attendees]

    result = _run(d, GOOGLE_API, args)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"google_api.py saiu com código {result.returncode}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"raw": result.stdout.strip()}
