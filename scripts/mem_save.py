#!/usr/bin/env python3
"""CLI tool to save memories to mini-Engram system (IMP-59).

Usage:
    # Basic usage
    python scripts/mem_save.py \\
        --title "API Authentication Pattern" \\
        --content "Use JWT tokens with 1h expiration..."

    # With category and tags
    python scripts/mem_save.py \\
        --title "Database Migration Strategy" \\
        --content "Use Alembic for migrations..." \\
        --category project \\
        --tags "database,migration,alembic"

    # From file
    python scripts/mem_save.py \\
        --title "IMP-59 Design" \\
        --file docs/IMP-59_DESIGN.md \\
        --category project

    # Append to existing memory
    python scripts/mem_save.py \\
        --title "API Authentication Pattern" \\
        --content "\\n\\n## Update: Added refresh token rotation" \\
        --append

    # Auto-generate title from content (first line)
    python scripts/mem_save.py \\
        --content "# JWT Authentication\\nUse JWT tokens..." \\
        --auto
"""

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.lib.memory import Memory, MemoryStore
from scripts.lib.sanitize import detect_secrets, sanitize, get_security_report

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Save a memory to mini-Engram system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Required (unless --auto)
    parser.add_argument(
        "--title",
        "-t",
        help="Memory title (required unless --auto)",
    )

    # Content sources (mutually exclusive)
    content_group = parser.add_mutually_exclusive_group(required=True)
    content_group.add_argument(
        "--content",
        "-c",
        help="Memory content (text)",
    )
    content_group.add_argument(
        "--file",
        "-f",
        type=Path,
        help="Read content from file",
    )

    # Optional metadata
    parser.add_argument(
        "--category",
        choices=["project", "team", "sessions"],
        default="project",
        help="Memory category (default: project)",
    )
    parser.add_argument(
        "--tags",
        help="Comma-separated tags (e.g., 'api,security,jwt')",
    )

    # Modes
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to existing memory (requires exact title match)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-generate title from first line of content",
    )

    # Output
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON (for scripting)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    return parser.parse_args()


def auto_generate_title(content: str) -> str:
    """Auto-generate title from first line of content."""
    lines = content.strip().split("\n")
    first_line = lines[0].strip()

    # If first line is markdown heading, use it
    if first_line.startswith("#"):
        title = first_line.lstrip("#").strip()
    else:
        # Use first line, truncate to 80 chars
        title = first_line[:80]
        if len(first_line) > 80:
            title += "..."

    return title


def validate_content(content: str, title: str, allow_sanitize: bool = True) -> str:
    """Validate content for security issues.

    Args:
        content: Memory content to validate
        title: Memory title
        allow_sanitize: If True, prompt user to sanitize if secrets detected

    Returns:
        Validated (and potentially sanitized) content
    """
    if not content.strip():
        log.error("❌ ERROR: Content is empty")
        sys.exit(1)

    # Basic validation
    if len(content) < 10:
        log.warning("⚠️  WARNING: Content is very short (%d chars)", len(content))

    # Security scan: detect potential secrets/PII
    findings = detect_secrets(content)

    if findings:
        # Display security report
        report = get_security_report(content)
        log.warning("")
        log.warning(report)
        log.warning("")
        log.warning("⚠️  SECURITY WARNING: Potential secrets/PII detected!")
        log.warning("")

        if not allow_sanitize:
            log.error("❌ Cannot save memory with secrets. Please remove sensitive data.")
            sys.exit(1)

        # Prompt user for action
        log.info("What would you like to do?")
        log.info("  1. Cancel save (review content manually)")
        log.info("  2. Sanitize content (auto-redact secrets)")
        log.info("  3. Save anyway (NOT RECOMMENDED - see MEMORY_POLICY.md)")
        log.info("")

        try:
            choice = input("Enter choice (1-3): ").strip()
        except (KeyboardInterrupt, EOFError):
            log.info("\n❌ Cancelled by user")
            sys.exit(1)

        if choice == "1":
            log.info("❌ Save cancelled. Please review and sanitize content manually.")
            sys.exit(0)
        elif choice == "2":
            log.info("")
            log.info("🔒 Sanitizing content...")
            sanitized_content, warnings = sanitize(content, redact=True)
            for warning in warnings:
                log.info("   ✓ %s", warning)
            log.info("")
            return sanitized_content
        elif choice == "3":
            log.warning("⚠️  Proceeding WITHOUT sanitization (user override)")
            log.warning("⚠️  Make sure content follows MEMORY_POLICY.md guidelines!")
            log.warning("")
            return content
        else:
            log.error("❌ Invalid choice. Cancelling save.")
            sys.exit(1)

    return content


