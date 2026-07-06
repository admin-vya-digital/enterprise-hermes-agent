#!/usr/bin/env python3
"""
session-time-tracker.py — Session Time Tracking with Breaks

Rastreia tempo de trabalho de sessões com suporte a pausas (café, almoço, etc.)
Gera CSV com estatísticas de tempo por sessão.

Uso:
    # Iniciar sessão
    python scripts/session-time-tracker.py start

    # Pausar (café, almoço, etc.)
    python scripts/session-time-tracker.py pause "café"

    # Retomar após pausa
    python scripts/session-time-tracker.py resume

    # Finalizar sessão
    python scripts/session-time-tracker.py stop

    # Visualizar estatísticas
    python scripts/session-time-tracker.py stats [--date YYYY-MM-DD]

    # Exportar CSV
    python scripts/session-time-tracker.py export [--output PATH]
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Local imports
sys.path.insert(0, str(Path(__file__).parent))
from lib.git_validators import validate_branch_name, format_validation_errors

try:
    from rich.console import Console
    from rich.table import Table
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    print("⚠️  Install 'rich' for better output: pip install rich", file=sys.stderr)

# Arquivo de estado da sessão atual
STATE_FILE = Path(__file__).parent.parent / ".session-time" / "current.json"
# Arquivo CSV com histórico de sessões
HISTORY_CSV = Path(__file__).parent.parent / ".session-time" / "history.csv"


def _ensure_dirs():
    """Garante que diretórios necessários existem."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)


