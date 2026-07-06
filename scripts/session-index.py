#!/usr/bin/env python3
"""
Session Documentation Indexer

Builds and maintains a full-text search index of session documentation
using SQLite FTS5.

Part of: IMP-51 — MCP Search Integration for Session History
Created: 2026-04-05

Usage:
    # Build complete index
    python scripts/session-index.py

    # Rebuild from scratch
    python scripts/session-index.py --rebuild

    # Index specific session(s)
    python scripts/session-index.py --session 2026-04-03

    # Show index statistics
    python scripts/session-index.py --stats

Examples:
    # Initial indexing
    $ python scripts/session-index.py
    Indexing 18 activity files...
    ✓ 2026-03-29/DAILY_ACTIVITIES_2026-03-29.md (12 blocks)
    ✓ 2026-04-03/DAILY_ACTIVITIES_2026-04-03.md (8 blocks)
    ...
    Summary: 18 files, 142 blocks indexed

    # Update index after new session
    $ python scripts/session-index.py
    Indexing 1 new activity files...
    ✓ 2026-04-05/DAILY_ACTIVITIES_2026-04-05.md (3 blocks)
    Summary: 1 files, 3 blocks indexed
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.lib.search import SessionIndexer

# ANSI colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def main():
    parser = argparse.ArgumentParser(
        description="Index session documentation for full-text search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--sessions-dir",
        type=Path,
        default=Path("docs/SESSIONS"),
        help="Path to sessions directory (default: docs/SESSIONS)",
    )

    parser.add_argument(
        "--index-path",
        type=Path,
        default=Path(".session-index/index.db"),
        help="Path to index database (default: .session-index/index.db)",
    )

    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild index from scratch (clears existing data)",
    )

    parser.add_argument(
        "--scope",
        type=str,
        choices=["sessions", "docs", "specs", "chats", "all"],
        default="sessions",
        help="Scope of documents to index (default: sessions)",
    )

    parser.add_argument(
        "--session",
        type=str,
        help="Index specific session date (YYYY-MM-DD) - only for sessions scope",
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show index statistics and exit",
    )

    args = parser.parse_args()

    # Validate sessions directory
    if not args.sessions_dir.exists():
        print(f"{RED}✗ Error:{RESET} Sessions directory not found: {args.sessions_dir}")
        print(f"  Expected path: {args.sessions_dir.absolute()}")
        sys.exit(1)

    # Initialize indexer
    try:
        indexer = SessionIndexer(index_path=args.index_path)
    except Exception as e:
        print(f"{RED}✗ Error:{RESET} Failed to initialize indexer: {e}")
        sys.exit(1)

    # Show stats and exit
    if args.stats:
        stats = indexer.get_stats()
        print(f"\n{CYAN}{BOLD}Index Statistics{RESET}")
        print(f"{CYAN}{'─' * 40}{RESET}")
        print(f"Database:       {args.index_path}")
        print(f"Total sessions: {stats['total_sessions']}")
        print(f"Total blocks:   {stats['total_blocks']}")
        print(f"Last indexed:   {stats['last_indexed']}")
        print()
        indexer.close()
        sys.exit(0)

    # Index specific session (only valid for sessions scope)
    if args.session:
        if args.scope != "sessions":
            print(f"{RED}✗ Error:{RESET} --session flag is only valid with --scope sessions")
            sys.exit(1)

        session_dir = args.sessions_dir / args.session

        if not session_dir.exists():
            print(f"{RED}✗ Error:{RESET} Session directory not found: {session_dir}")
            sys.exit(1)

        activity_files = list(session_dir.glob("DAILY_ACTIVITIES_*.md"))
        activity_files.extend(session_dir.glob("TODAY_ACTIVITIES_*.md"))

        if not activity_files:
            print(f"{YELLOW}⚠ Warning:{RESET} No activity files found in {session_dir}")
            sys.exit(0)

        print(f"{BLUE}Indexing session {args.session}...{RESET}\n")

        total_blocks = 0
        for file_path in activity_files:
            try:
                blocks_count = indexer.index_file(file_path, document_type="sessions")
                total_blocks += blocks_count
                print(f"{GREEN}✓{RESET} {file_path.name} ({blocks_count} blocks)")
            except Exception as e:
                print(f"{RED}✗{RESET} {file_path.name}: {e}")

        print(f"\n{CYAN}Summary:{RESET} {len(activity_files)} file(s), {total_blocks} blocks indexed")
        indexer.close()
        sys.exit(0)

    # Index by scope
    print(f"\n{CYAN}{BOLD}Session Documentation Indexer{RESET}")
    print(f"{CYAN}{'─' * 40}{RESET}")
    print(f"Scope: {args.scope}\n")

    if args.rebuild:
        print(f"{YELLOW}⚠ Rebuilding index from scratch...{RESET}\n")

    try:
        files_indexed, blocks_indexed = indexer.index_by_scope(
            scope=args.scope,
            force_rebuild=args.rebuild,
        )

        print(f"\n{GREEN}✓ Indexing complete!{RESET}")
        print(f"  Index: {args.index_path}")
        print(f"  Scope: {args.scope}")
        print(f"  Files: {files_indexed}")
        print(f"  Blocks/Sections: {blocks_indexed}")
        print(f"\n{BLUE}💡 Tip:{RESET} Use 'python scripts/session-search.py --scope {args.scope}' to search indexed content\n")

    except Exception as e:
        print(f"\n{RED}✗ Error during indexing:{RESET} {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        indexer.close()


if __name__ == "__main__":
    main()
