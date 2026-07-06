#!/usr/bin/env python3
"""Core memory system for mini-Engram (IMP-59).

This module provides persistent memory storage with FTS5 full-text search.
Designed to integrate with GitHub Copilot workflow for context retention.

Architecture:
- Source of truth: .memory/memories/**/*.md (versionable, human-readable)
- Index cache: .memory/index/memory.db (SQLite FTS5, gitignored, rebuildable)

Classes:
- Memory: Data class representing a memory entry
- SearchResult: Search result with ranking and snippets
- MemoryStore: Main API for save/search/index operations

Usage:
    from scripts.lib.memory import MemoryStore

    store = MemoryStore()
    store.save(
        title="API Authentication Pattern",
        content="Use JWT tokens with 1h expiration...",
        category="project",
        tags=["api", "security"]
    )

    results = store.search("JWT authentication")
    for result in results:
        print(f"{result.title} (score: {result.score})")
"""

import hashlib
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ============================================================================
# Configuration
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent
MEMORY_ROOT = PROJECT_ROOT / ".memory"
MEMORY_DIR = MEMORY_ROOT / "memories"
INDEX_DIR = MEMORY_ROOT / "index"
DB_PATH = INDEX_DIR / "memory.db"

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class Memory:
    """Represents a memory entry."""

    title: str
    content: str
    category: str = "project"  # project, team, sessions
    tags: List[str] = field(default_factory=list)
    file_path: Optional[Path] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    memory_id: Optional[int] = None

    def __post_init__(self):
        """Validate and normalize fields."""
        if not self.title:
            raise ValueError("Memory title is required")
        if not self.content:
            raise ValueError("Memory content is required")
        if self.category not in ["project", "team", "sessions"]:
            raise ValueError(f"Invalid category: {self.category}")

        # Auto-generate file_path if not provided
        if not self.file_path:
            slug = self._slugify(self.title)
            date_str = datetime.now().strftime("%Y-%m-%d")
            self.file_path = MEMORY_DIR / self.category / f"{date_str}__{slug}.md"

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to slug (lowercase, dashes, no special chars)."""
        text = text.lower()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[-\s]+", "-", text)
        return text[:50]  # Max 50 chars

    def to_markdown(self) -> str:
        """Convert memory to markdown format."""
        frontmatter = [
            "---",
            f"title: {self.title}",
            f"category: {self.category}",
        ]
        if self.tags:
            frontmatter.append(f"tags: {', '.join(self.tags)}")
        if self.created_at:
            frontmatter.append(f"created: {self.created_at.isoformat()}")
        if self.updated_at:
            frontmatter.append(f"updated: {self.updated_at.isoformat()}")
        frontmatter.append("---")
        frontmatter.append("")

        return "\n".join(frontmatter) + self.content


@dataclass
class SearchResult:
    """Represents a search result with ranking."""

    memory_id: int
    file_path: Path
    title: str
    category: str
    tags: List[str]
    updated_at: datetime
    score: float  # FTS5 BM25 rank
    snippet: str = ""  # Relevant text excerpt


# ============================================================================
# Core Memory Store
# ============================================================================


class MemoryStore:
    """Main API for memory operations."""

    def __init__(self, db_path: Path = DB_PATH):
        """Initialize memory store."""
        self.db_path = db_path
        self._ensure_structure()
        self.conn = self._init_db()

    def _ensure_structure(self):
        """Ensure .memory directory structure exists."""
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        for category in ["project", "team", "sessions"]:
            (MEMORY_DIR / category).mkdir(parents=True, exist_ok=True)

    def _init_db(self) -> sqlite3.Connection:
        """Initialize SQLite database with FTS5 tables."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Access columns by name
        conn.execute("PRAGMA journal_mode=WAL")  # Concurrency support

        # Main table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT NOT NULL,
                tags TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                hash TEXT NOT NULL
            )
        """
        )

        # FTS5 virtual table for full-text search
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                title,
                content,
                tags,
                content=memories,
                content_rowid=id,
                tokenize='porter unicode61'
            )
        """
        )

        # Triggers to keep FTS5 in sync
        conn.executescript(
            """
            DROP TRIGGER IF EXISTS memories_ai;
            DROP TRIGGER IF EXISTS memories_au;
            DROP TRIGGER IF EXISTS memories_ad;

            CREATE TRIGGER memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, title, content, tags)
                SELECT new.id, new.title, new.content, new.tags;
            END;

            CREATE TRIGGER memories_au AFTER UPDATE ON memories BEGIN
                UPDATE memories_fts SET title=new.title, content=new.content, tags=new.tags
                WHERE rowid=new.id;
            END;

            CREATE TRIGGER memories_ad AFTER DELETE ON memories BEGIN
                DELETE FROM memories_fts WHERE rowid=old.id;
            END;
        """
        )

        # Indices for performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON memories(category)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_updated_at ON memories(updated_at DESC)")

        conn.commit()
        log.debug("Database initialized: %s", self.db_path)
        return conn

    def save(self, memory: Memory) -> int:
        """Save a memory to disk and index.

        Args:
            memory: Memory object to save

        Returns:
            int: Memory ID
        """
        # Ensure file path directory exists
        memory.file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write markdown file (source of truth)
        content_with_frontmatter = memory.to_markdown()
        memory.file_path.write_text(content_with_frontmatter, encoding="utf-8")

        # Prepare database fields
        tags_str = ",".join(memory.tags) if memory.tags else ""
        content_hash = hashlib.sha256(memory.content.encode()).hexdigest()
        now = datetime.now().isoformat()

        # Insert or update database
        cursor = self.conn.execute(
            """
            INSERT OR REPLACE INTO memories
            (file_path, title, content, category, tags, created_at, updated_at, hash)
            VALUES (
                ?, ?, ?, ?, ?,
                COALESCE((SELECT created_at FROM memories WHERE file_path = ?), ?),
                ?, ?
            )
        """,
            (
                str(memory.file_path),
                memory.title,
                memory.content,
                memory.category,
                tags_str,
                str(memory.file_path),
                now,
                now,
                content_hash,
            ),
        )

        self.conn.commit()
        memory_id = cursor.lastrowid
        log.info("✅ Memory saved: %s (ID: %d)", memory.title, memory_id)
        return memory_id

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[SearchResult]:
        """Search memories with FTS5 ranking.

        Args:
            query: Search query (supports FTS5 syntax: AND, OR, NOT, NEAR, "phrase")
            category: Filter by category (project, team, sessions)
            tags: Filter by tags
            limit: Maximum number of results

        Returns:
            List of SearchResult ordered by relevance
        """
        # Build SQL query
        sql_parts = [
            """
            SELECT
                m.id,
                m.file_path,
                m.title,
                m.category,
                m.tags,
                m.updated_at,
                bm25(memories_fts) AS score
            FROM memories_fts
            INNER JOIN memories m ON memories_fts.rowid = m.id
            WHERE memories_fts MATCH ?
        """
        ]
        params = [query]

        if category:
            sql_parts.append("AND m.category = ?")
            params.append(category)

        if tags:
            # Filter by tags using LIKE (SQLite doesn't have REGEXP by default)
            tag_conditions = []
            for tag in tags:
                tag_conditions.append("m.tags LIKE ?")
                params.append(f"%{tag}%")
            sql_parts.append(f"AND ({' OR '.join(tag_conditions)})")

        sql_parts.append("ORDER BY score")
        sql_parts.append("LIMIT ?")
        params.append(limit)

        sql = "\n".join(sql_parts)

        # Execute search
        cursor = self.conn.execute(sql, params)
        rows = cursor.fetchall()

        # Convert to SearchResult objects
        results = []
        for row in rows:
            tags_list = row["tags"].split(",") if row["tags"] else []
            result = SearchResult(
                memory_id=row["id"],
                file_path=Path(row["file_path"]),
                title=row["title"],
                category=row["category"],
                tags=tags_list,
                updated_at=datetime.fromisoformat(row["updated_at"]),
                score=row["score"],
                snippet=self._get_snippet(row["file_path"], query),
            )
            results.append(result)

        log.info("🔍 Found %d results for query: %s", len(results), query)
        return results

    def _get_snippet(self, file_path: str, query: str, context_lines: int = 2) -> str:
        """Extract relevant snippet from memory file."""
        try:
            content = Path(file_path).read_text(encoding="utf-8")
            # Simple implementation: find first line matching query
            query_terms = query.lower().split()
            for line in content.split("\n"):
                if any(term in line.lower() for term in query_terms):
                    return line.strip()[:200]  # Max 200 chars
            return content.split("\n")[0][:200]  # Fallback: first line
        except Exception as e:
            log.warning("Failed to get snippet from %s: %s", file_path, e)
            return ""

    def rebuild_index(self) -> int:
        """Rebuild index from markdown files (for recovery/migration).

        Returns:
            int: Number of memories indexed
        """
        log.info("Rebuilding index from .memory/memories/...")

        # Clear existing index
        self.conn.execute("DELETE FROM memories")
        self.conn.commit()

        # Scan all markdown files
        count = 0
        for md_file in MEMORY_DIR.rglob("*.md"):
            if md_file.name.startswith("."):
                continue  # Skip hidden files

            try:
                # Parse frontmatter + content
                content = md_file.read_text(encoding="utf-8")
                frontmatter, body = self._parse_markdown(content)

                # Create Memory object
                memory = Memory(
                    title=frontmatter.get("title", md_file.stem),
                    content=body,
                    category=frontmatter.get("category", "project"),
                    tags=frontmatter.get("tags", "").split(",") if frontmatter.get("tags") else [],
                    file_path=md_file,
                )

                # Save to index
                self.save(memory)
                count += 1

            except Exception as e:
                log.warning("Failed to index %s: %s", md_file, e)

        log.info("✅ Index rebuilt: %d memories", count)
        return count

    @staticmethod
    def _parse_markdown(content: str) -> Tuple[Dict[str, str], str]:
        """Parse frontmatter and body from markdown."""
        frontmatter = {}
        body = content

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                # Parse frontmatter
                fm_lines = parts[1].strip().split("\n")
                for line in fm_lines:
                    if ":" in line:
                        key, value = line.split(":", 1)
                        frontmatter[key.strip()] = value.strip()

                # Body is everything after second ---
                body = parts[2].strip()

        return frontmatter, body

    def get_stats(self) -> Dict[str, int]:
        """Get memory statistics."""
        stats = {}

        cursor = self.conn.execute("SELECT COUNT(*) FROM memories")
        stats["total"] = cursor.fetchone()[0]

        cursor = self.conn.execute("SELECT category, COUNT(*) FROM memories GROUP BY category")
        for row in cursor.fetchall():
            stats[f"category_{row[0]}"] = row[1]

        return stats

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            log.debug("Database connection closed")

    def __enter__(self):
        """Context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.close()
