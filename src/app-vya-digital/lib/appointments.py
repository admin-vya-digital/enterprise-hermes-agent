"""
appointments.py — agenda de compromissos por perfil (data/hora marcada com um
contato).

Guarda em profiles/<agent_id>/appointments.db. Cada linha é um compromisso
vinculado a um contato via phone (E.164), com data/hora (unix ts, UTC) e um
status simples. Usado tanto pela aba "Agenda" do dashboard (calendário/dia a
dia) quanto pelo agente (skill `appointments`) para registrar o horário
combinado com o contato.
"""

import sqlite3
import time
from pathlib import Path
from contextlib import contextmanager

STATUSES = ("scheduled", "confirmed", "completed", "cancelled")


def _db_path(d: Path) -> Path:
    return d / "appointments.db"


@contextmanager
def _get_db(d: Path):
    db_path = _db_path(d)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _init_db(d: Path):
    db_path = _db_path(d)
    if db_path.exists():
        return

    with _get_db(d) as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_phone TEXT NOT NULL,
                scheduled_at INTEGER NOT NULL,
                title TEXT,
                notes TEXT,
                status TEXT NOT NULL DEFAULT 'scheduled' CHECK (status IN {STATUSES}),
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX idx_appt_scheduled ON appointments(scheduled_at)")
        cursor.execute("CREATE INDEX idx_appt_contact ON appointments(contact_phone)")
        conn.commit()


def create_appointment(d: Path, contact_phone: str, scheduled_at: int, title: str = "", notes: str = "") -> dict:
    """Cria um compromisso novo. scheduled_at é unix timestamp (segundos, UTC)."""
    _init_db(d)
    now = int(time.time())

    with _get_db(d) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO appointments (contact_phone, scheduled_at, title, notes, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'scheduled', ?, ?)
            """,
            (contact_phone, scheduled_at, title, notes, now, now)
        )
        conn.commit()
        appt_id = cursor.lastrowid

    return get_appointment(d, appt_id)


def get_appointment(d: Path, appt_id: int) -> dict | None:
    _init_db(d)
    with _get_db(d) as conn:
        row = conn.execute("SELECT * FROM appointments WHERE id = ?", (appt_id,)).fetchone()
    return dict(row) if row else None


def list_appointments(d: Path, start_ts: int | None = None, end_ts: int | None = None) -> list[dict]:
    """Lista compromissos, opcionalmente filtrando por janela de tempo (inclusive)."""
    _init_db(d)
    query = "SELECT * FROM appointments"
    clauses, params = [], []
    if start_ts is not None:
        clauses.append("scheduled_at >= ?")
        params.append(start_ts)
    if end_ts is not None:
        clauses.append("scheduled_at <= ?")
        params.append(end_ts)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY scheduled_at ASC"

    with _get_db(d) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def list_appointments_by_contact(d: Path, contact_phone: str) -> list[dict]:
    _init_db(d)
    with _get_db(d) as conn:
        rows = conn.execute(
            "SELECT * FROM appointments WHERE contact_phone = ? ORDER BY scheduled_at DESC",
            (contact_phone,)
        ).fetchall()
    return [dict(row) for row in rows]


def update_appointment(d: Path, appt_id: int, scheduled_at: int | None = None,
                        title: str | None = None, notes: str | None = None,
                        status: str | None = None) -> dict:
    """Atualiza campos informados (reagendar, editar nota, mudar status)."""
    if status is not None and status not in STATUSES:
        raise ValueError(f"Status inválido: '{status}'. Use um de {STATUSES}.")

    _init_db(d)
    current = get_appointment(d, appt_id)
    if not current:
        raise ValueError(f"Compromisso não encontrado: {appt_id}")

    now = int(time.time())
    new_vals = {
        "scheduled_at": scheduled_at if scheduled_at is not None else current["scheduled_at"],
        "title": title if title is not None else current["title"],
        "notes": notes if notes is not None else current["notes"],
        "status": status if status is not None else current["status"],
    }

    with _get_db(d) as conn:
        conn.execute(
            """
            UPDATE appointments
            SET scheduled_at = ?, title = ?, notes = ?, status = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_vals["scheduled_at"], new_vals["title"], new_vals["notes"], new_vals["status"], now, appt_id)
        )
        conn.commit()

    return get_appointment(d, appt_id)


def cancel_appointment(d: Path, appt_id: int) -> dict:
    return update_appointment(d, appt_id, status="cancelled")


def delete_appointment(d: Path, appt_id: int) -> bool:
    _init_db(d)
    with _get_db(d) as conn:
        conn.execute("DELETE FROM appointments WHERE id = ?", (appt_id,))
        conn.commit()
    return True
