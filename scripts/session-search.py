#!/usr/bin/env python3
"""
Session Documentation Search

Search through indexed session documentation using full-text search.

Part of: IMP-51 — MCP Search Integration for Session History
Created: 2026-04-05

Usage:
    # Simple keyword search
    python scripts/session-search.py "validador semver"

    # Phrase search
    python scripts/session-search.py '"bug fix"'

    # Boolean queries
    python scripts/session-search.py "python AND fastapi"
    python scripts/session-search.py "IMP-47 OR IMP-48"

    # Date range filtering
    python scripts/session-search.py "migration" --from 2026-03-01 --to 2026-04-05

    # Show full context of result
    python scripts/session-search.py "validador" --context

    # Limit results
    python scripts/session-search.py "session" --limit 5

Examples:
    # Find when semver validator was implemented
    $ python scripts/session-search.py "validador de semver"

    2026-03-23 16:00 — Bug Analysis & Fix
    …Corrigir <mark>validador</mark> de <mark>semver</mark> em versões pre-release…

    # Find all IMP-47 related activities
    $ python scripts/session-search.py "IMP-47"

    2026-03-23 16:00 — Bug Analysis & Fix (IMP-47)
    …análise detalhada do bug <mark>IMP-47</mark> nested folder issue…

    # Find Python-related work in April
    $ python scripts/session-search.py "python" --from 2026-04-01

    2026-04-03 14:32 — Migration Script Implementation
    …Implementado migration script em <mark>Python</mark> com 600 linhas…

FTS5 Query Syntax:
    - Simple keywords:  python fastapi
    - Phrase search:    "bug fix"
    - AND operator:     python AND fastapi
    - OR operator:      IMP-47 OR IMP-48
    - NOT operator:     python NOT test
    - NEAR operator:    migration NEAR/3 script
    - Column search:    title:IMP-47
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.lib.search import SessionSearcher

# ANSI colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def format_snippet(snippet: str) -> str:
    """Format snippet with ANSI colors for terminal output."""
    # Replace HTML marks with ANSI colors
    snippet = snippet.replace("<mark>", f"{YELLOW}{BOLD}")
    snippet = snippet.replace("</mark>", RESET)
    return snippet


def print_result(result, show_context: bool = False, searcher = None):
    """Print a single search result."""
    # Document type badge
    doc_type_badge = ""
    if result.document_type == "docs":
        doc_type_badge = f"[{BLUE}DOC{RESET}] "
    elif result.document_type == "specs":
        doc_type_badge = f"[{GREEN}SPEC{RESET}] "
    elif result.document_type == "sessions":
        doc_type_badge = f"[{CYAN}SESSION{RESET}] "

    # Header: date + timestamp + title
    print(f"{doc_type_badge}{CYAN}{result.session_date}{RESET} {DIM}{result.timestamp}{RESET} — {BOLD}{result.title}{RESET}")

    # Snippet with highlighted matches
    snippet = format_snippet(result.snippet)
    print(f"  {snippet}")

    # Optional: show full context
    if show_context and searcher:
        context = searcher.get_activity_context(result.session_date, result.title)
        if context:
            print(f"\n{DIM}{'─' * 60}{RESET}")
            print(context)
            print(f"{DIM}{'─' * 60}{RESET}")

    print()  # Blank line between results


def main():
    parser = argparse.ArgumentParser(
        description="Search session documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "query",
        type=str,
        help="Search query (FTS5 syntax)",
    )

    parser.add_argument(
        "--index-path",
        type=Path,
        default=Path(".session-index/index.db"),
        help="Path to index database (default: .session-index/index.db)",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of results (default: 20)",
    )

    parser.add_argument(
        "--from",
        dest="date_from",
        type=str,
        help="Filter by start date (YYYY-MM-DD)",
    )

    parser.add_argument(
        "--to",
        dest="date_to",
        type=str,
        help="Filter by end date (YYYY-MM-DD)",
    )

    parser.add_argument(
        "--scope",
        type=str,
        choices=["sessions", "docs", "specs", "chats", "all"],
        help="Filter by document type (sessions, docs, specs, or all)",
    )

    parser.add_argument(
        "--context",
        action="store_true",
        help="Show full activity block for each result",
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show search statistics",
    )

    args = parser.parse_args()

    # Check if index exists
    if not args.index_path.exists():
        print(f"{RED}✗ Error:{RESET} Index database not found: {args.index_path}")
        print(f"\n{BLUE}💡 Tip:{RESET} Build the index first:")
        print(f"  python scripts/session-index.py\n")
        sys.exit(1)

    # Initialize searcher
    try:
        searcher = SessionSearcher(index_path=args.index_path)
    except Exception as e:
        print(f"{RED}✗ Error:{RESET} Failed to initialize searcher: {e}")
        sys.exit(1)

    # Perform search
    try:
        results = searcher.search(
            query=args.query,
            limit=args.limit,
            date_from=args.date_from,
            date_to=args.date_to,
            scope=args.scope,
        )

        # Print header
        print(f"\n{CYAN}{BOLD}Search Results{RESET}")
        print(f"{CYAN}{'─' * 60}{RESET}")
        print(f"Query: {BOLD}{args.query}{RESET}")
        if args.date_from:
            print(f"From:  {args.date_from}")
        if args.date_to:
            print(f"To:    {args.date_to}")
        if args.scope:
            print(f"Scope: {args.scope}")
        print(f"Found: {BOLD}{len(results)}{RESET} result(s)")
        print(f"{CYAN}{'─' * 60}{RESET}\n")

        # Print results
        if not results:
            print(f"{YELLOW}No results found{RESET}\n")
            print(f"{BLUE}💡 Tips:{RESET}")
            print(f"  - Try different keywords")
            print(f"  - Use broader search terms")
            print(f"  - Check spelling")
            print(f"  - Use FTS5 syntax (see --help for examples)\n")
        else:
            for i, result in enumerate(results, 1):
                if args.stats:
                    print(f"{DIM}[{i}] Rank: {result.rank:.4f}{RESET}")
                print_result(result, show_context=args.context, searcher=searcher)

        # Stats summary
        if args.stats and results:
            avg_rank = sum(r.rank for r in results) / len(results)
            print(f"\n{CYAN}{'─' * 60}{RESET}")
            print(f"Average rank: {avg_rank:.4f}")
            print(f"Best match:   {results[0].title if results else 'N/A'}")

    except ValueError as e:
        print(f"{RED}✗ Invalid query:{RESET} {e}")
        print(f"\n{BLUE}💡 FTS5 query syntax:{RESET}")
        print(f"  Simple:      python fastapi")
        print(f"  Phrase:      \"bug fix\"")
        print(f"  Boolean AND: python AND fastapi")
        print(f"  Boolean OR:  IMP-47 OR IMP-48")
        print(f"  Exclude:     python NOT test")
        print(f"  Near:        migration NEAR/3 script")
        print(f"\nSee --help for more examples\n")
        sys.exit(1)

    except Exception as e:
        print(f"{RED}✗ Error during search:{RESET} {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        searcher.close()


if __name__ == "__main__":
    main()
