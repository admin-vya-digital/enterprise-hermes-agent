#!/usr/bin/env python3
"""CLI tool to search memories in mini-Engram system (IMP-59).

Usage:
    # Basic search
    python scripts/mem_search.py "JWT authentication"

    # With filters
    python scripts/mem_search.py \\
        --query "database migration" \\
        --category project \\
        --limit 5

    # Filter by tags
    python scripts/mem_search.py \\
        --query "API" \\
        --tags "security,authentication"

    # Advanced FTS5 syntax
    python scripts/mem_search.py "database AND migration"
    python scripts/mem_search.py "jwt OR oauth"
    python scripts/mem_search.py '"zero downtime deployment"'  # Phrase
    python scripts/mem_search.py "database NEAR/5 migration"  # Proximity

    # JSON output (for scripting)
    python scripts/mem_search.py "authentication" --json

    # Show full content
    python scripts/mem_search.py "authentication" --full
"""

import argparse
import json as json_module
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.lib.memory import MemoryStore

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Search memories in mini-Engram system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Query (positional or --query)
    parser.add_argument(
        "query",
        nargs="?",
        help="Search query (FTS5 syntax supported)",
    )
    parser.add_argument(
        "--query",
        "-q",
        help="Search query (alternative to positional argument)",
    )

    # Filters
    parser.add_argument(
        "--category",
        "-c",
        choices=["project", "team", "sessions"],
        help="Filter by category",
    )
    parser.add_argument(
        "--tags",
        "-t",
        help="Filter by tags (comma-separated)",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=10,
        help="Maximum number of results (default: 10)",
    )

    # Output options
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON (for scripting)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Show full content (not just snippets)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    return parser.parse_args()


def format_result_text(result, index: int, full_content: bool = False):
    """Format search result as text."""
    output = []

    # Header
    output.append(f"{index}. {result.title} (score: {result.score:.2f})")

    # Metadata
    metadata_parts = [f"Category: {result.category}"]
    if result.tags:
        metadata_parts.append(f"Tags: {', '.join(result.tags)}")
    metadata_parts.append(f"Updated: {result.updated_at.strftime('%Y-%m-%d')}")
    output.append(f"   {' | '.join(metadata_parts)}")

    # Snippet or full content
    if full_content:
        try:
            content = result.file_path.read_text(encoding="utf-8")
            # Skip frontmatter
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    content = parts[2].strip()

            output.append("")
            output.append("   " + "-" * 70)
            # Indent content
            for line in content.split("\n"):
                output.append(f"   {line}")
            output.append("   " + "-" * 70)
        except Exception as e:
            output.append(f"   ⚠️  Failed to read full content: {e}")
    else:
        if result.snippet:
            # Wrap snippet
            snippet = result.snippet
            if len(snippet) > 200:
                snippet = snippet[:197] + "..."
            output.append(f"   Snippet: {snippet}")

    # File path
    output.append(f"   File: {result.file_path}")

    return "\n".join(output)


def format_result_json(result):
    """Format search result as JSON-serializable dict."""
    return {
        "id": result.memory_id,
        "title": result.title,
        "category": result.category,
        "tags": result.tags,
        "updated_at": result.updated_at.isoformat(),
        "score": result.score,
        "snippet": result.snippet,
        "file_path": str(result.file_path),
    }


def main():
    """Main CLI entry point."""
    args = parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Get query
    query = args.query if args.query else args.query
    if not query:
        log.error("❌ ERROR: Query is required")
        log.error("Usage: python scripts/mem_search.py \"search query\"")
        sys.exit(1)

    # Parse tags
    tags = None
    if args.tags:
        tags = [tag.strip() for tag in args.tags.split(",")]
        if args.verbose:
            log.debug("Filtering by tags: %s", tags)

    # Search
    try:
        store = MemoryStore()

        if args.verbose:
            log.debug("Query: %s", query)
            log.debug("Category: %s", args.category)
            log.debug("Limit: %d", args.limit)

        results = store.search(
            query=query,
            category=args.category,
            tags=tags,
            limit=args.limit,
        )

        store.close()

        # Output
        if args.json:
            output = {
                "query": query,
                "count": len(results),
                "results": [format_result_json(r) for r in results],
            }
            print(json_module.dumps(output, indent=2))
        else:
            # Text output
            if not results:
                log.info("🔍 No results found for query: %s", query)
                log.info("")
                log.info("Tips:")
                log.info("  - Try broader keywords")
                log.info("  - Use FTS5 syntax: AND, OR, NOT, NEAR")
                log.info("  - Check spelling")
                log.info("  - Use --category or --tags filters")
                sys.exit(0)

            log.info("🔍 Found %d result(s) for query: %s", len(results), query)
            log.info("")

            for i, result in enumerate(results, 1):
                print(format_result_text(result, i, full_content=args.full))
                print()  # Blank line between results

            # Summary
            log.info("=" * 70)
            log.info("Total: %d result(s)", len(results))
            if len(results) == args.limit:
                log.info("(Showing top %d. Use --limit to see more)", args.limit)

    except Exception as e:
        if args.json:
            output = {
                "success": False,
                "error": str(e),
            }
            print(json_module.dumps(output, indent=2))
        else:
            log.error("❌ ERROR: Search failed: %s", e)
            if args.verbose:
                import traceback

                traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
