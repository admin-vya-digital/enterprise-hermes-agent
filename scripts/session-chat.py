#!/usr/bin/env python3
"""
Session Chat Management CLI - IMP-55

Manage, capture, list, and search GitHub Copilot conversation files (CHAT-*.md).

Usage:
    ./scripts/session-chat.py capture --latest
    ./scripts/session-chat.py capture --transcript-id abc123
    ./scripts/session-chat.py list --date 2026-04-14
    ./scripts/session-chat.py search "IMP-55 implementation"
    ./scripts/session-chat.py export --chat CHAT-2026-04-14-1430.md --output context.md

Author: @yves_marinho
Created: 2026-04-14
Version: 1.0.0
"""

import argparse
import sys
from pathlib import Path

# Add scripts/lib to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from chat_capture import ChatCapture  # noqa: E402


def cmd_capture(args):
    """Capture a conversation transcript to CHAT-*.md format."""
    capture = ChatCapture(workspace_root=args.workspace)

    if args.latest:
        transcript_path = capture.get_latest_transcript()
        if not transcript_path:
            print("❌ No transcripts found")
            return 1
        print(f"📋 Capturing latest transcript: {transcript_path.name}")
    elif args.transcript_id:
        # Find transcript by ID
        transcript_path = capture.transcripts_dir / f"{args.transcript_id}.jsonl"
        if not transcript_path.exists():
            print(f"❌ Transcript not found: {transcript_path}")
            return 1
        print(f"📋 Capturing transcript: {args.transcript_id}")
    elif args.transcript:
        transcript_path = Path(args.transcript)
        if not transcript_path.exists():
            print(f"❌ Transcript not found: {transcript_path}")
            return 1
        print(f"📋 Capturing transcript: {transcript_path}")
    else:
        print("❌ Specify --latest, --transcript-id, or --transcript")
        return 1

    try:
        chat_path = capture.capture_to_markdown(transcript_path, session_date=args.session_date)
        print(f"✅ Chat captured: {chat_path}")
        print(f"   Location: {chat_path.relative_to(capture.workspace_root)}")
        return 0
    except Exception as e:
        print(f"❌ Capture failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_list(args):
    """List captured CHAT-*.md files."""
    workspace_root = Path(args.workspace)
    sessions_dir = workspace_root / "docs" / "SESSIONS"

    if not sessions_dir.exists():
        print(f"❌ Sessions directory not found: {sessions_dir}")
        return 1

    # Find CHAT-*.md files
    if args.date:
        # List chats for specific date
        session_dir = sessions_dir / args.date
        if not session_dir.exists():
            print(f"❌ No session found for date: {args.date}")
            return 1
        chat_files = sorted(session_dir.glob("CHAT-*.md"))
    else:
        # List all chats
        chat_files = sorted(sessions_dir.glob("*/CHAT-*.md"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not chat_files:
        print("❌ No CHAT files found")
        return 1

    print(f"📁 Found {len(chat_files)} chat files:\n")

    for chat_path in chat_files:
        # Read frontmatter to get metadata
        with open(chat_path, "r", encoding="utf-8") as f:
            content = f.read()

            # Extract session_id and duration from frontmatter
            import re
            session_id_match = re.search(r'^session_id:\s*["\']?([^"\'\n]+)', content, re.MULTILINE)
            duration_match = re.search(r'^start_time:\s*["\']?([^"\'\n]+).*?end_time:\s*["\']?([^"\'\n]+)', content, re.MULTILINE | re.DOTALL)
            topics_match = re.search(r'^topics:\s*\n((?:^-\s+.+\n?)+)', content, re.MULTILINE)

            session_id = session_id_match.group(1) if session_id_match else "unknown"
            start_time = duration_match.group(1) if duration_match else "unknown"
            end_time = duration_match.group(2) if duration_match else "unknown"

            topics = []
            if topics_match:
                topics_text = topics_match.group(1)
                topics = [line.strip('- \n') for line in topics_text.split('\n') if line.strip()]

        # Get file size
        size_kb = chat_path.stat().st_size / 1024

        # Print info
        print(f"📄 {chat_path.name}")
        print(f"   Date: {chat_path.parent.name}")
        print(f"   Time: {start_time} - {end_time}")
        print(f"   Size: {size_kb:.1f} KB")
        print(f"   Session ID: {session_id[:16]}...")
        if topics:
            print(f"   Topics: {', '.join(topics[:5])}")
        print()

    return 0


def cmd_search(args):
    """Search chat content using Session Search."""
    import subprocess

    # Delegate to session-search.py with --scope chats
    cmd = [
        "python",
        "scripts/session-search.py",
        "--scope", "chats",
    ]

    if args.limit:
        cmd.extend(["--limit", str(args.limit)])

    if args.date_from:
        cmd.extend(["--date-from", args.date_from])

    if args.date_to:
        cmd.extend(["--date-to", args.date_to])

    cmd.append(args.query)

    print(f"🔍 Searching chats: {args.query}\n")
    result = subprocess.run(cmd, cwd=args.workspace)
    return result.returncode


def cmd_export(args):
    """Export chat to a context file."""
    workspace_root = Path(args.workspace)

    # Find chat file
    if args.chat.startswith("CHAT-"):
        # Find in sessions directory
        sessions_dir = workspace_root / "docs" / "SESSIONS"
        chat_files = list(sessions_dir.glob(f"*/{args.chat}"))
        if not chat_files:
            print(f"❌ Chat file not found: {args.chat}")
            return 1
        chat_path = chat_files[0]
    else:
        chat_path = Path(args.chat)
        if not chat_path.exists():
            print(f"❌ Chat file not found: {chat_path}")
            return 1

    # Read chat content
    with open(chat_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Export to output file
    output_path = Path(args.output) if args.output else Path(f"{chat_path.stem}_context.md")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# Context from {chat_path.name}\n\n")
        f.write(content)

    print(f"✅ Exported to: {output_path}")
    print(f"   Size: {output_path.stat().st_size / 1024:.1f} KB")
    return 0


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Session Chat Management - Capture, list, search GitHub Copilot conversations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Capture latest conversation
  ./scripts/session-chat.py capture --latest

  # Capture specific transcript
  ./scripts/session-chat.py capture --transcript-id 9fd874f3-6871-4aa8-bd08-d20d55273600

  # List all chats
  ./scripts/session-chat.py list

  # List chats for specific date
  ./scripts/session-chat.py list --date 2026-04-14

  # Search in chats
  ./scripts/session-chat.py search "IMP-55 implementation"

  # Export chat to context file
  ./scripts/session-chat.py export --chat CHAT-2026-04-14-1317.md --output context.md
"""
    )

    parser.add_argument("--workspace", type=Path, default=Path.cwd(), help="Workspace root (default: current directory)")

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Capture command
    capture_parser = subparsers.add_parser("capture", help="Capture a conversation to CHAT-*.md")
    capture_parser.add_argument("--latest", action="store_true", help="Capture the latest transcript")
    capture_parser.add_argument("--transcript-id", help="Transcript ID to capture")
    capture_parser.add_argument("--transcript", type=Path, help="Path to specific transcript file")
    capture_parser.add_argument("--session-date", help="Session date (YYYY-MM-DD), default = today")

    # List command
    list_parser = subparsers.add_parser("list", help="List captured CHAT files")
    list_parser.add_argument("--date", help="Filter by session date (YYYY-MM-DD)")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search chat content")
    search_parser.add_argument("query", help="Search query (FTS5 syntax)")
    search_parser.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")
    search_parser.add_argument("--date-from", help="Filter by start date (YYYY-MM-DD)")
    search_parser.add_argument("--date-to", help="Filter by end date (YYYY-MM-DD)")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export chat to context file")
    export_parser.add_argument("--chat", required=True, help="Chat filename or path")
    export_parser.add_argument("--output", help="Output file path (default: <chat>_context.md)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Route to command handler
    handlers = {
        "capture": cmd_capture,
        "list": cmd_list,
        "search": cmd_search,
        "export": cmd_export,
    }

    handler = handlers.get(args.command)
    if not handler:
        print(f"❌ Unknown command: {args.command}")
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
