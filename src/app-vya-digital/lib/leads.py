"""
leads.py — pipeline de qualificação de leads (kanban de fases).

Guarda em profiles/<agent_id>/leads.db. Cada lead vincula-se a um contato existente
via phone (E.164). Dados do lead (nome, email, etc) vêm do contato; o banco guarda
apenas fase, score de qualificação e histórico de movimentações.

Fases: 'phase_one' | 'phase_two' | 'phase_three' | 'phase_four' | 'phase_five'
(nomes são controlados no frontend para tradução/customização)
"""

import sqlite3
import time
from pathlib import Path
from contextlib import contextmanager

PHASES = ("phase_one", "phase_two", "phase_three", "phase_four", "phase_five")


def _leads_db(d: Path) -> Path:
    return d / "leads.db"


@contextmanager
def _get_db(d: Path):
    """Context manager para conexão SQLite com row factory."""
    db_path = _leads_db(d)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _init_db(d: Path):
    """Cria schema do leads.db se não existir (idempotente)."""
    db_path = _leads_db(d)
    if db_path.exists():
        return

    with _get_db(d) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE leads (
                contact_phone TEXT PRIMARY KEY,
                phase TEXT NOT NULL CHECK (phase IN ('phase_one', 'phase_two', 'phase_three', 'phase_four', 'phase_five')),
                qualification_score INTEGER DEFAULT 0,
                phase_entered_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE lead_phase_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_phone TEXT NOT NULL,
                from_phase TEXT,
                to_phase TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                FOREIGN KEY(contact_phone) REFERENCES leads(contact_phone)
            )
        """)
        cursor.execute("CREATE INDEX idx_leads_phase ON leads(phase)")
        cursor.execute("CREATE INDEX idx_leads_score ON leads(qualification_score DESC)")
        cursor.execute("CREATE INDEX idx_history_phone ON lead_phase_history(contact_phone)")
        conn.commit()


def create_lead(d: Path, contact_phone: str, initial_phase: str = "triage", score: int = 0) -> dict:
    """Cria novo lead. Validações básicas; contato deve existir no caller."""
    if initial_phase not in PHASES:
        raise ValueError(f"Fase inválida: '{initial_phase}'. Use um de {PHASES}.")
    if not (0 <= score <= 100):
        raise ValueError(f"Score fora do range [0, 100]: {score}")

    _init_db(d)
    now = int(time.time())

    with _get_db(d) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO leads (contact_phone, phase, qualification_score, phase_entered_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (contact_phone, initial_phase, score, now, now)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError(f"Lead para {contact_phone} já existe.")

    return get_lead(d, contact_phone)


def get_lead(d: Path, contact_phone: str) -> dict | None:
    """Retorna lead ou None se não existir."""
    _init_db(d)

    with _get_db(d) as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT * FROM leads WHERE contact_phone = ?",
            (contact_phone,)
        ).fetchone()

    if not row:
        return None

    return dict(row)


def list_leads(d: Path) -> list[dict]:
    """Retorna todos os leads, agrupados por fase para renderizar kanban."""
    _init_db(d)

    with _get_db(d) as conn:
        cursor = conn.cursor()
        rows = cursor.execute(
            "SELECT * FROM leads ORDER BY phase, qualification_score DESC"
        ).fetchall()

    return [dict(row) for row in rows]


def list_leads_by_phase(d: Path, phase: str) -> list[dict]:
    """Retorna leads de uma fase específica, ordenados por score."""
    if phase not in PHASES:
        raise ValueError(f"Fase inválida: '{phase}'")

    _init_db(d)

    with _get_db(d) as conn:
        cursor = conn.cursor()
        rows = cursor.execute(
            "SELECT * FROM leads WHERE phase = ? ORDER BY qualification_score DESC",
            (phase,)
        ).fetchall()

    return [dict(row) for row in rows]


def move_lead(d: Path, contact_phone: str, to_phase: str) -> dict:
    """Move lead para nova fase, registra transição no histórico."""
    if to_phase not in PHASES:
        raise ValueError(f"Fase inválida: '{to_phase}'")

    _init_db(d)
    now = int(time.time())

    with _get_db(d) as conn:
        cursor = conn.cursor()

        # Busca fase anterior
        current = cursor.execute(
            "SELECT phase FROM leads WHERE contact_phone = ?",
            (contact_phone,)
        ).fetchone()

        if not current:
            raise ValueError(f"Lead não encontrado: {contact_phone}")

        from_phase = current["phase"]

        # Atualiza lead
        cursor.execute(
            """
            UPDATE leads
            SET phase = ?, phase_entered_at = ?, updated_at = ?
            WHERE contact_phone = ?
            """,
            (to_phase, now, now, contact_phone)
        )

        # Registra no histórico
        cursor.execute(
            """
            INSERT INTO lead_phase_history (contact_phone, from_phase, to_phase, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (contact_phone, from_phase, to_phase, now)
        )

        conn.commit()

    return get_lead(d, contact_phone)


def update_score(d: Path, contact_phone: str, score: int) -> dict:
    """Atualiza qualification_score do lead."""
    if not (0 <= score <= 100):
        raise ValueError(f"Score fora do range [0, 100]: {score}")

    _init_db(d)
    now = int(time.time())

    with _get_db(d) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE leads SET qualification_score = ?, updated_at = ? WHERE contact_phone = ?",
            (score, now, contact_phone)
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Lead não encontrado: {contact_phone}")
        conn.commit()

    return get_lead(d, contact_phone)


def delete_lead(d: Path, contact_phone: str) -> bool:
    """Remove lead (contato permanece)."""
    _init_db(d)

    with _get_db(d) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM lead_phase_history WHERE contact_phone = ?", (contact_phone,))
        cursor.execute("DELETE FROM leads WHERE contact_phone = ?", (contact_phone,))
        conn.commit()

    return True


def get_phase_history(d: Path, contact_phone: str) -> list[dict]:
    """Retorna timeline de transições do lead."""
    _init_db(d)

    with _get_db(d) as conn:
        cursor = conn.cursor()
        rows = cursor.execute(
            """
            SELECT id, contact_phone, from_phase, to_phase, timestamp
            FROM lead_phase_history
            WHERE contact_phone = ?
            ORDER BY timestamp DESC
            """,
            (contact_phone,)
        ).fetchall()

    return [dict(row) for row in rows]


def get_stats(d: Path) -> dict:
    """Retorna agregados: total, por fase, score médio."""
    _init_db(d)

    with _get_db(d) as conn:
        cursor = conn.cursor()

        total = cursor.execute("SELECT COUNT(*) FROM leads").fetchone()[0]

        by_phase = {}
        for phase in PHASES:
            count = cursor.execute(
                "SELECT COUNT(*) FROM leads WHERE phase = ?",
                (phase,)
            ).fetchone()[0]
            by_phase[phase] = count

        avg_score = cursor.execute(
            "SELECT AVG(qualification_score) FROM leads"
        ).fetchone()[0]
        avg_score = round(avg_score or 0, 1)

    return {
        "total": total,
        "by_phase": by_phase,
        "avg_score": avg_score
    }
