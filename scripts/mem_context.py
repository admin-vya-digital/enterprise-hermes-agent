#!/usr/bin/env python3
"""CLI tool to suggest relevant memories based on current context (IMP-59 Phase 4).

This tool analyzes your current working context (git branch, recent commits, etc.)
and suggests relevant memories that might be helpful for your current task.

Usage:
    # Auto-detect context and suggest memories
    python scripts/mem_context.py --auto

    # Manual query
    python scripts/mem_context.py --query "implementing feature X"

    # Task-specific context
    python scripts/mem_context.py --task IMP-60

    # Limit results
    python scripts/mem_context.py --auto --limit 3

    # JSON output (for scripting)
    python scripts/mem_context.py --auto --json
"""

import argparse
import json
import logging
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.lib.memory import MemoryStore, SearchResult

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


@dataclass
class ContextSource:
    """Source of context information."""
    type: str  # "branch", "commit", "file", "task", "query"
    value: str
    weight: float  # Relevance weight (0.0-1.0)


@dataclass
class SuggestedMemory:
    """Memory suggestion with relevance score."""
    memory: SearchResult
    relevance: float  # 0-100 (percentage)
    reasons: List[str]  # Why this memory was suggested


def get_current_branch() -> str:
    """Get current git branch name."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def get_recent_commits(count: int = 10) -> List[str]:
    """Get recent commit messages."""
    try:
        result = subprocess.run(
            ["git", "log", f"-{count}", "--pretty=format:%s"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return [line.strip() for line in result.stdout.split("\n") if line.strip()]
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return []


def extract_keywords(text: str) -> List[str]:
    """Extract meaningful keywords from text.

    Args:
        text: Input text (branch name, commit message, etc.)

    Returns:
        List of keywords (lowercased, deduplicated)
    """
    # Remove common prefixes/patterns
    text = re.sub(r"^\d+-", "", text)  # "018-feature" -> "feature"
    text = re.sub(r"^(feat|fix|chore|docs|refactor|test|style|perf|ci|build)\([^)]+\):\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(feat|fix|chore|docs|refactor|test|style|perf|ci|build):\s*", "", text, flags=re.IGNORECASE)

    # Split on non-alphanumeric characters
    words = re.findall(r"\w+", text.lower())

    # Filter stopwords and short words
    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
        "been", "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "should", "could", "can", "may", "might", "must", "this",
        "that", "these", "those", "it", "its", "i", "you", "we", "they",
        "add", "update", "remove", "delete", "create", "make", "set", "get",
    }

    keywords = [w for w in words if w not in stopwords and len(w) >= 3]

    # Deduplicate while preserving order
    seen = set()
    unique_keywords = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique_keywords.append(kw)

    return unique_keywords


def analyze_context(branch: str = None, commits: List[str] = None, query: str = None, task: str = None) -> List[ContextSource]:
    """Analyze current context and extract keywords.

    Args:
        branch: Current git branch (if None, auto-detect)
        commits: Recent commit messages (if None, auto-detect)
        query: Manual query string
        task: Task ID (e.g., "IMP-60")

    Returns:
        List of context sources with weights
    """
    sources = []

    # Manual query (highest priority)
    if query:
        keywords = extract_keywords(query)
        sources.append(ContextSource(type="query", value=" ".join(keywords), weight=1.0))

    # Task ID
    if task:
        sources.append(ContextSource(type="task", value=task, weight=0.9))

    # Git branch (auto-detect if not provided)
    if branch is None:
        branch = get_current_branch()
    if branch and branch not in ("main", "master", "HEAD"):
        keywords = extract_keywords(branch)
        if keywords:
            sources.append(ContextSource(type="branch", value=" ".join(keywords), weight=0.8))

    # Recent commits (auto-detect if not provided)
    if commits is None:
        commits = get_recent_commits(count=5)
    if commits:
        # Combine and extract keywords from recent commits
        combined_commits = " ".join(commits[:5])  # Use only last 5
        keywords = extract_keywords(combined_commits)
        if keywords:
            # Take top 10 most frequent keywords
            keyword_freq = {}
            for kw in keywords:
                keyword_freq[kw] = keyword_freq.get(kw, 0) + 1
            top_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:10]
            sources.append(ContextSource(
                type="commit",
                value=" ".join(kw for kw, _ in top_keywords),
                weight=0.6
            ))

    return sources


def search_with_context(sources: List[ContextSource], limit: int = 5) -> List[SuggestedMemory]:
    """Search memories using context sources and calculate relevance.

    Args:
        sources: Context sources to search with
        limit: Maximum number of suggestions

    Returns:
        List of suggested memories with relevance scores
    """
    if not sources:
        return []

    store = MemoryStore()

    # Combine all keywords from sources (weighted)
    all_keywords = []
    for source in sources:
        keywords = source.value.split()
        for kw in keywords:
            all_keywords.append((kw, source.weight, source.type))

    # Build search query (OR all keywords)
    # Quote keywords to avoid FTS5 syntax errors with numbers or special chars
    query_parts = list(set(kw for kw, _, _ in all_keywords))
    quoted_keywords = [f'"{kw}"' for kw in query_parts[:20]]  # Limit to 20 keywords
    search_query = " OR ".join(quoted_keywords)

    if not search_query:
        store.close()
        return []

    # Search memories
    results = store.search(search_query, limit=limit * 3)  # Get more results for filtering
    store.close()

    # Calculate relevance for each result
    suggestions = []
    for result in results:
        relevance, reasons = calculate_relevance(result, all_keywords, sources)

        if relevance > 0:
            suggestions.append(SuggestedMemory(
                memory=result,
                relevance=relevance,
                reasons=reasons
            ))

    # Sort by relevance and take top N
    suggestions.sort(key=lambda x: x.relevance, reverse=True)
    return suggestions[:limit]


def calculate_relevance(result: SearchResult, keywords: List[Tuple[str, float, str]], sources: List[ContextSource]) -> Tuple[float, List[str]]:
    """Calculate relevance score for a memory result.

    Args:
        result: Search result from memory store
        keywords: List of (keyword, weight, source_type) tuples
        sources: Original context sources

    Returns:
        Tuple of (relevance_score 0-100, list_of_reasons)
    """
    score = 0.0
    reasons = []

    # Base score from FTS5 BM25 (normalized to 0-30)
    # FTS5 scores are negative, closer to 0 = more relevant
    base_score = min(30, max(0, -result.score * 10))
    score += base_score

    # Title match bonus (20 points)
    title_lower = result.title.lower()
    title_matches = sum(1 for kw, _, _ in keywords if kw in title_lower)
    if title_matches > 0:
        title_bonus = min(20, title_matches * 10)
        score += title_bonus
        reasons.append(f"Title matches {title_matches} keyword(s)")

    # Content match (from snippet) (15 points)
    if result.snippet:
        snippet_lower = result.snippet.lower()
        snippet_matches = sum(1 for kw, _, _ in keywords if kw in snippet_lower)
        if snippet_matches > 0:
            snippet_bonus = min(15, snippet_matches * 5)
            score += snippet_bonus

    # Tag match bonus (15 points)
    if result.tags:
        tags_lower = [tag.lower() for tag in result.tags]
        tag_matches = sum(1 for kw, _, _ in keywords if kw in tags_lower)
        if tag_matches > 0:
            tag_bonus = min(15, tag_matches * 10)
            score += tag_bonus
            reasons.append(f"Tags match: {', '.join(t for t in result.tags if any(kw in t.lower() for kw, _, _ in keywords))}")

    # Category bonus (10 points)
    if result.category == "project":
        score += 10
        reasons.append("Project-wide knowledge")
    elif result.category == "team":
        score += 5
        reasons.append("Team conventions")

    # Recency bonus (10 points for last 7 days)
    days_old = (datetime.now() - result.updated_at).days
    if days_old <= 7:
        recency_bonus = 10 * (1 - days_old / 7)
        score += recency_bonus
        reasons.append(f"Recently updated ({days_old}d ago)")

    # Source-specific bonuses
    for source in sources:
        if source.type == "task" and source.value.lower() in title_lower:
            score += 15
            reasons.append(f"Related to {source.value}")
        elif source.type == "branch":
            branch_keywords = source.value.split()
            branch_matches = sum(1 for kw in branch_keywords if kw in title_lower)
            if branch_matches > 0:
                score += 5
                reasons.append(f"Matches branch context")

    # Ensure score is in 0-100 range
    score = min(100, max(0, score))

    if not reasons:
        reasons.append("General keyword match")

    return score, reasons


def format_output(suggestions: List[SuggestedMemory], context_sources: List[ContextSource]) -> str:
    """Format suggestions as human-readable output."""
    if not suggestions:
        return "💡 No relevant memories found for current context."

    lines = []
    lines.append("")
    lines.append("💡 Suggested Context for Current Session")
    lines.append("─" * 60)

    # Show context analysis
    if context_sources:
        context_parts = []
        for source in context_sources:
            if source.type == "branch":
                context_parts.append(f"Branch: {source.value}")
            elif source.type == "commit":
                context_parts.append(f"Recent work: {source.value[:50]}...")
            elif source.type == "task":
                context_parts.append(f"Task: {source.value}")
            elif source.type == "query":
                context_parts.append(f"Query: {source.value}")

        lines.append(f"Based on: {', '.join(context_parts)}")
        lines.append("")

    lines.append("📌 Relevant Memories:")
    lines.append("")

    for i, suggestion in enumerate(suggestions, 1):
        mem = suggestion.memory
        lines.append(f"[{i}] {mem.title} ({suggestion.relevance:.0f}% relevance)")
        lines.append(f"    Category: {mem.category} | Tags: {', '.join(mem.tags) if mem.tags else 'none'}")
        lines.append(f"    File: {mem.file_path}")
        lines.append(f"    Why: {'; '.join(suggestion.reasons)}")
        lines.append("")

    lines.append("─" * 60)
    lines.append(f"💬 Found {len(suggestions)} relevant memor{'y' if len(suggestions) == 1 else 'ies'}")
    lines.append("")

    return "\n".join(lines)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Suggest relevant memories based on current context",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Modes
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-detect context from git branch and commits",
    )
    parser.add_argument(
        "--query",
        help="Manual query string",
    )
    parser.add_argument(
        "--task",
        help="Task ID (e.g., IMP-60)",
    )

    # Options
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of suggestions (default: 5)",
    )
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

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate arguments
    if not args.auto and not args.query and not args.task:
        log.error("❌ ERROR: Must specify --auto, --query, or --task")
        parser.print_help()
        sys.exit(1)

    # Analyze context
    if args.auto:
        sources = analyze_context()
        if args.verbose:
            log.debug("Auto-detected context sources: %d", len(sources))
            for source in sources:
                log.debug("  %s (weight=%.1f): %s", source.type, source.weight, source.value[:50])
    else:
        sources = analyze_context(query=args.query, task=args.task)

    if not sources:
        log.warning("⚠️  No context detected. Try using --query or --task.")
        sys.exit(0)

    # Search and suggest memories
    try:
        suggestions = search_with_context(sources, limit=args.limit)

        # Output
        if args.json:
            output = {
                "success": True,
                "context_sources": [
                    {"type": s.type, "value": s.value, "weight": s.weight}
                    for s in sources
                ],
                "suggestions": [
                    {
                        "title": s.memory.title,
                        "file": str(s.memory.file_path),
                        "category": s.memory.category,
                        "tags": s.memory.tags,
                        "relevance": s.relevance,
                        "reasons": s.reasons,
                    }
                    for s in suggestions
                ],
            }
            print(json.dumps(output, indent=2))
        else:
            output = format_output(suggestions, sources)
            print(output)

    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}, indent=2))
        else:
            log.error("❌ ERROR: %s", e)
            if args.verbose:
                import traceback
                traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