def main():
    """Main CLI entry point."""
    args = parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Read content
    if args.file:
        try:
            content = args.file.read_text(encoding="utf-8")
            if args.verbose:
                log.debug("Read %d bytes from %s", len(content), args.file)
        except FileNotFoundError:
            log.error("❌ ERROR: File not found: %s", args.file)
            sys.exit(1)
        except Exception as e:
            log.error("❌ ERROR: Failed to read file: %s", e)
            sys.exit(1)
    else:
        content = args.content

    # Auto-generate title if requested
    if args.auto:
        if args.title:
            log.warning("⚠️  --auto flag ignores --title argument")
        title = auto_generate_title(content)
        if args.verbose:
            log.debug("Auto-generated title: %s", title)
    else:
        if not args.title:
            log.error("❌ ERROR: --title is required (or use --auto)")
            sys.exit(1)
        title = args.title

    # Parse tags
    tags = []
    if args.tags:
        tags = [tag.strip() for tag in args.tags.split(",")]
        if args.verbose:
            log.debug("Tags: %s", tags)

    # Validate content (may sanitize if secrets detected)
    content = validate_content(content, title)

    # Handle append mode
    if args.append:
        store = MemoryStore()
        # Search for existing memory by exact title match
        results = store.search(f'"{title}"', limit=1)  # Phrase search
        if results:
            existing = results[0]
            log.info("📝 Appending to existing memory: %s", existing.title)

            # Read existing content
            existing_content = existing.file_path.read_text(encoding="utf-8")
            # Extract body (skip frontmatter)
            if existing_content.startswith("---"):
                parts = existing_content.split("---", 2)
                if len(parts) >= 3:
                    existing_body = parts[2].strip()
                else:
                    existing_body = existing_content
            else:
                existing_body = existing_content

            # Append new content
            content = existing_body + "\n\n" + content
            if args.verbose:
                log.debug("New content length: %d bytes", len(content))
        else:
            log.warning(
                "⚠️  No existing memory found for title '%s'. Creating new memory.",
                title,
            )
        store.close()

    # Create memory object
    memory = Memory(
        title=title,
        content=content,
        category=args.category,
        tags=tags,
    )

    # Save to store
    try:
        store = MemoryStore()
        memory_id = store.save(memory)
        store.close()

        # Output
        if args.json:
            import json

            output = {
                "success": True,
                "id": memory_id,
                "title": title,
                "category": args.category,
                "tags": tags,
                "file": str(memory.file_path),
            }
            print(json.dumps(output, indent=2))
        else:
            log.info("✅ Memory saved successfully!")
            log.info("")
            log.info("   Title: %s", title)
            log.info("   Category: %s", args.category)
            if tags:
                log.info("   Tags: %s", ", ".join(tags))
            log.info("   File: %s", memory.file_path)
            log.info("   ID: %d", memory_id)
            log.info("")
            log.info("Search: python scripts/mem_search.py \"%s\"", title[:50])

    except Exception as e:
        if args.json:
            import json

            output = {"success": False, "error": str(e)}
            print(json.dumps(output, indent=2))
        else:
            log.error("❌ ERROR: Failed to save memory: %s", e)
            if args.verbose:
                import traceback

                traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
