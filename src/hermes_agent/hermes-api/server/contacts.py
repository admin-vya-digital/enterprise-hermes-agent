"""
contacts.py — perfis de contato por agente (contact_type: owner | cliente).

Guarda em profiles/<agent_id>/contacts/<phone>.json. O plugin whatsapp-mixed
(instalado por perfil, ver templates/plugins/whatsapp-mixed/) lê esse mesmo
arquivo para decidir se um remetente é o dono do número ou um cliente.
"""

import time
from pathlib import Path

from hermes_fs import locked_json

CONTACT_TYPES = ("owner", "cliente")


def _contacts_dir(d: Path) -> Path:
    return d / "contacts"


def _contact_file(d: Path, phone: str) -> Path:
    return _contacts_dir(d) / f"{phone}.json"


def set_contact(d: Path, phone: str, contact_type: str, name: str = "", notes: str = "") -> dict:
    if contact_type not in CONTACT_TYPES:
        raise ValueError(f"contact_type inválido: '{contact_type}'. Use um de {CONTACT_TYPES}.")

    now = time.time()
    path = _contact_file(d, phone)
    with locked_json(path, default={}) as data:
        data["phone"] = phone
        data["contact_type"] = contact_type
        if name:
            data["name"] = name
        if notes:
            data["notes"] = notes
        data.setdefault("created_at", now)
        data["updated_at"] = now
        result = dict(data)
    return result


def get_contact(d: Path, phone: str) -> dict | None:
    path = _contact_file(d, phone)
    if not path.exists():
        return None
    import json
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def list_contacts(d: Path) -> list[dict]:
    cdir = _contacts_dir(d)
    if not cdir.is_dir():
        return []
    import json
    result = []
    for f in sorted(cdir.glob("*.json")):
        try:
            result.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            continue
    return result


def delete_contact(d: Path, phone: str) -> bool:
    path = _contact_file(d, phone)
    if not path.exists():
        return False
    path.unlink()
    return True