def _get_current_branch() -> str | None:
    """Retorna nome da branch Git atual, ou None se não estiver em repo Git."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path.cwd()
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _iso_now() -> str:
    """Retorna timestamp ISO 8601 UTC."""
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _format_duration(seconds: float) -> str:
    """Formata duração em formato legível (HH:MM:SS)."""
    td = timedelta(seconds=int(seconds))
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _force_finish_orphan(state: dict[str, Any]):
    """Finaliza sessão órfã automaticamente."""
    # Se houver pausa pendente, finalizá-la primeiro
    if state.get("current_pause"):
        now = _iso_now()
        pause = state["current_pause"]
        pause["end"] = now
        start = datetime.fromisoformat(pause["start"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(now.replace("Z", "+00:00"))
        pause["duration_seconds"] = (end - start).total_seconds()
        state["pauses"].append(pause)
        state["current_pause"] = None

    # Finalizar sessão
    now = _iso_now()
    state["end_time"] = now
    state["status"] = "auto_completed_orphan"

    # Calcular durações
    start = datetime.fromisoformat(state["start_time"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(now.replace("Z", "+00:00"))
    total_seconds = (end - start).total_seconds()
    pause_seconds = sum(p.get("duration_seconds", 0) for p in state.get("pauses", []))
    net_seconds = total_seconds - pause_seconds

    state["total_duration_seconds"] = total_seconds
    state["pause_duration_seconds"] = pause_seconds
    state["net_duration_seconds"] = net_seconds

    # Salvar no CSV
    _save_to_csv(state)

    # Remover arquivo órfão
    STATE_FILE.unlink()


def cmd_start():
    """Inicia nova sessão de trabalho."""
    _ensure_dirs()

    # Verificar se há sessão em andamento
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)

        current_date = datetime.utcnow().strftime("%Y-%m-%d")
        session_date = state.get("session_date", "")

        # Detectar sessão órfã (de outro dia)
        if session_date and session_date != current_date:
            print(f"⚠️  Sessão órfã detectada de {session_date} (hoje: {current_date})", file=sys.stderr)
            print(f"   Iniciada em: {state.get('start_time', 'desconhecido')}", file=sys.stderr)
            print(f"   Status: {state.get('status', 'unknown')}", file=sys.stderr)
            print("\n🔧 Auto-finalizando sessão órfã...", file=sys.stderr)

            # Auto-finalizar sessão órfã
            _force_finish_orphan(state)
            print("✅ Sessão órfã finalizada. Iniciando nova sessão...\n")
        else:
            # Sessão do mesmo dia ainda ativa
            print("❌ Sessão já em andamento. Use 'stop' para finalizar antes de iniciar nova.", file=sys.stderr)
            print(f"   Data: {session_date}", file=sys.stderr)
            print(f"   Início: {state.get('start_time', 'desconhecido')}", file=sys.stderr)
            print(f"   Status: {state.get('status', 'unknown')}", file=sys.stderr)
            print("\n💡 Use 'python scripts/session-time-tracker.py cleanup' para forçar limpeza.", file=sys.stderr)
            return 1

    # Validar nome da branch Git (melhores práticas GitHub)
    current_branch = _get_current_branch()
    if current_branch:
        validation = validate_branch_name(current_branch)

        if not validation.is_valid:
            print(f"\n⚠️  Branch '{current_branch}' não segue convenções do projeto:", file=sys.stderr)
            print(format_validation_errors(validation), file=sys.stderr)
            print("\n💡 Dicas:", file=sys.stderr)
            print("   - Use formato: feature/NNN-descricao, fix/descricao, etc.", file=sys.stderr)
            print("   - Apenas lowercase com hífens", file=sys.stderr)
            print("   - Veja CONTRIBUTING.md para detalhes", file=sys.stderr)
            print("\n❓ Continuar mesmo assim? (y/N): ", end="", file=sys.stderr)

            response = input().strip().lower()
            if response not in ("y", "yes", "s", "sim"):
                print("❌ Sessão não iniciada. Corrija o nome da branch primeiro.", file=sys.stderr)
                return 1
            print("⚠️  Continuando com branch não-padrão...\n", file=sys.stderr)

        elif validation.warnings:
            print(f"\n⚠️  Avisos para branch '{current_branch}':", file=sys.stderr)
            for warning in validation.warnings:
                print(f"   - {warning}", file=sys.stderr)
            print("")  # linha em branco

    now = _iso_now()
    date = datetime.utcnow().strftime("%Y-%m-%d")

    state = {
        "session_date": date,
        "start_time": now,
        "pauses": [],
        "current_pause": None,
        "status": "active"
    }

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

    print(f"✅ Sessão iniciada: {now}")
    print(f"📅 Data: {date}")
    return 0


def cmd_pause(reason: str = "break"):
    """Pausa a sessão atual (café, almoço, etc.)."""
    if not STATE_FILE.exists():
        print("❌ Nenhuma sessão ativa. Use 'start' primeiro.", file=sys.stderr)
        return 1

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    if state.get("current_pause"):
        print("❌ Sessão já pausada. Use 'resume' para retomar.", file=sys.stderr)
        return 1

    now = _iso_now()
    state["current_pause"] = {
        "start": now,
        "reason": reason
    }
    state["status"] = "paused"

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

    print(f"⏸️  Sessão pausada: {now}")
    print(f"   Motivo: {reason}")
    return 0


def cmd_resume():
    """Retoma sessão após pausa."""
    if not STATE_FILE.exists():
        print("❌ Nenhuma sessão ativa.", file=sys.stderr)
        return 1

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    if not state.get("current_pause"):
        print("❌ Sessão não está pausada.", file=sys.stderr)
        return 1

    now = _iso_now()
    pause = state["current_pause"]
    pause["end"] = now

    # Calcular duração da pausa
    start = datetime.fromisoformat(pause["start"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(now.replace("Z", "+00:00"))
    pause["duration_seconds"] = (end - start).total_seconds()

    state["pauses"].append(pause)
    state["current_pause"] = None
    state["status"] = "active"

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

    duration = _format_duration(pause["duration_seconds"])
    print(f"▶️  Sessão retomada: {now}")
    print(f"   Pausa: {duration} ({pause['reason']})")
    return 0


def cmd_stop():
    """Finaliza sessão atual e salva no histórico."""
    if not STATE_FILE.exists():
        print("❌ Nenhuma sessão ativa.", file=sys.stderr)
        return 1

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    if state.get("current_pause"):
        print("⚠️  Sessão ainda pausada. Retomando automaticamente antes de finalizar.")
        cmd_resume()
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)

    now = _iso_now()
    state["end_time"] = now
    state["status"] = "completed"

    # Calcular duração total e líquida
    start = datetime.fromisoformat(state["start_time"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(now.replace("Z", "+00:00"))
    total_seconds = (end - start).total_seconds()

    pause_seconds = sum(p.get("duration_seconds", 0) for p in state["pauses"])
    net_seconds = total_seconds - pause_seconds

    state["total_duration_seconds"] = total_seconds
    state["pause_duration_seconds"] = pause_seconds
    state["net_duration_seconds"] = net_seconds

    # Salvar no CSV
    _save_to_csv(state)

    # Remover arquivo de estado
    STATE_FILE.unlink()

    print(f"🏁 Sessão finalizada: {now}")
    print(f"   Duração total: {_format_duration(total_seconds)}")
    print(
        f"   Pausas: {_format_duration(pause_seconds)} ({len(state['pauses'])} pausa(s))")
    print(f"   Tempo líquido: {_format_duration(net_seconds)}")
    return 0


def _save_to_csv(state: dict[str, Any]):
    """Salva sessão no histórico CSV."""
    _ensure_dirs()

    # Criar CSV se não existir
    file_exists = HISTORY_CSV.exists()

    with open(HISTORY_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "session_date", "start_time", "end_time",
            "total_duration", "pause_duration", "net_duration",
            "num_pauses", "pause_details"
        ])

        if not file_exists:
            writer.writeheader()

        pause_details = "; ".join(
            f"{p['reason']}:{_format_duration(p.get('duration_seconds', 0))}"
            for p in state.get("pauses", [])
        ) or "none"

        writer.writerow({
            "session_date": state["session_date"],
            "start_time": state["start_time"],
            "end_time": state["end_time"],
            "total_duration": _format_duration(state["total_duration_seconds"]),
            "pause_duration": _format_duration(state["pause_duration_seconds"]),
            "net_duration": _format_duration(state["net_duration_seconds"]),
            "num_pauses": len(state.get("pauses", [])),
            "pause_details": pause_details
        })


def cmd_stats(date: str | None = None):
    """Exibe estatísticas de sessões."""
    if not HISTORY_CSV.exists():
        print("❌ Nenhum histórico encontrado.", file=sys.stderr)
        return 1

    sessions = []
    with open(HISTORY_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if date is None or row["session_date"] == date:
                sessions.append(row)

    if not sessions:
        print(
            f"❌ Nenhuma sessão encontrada{f' para {date}' if date else ''}.", file=sys.stderr)
        return 1

    if HAS_RICH:
        _print_stats_rich(sessions, date)
    else:
        _print_stats_plain(sessions, date)

    return 0


def _print_stats_rich(sessions: list[dict], date_filter: str | None):
    """Exibe estatísticas com Rich."""
    console = Console()

    title = "📊 Estatísticas de Sessões"
    if date_filter:
        title += f" — {date_filter}"

    table = Table(title=title, show_header=True, header_style="bold magenta")
    table.add_column("Data", style="cyan")
    table.add_column("Início", style="green")
    table.add_column("Fim", style="green")
    table.add_column("Total", justify="right")
    table.add_column("Pausas", justify="right")
    table.add_column("Líquido", justify="right", style="bold yellow")
    table.add_column("# Pausas", justify="center")

    for s in sessions:
        table.add_row(
            s["session_date"],
            s["start_time"].split("T")[1].replace("Z", ""),
            s["end_time"].split("T")[1].replace("Z", ""),
            s["total_duration"],
            s["pause_duration"],
            s["net_duration"],
            s["num_pauses"]
        )

    console.print(table)


def _print_stats_plain(sessions: list[dict], date_filter: str | None):
    """Exibe estatísticas em texto simples."""
    header = "📊 Estatísticas de Sessões"
    if date_filter:
        header += f" — {date_filter}"
    print(f"\n{header}\n{'=' * len(header)}\n")

    for s in sessions:
        print(f"Data: {s['session_date']}")
        print(f"  Início: {s['start_time']}")
        print(f"  Fim:    {s['end_time']}")
        print(f"  Total:  {s['total_duration']}")
        print(f"  Pausas: {s['pause_duration']} ({s['num_pauses']} pausa(s))")
        print(f"  Líquido: {s['net_duration']}")
        print()


def cmd_export(output: str | None = None):
    """Exporta histórico para CSV."""
    if not HISTORY_CSV.exists():
        print("❌ Nenhum histórico encontrado.", file=sys.stderr)
        return 1

    dest = Path(output) if output else Path.cwd() / "session-time-history.csv"

    import shutil
    shutil.copy(HISTORY_CSV, dest)

    print(f"✅ Histórico exportado: {dest}")
    return 0


def cmd_status():
    """Exibe status da sessão atual."""
    if not STATE_FILE.exists():
        print("📊 Status: Nenhuma sessão ativa")
        return 0

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    current_date = datetime.utcnow().strftime("%Y-%m-%d")
    session_date = state.get("session_date", "unknown")
    is_orphan = session_date != current_date

    print("\n📊 Status da Sessão Atual")
    print("=" * 40)
    print(f"Data da sessão: {session_date}")
    print(f"Data atual:     {current_date}")

    if is_orphan:
        print(f"⚠️  Status:        ÓRFÃ (sessão de outro dia)")
    else:
        print(f"✅ Status:        {state.get('status', 'unknown').upper()}")

    print(f"Início:         {state.get('start_time', 'desconhecido')}")

    # Calcular tempo decorrido
    start = datetime.fromisoformat(state["start_time"].replace("Z", "+00:00"))
    now_dt = datetime.fromisoformat(_iso_now().replace("Z", "+00:00"))
    elapsed_seconds = (now_dt - start).total_seconds()

    print(f"Tempo decorrido: {_format_duration(elapsed_seconds)}")
    print(f"Número de pausas: {len(state.get('pauses', []))}")

    if state.get("current_pause"):
        print(f"Pausa ativa:    {state['current_pause'].get('reason', 'sem motivo')}")
        pause_start = datetime.fromisoformat(state["current_pause"]["start"].replace("Z", "+00:00"))
        pause_elapsed = (now_dt - pause_start).total_seconds()
        print(f"Duração da pausa: {_format_duration(pause_elapsed)}")

    if is_orphan:
        print("\n💡 Ações disponíveis:")
        print("   - 'cleanup' para forçar limpeza")
        print("   - 'start' para auto-finalizar e iniciar nova sessão")

    print()
    return 0


def cmd_cleanup(force: bool = False):
    """Limpa sessão órfã ou corrompida."""
    if not STATE_FILE.exists():
        print("✅ Nenhuma sessão órfã encontrada.")
        return 0

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    current_date = datetime.utcnow().strftime("%Y-%m-%d")
    session_date = state.get("session_date", "")

    print("\n🗑️  Cleanup de Sessão")
    print("=" * 40)
    print(f"Data da sessão: {session_date}")
    print(f"Início:         {state.get('start_time', 'desconhecido')}")
    print(f"Status:         {state.get('status', 'unknown')}")

    if not force and session_date == current_date:
        print("\n⚠️  AVISO: Esta sessão é do dia atual!")
        print("   Use '--force' para forçar limpeza mesmo assim.")
        return 1

    print("\n🔧 Finalizando e salvando sessão no histórico...")
    _force_finish_orphan(state)

    print("✅ Sessão limpa com sucesso.")
    print("   A sessão foi salva no histórico antes da remoção.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Session Time Tracker — Rastreamento de tempo com pausas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest="command", help="Comando")

    # start
    subparsers.add_parser("start", help="Iniciar nova sessão")

    # pause
    pause_parser = subparsers.add_parser("pause", help="Pausar sessão")
    pause_parser.add_argument(
        "reason", nargs="?", default="break", help="Motivo da pausa")

    # resume
    subparsers.add_parser("resume", help="Retomar sessão")

    # stop
    subparsers.add_parser("stop", help="Finalizar sessão")

    # stats
    stats_parser = subparsers.add_parser("stats", help="Exibir estatísticas")
    stats_parser.add_argument("--date", help="Filtrar por data (YYYY-MM-DD)")

    # export
    export_parser = subparsers.add_parser("export", help="Exportar CSV")
    export_parser.add_argument("--output", help="Caminho do arquivo de saída")

    # status
    subparsers.add_parser("status", help="Exibir status da sessão atual")

    # cleanup
    cleanup_parser = subparsers.add_parser("cleanup", help="Limpar sessão órfã")
    cleanup_parser.add_argument("--force", action="store_true",
                                help="Forçar limpeza mesmo se for sessão do dia atual")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "start":
        return cmd_start()
    elif args.command == "pause":
        return cmd_pause(args.reason)
    elif args.command == "resume":
        return cmd_resume()
    elif args.command == "stop":
        return cmd_stop()
    elif args.command == "stats":
        return cmd_stats(args.date)
    elif args.command == "export":
        return cmd_export(args.output)
    elif args.command == "status":
        return cmd_status()
    elif args.command == "cleanup":
        return cmd_cleanup(args.force)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
