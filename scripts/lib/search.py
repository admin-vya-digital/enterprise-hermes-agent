"""
Session Search and Indexing Library

Provides full-text search capabilities over session documentation using SQLite FTS5.

Part of: IMP-51 — MCP Search Integration for Session History
Created: 2026-04-05

Architecture:
- SessionIndexer: Parses DAILY_ACTIVITIES files, extracts activity blocks, indexes to SQLite FTS5
- SessionSearcher: Queries indexed content, returns ranked results with snippets
- ActivityBlock: Dataclass representing a parsed activity block

Usage:
    # Indexing
    indexer = SessionIndexer(index_path=".session-index/index.db")
    indexer.index_all_sessions("docs/SESSIONS")

    # Searching
    searcher = SessionSearcher(index_path=".session-index/index.db")
    results = searcher.search("validador de semver", limit=10)
    for result in results:
        print(f"{result.date} - {result.title}: {result.snippet}")
"""

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

# ANSI colors
GREEN = "\033[92m"
YELLOW = "\033[93"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


@dataclass
class ActivityBlock:
    """Represents a parsed activity block from DAILY_ACTIVITIES."""

    session_date: str  # YYYY-MM-DD
    timestamp: str  # HH:MM or full datetime
    title: str
    objective: Optional[str] = None
    context: Optional[str] = None
    steps: Optional[str] = None
    result: Optional[str] = None
    decisions: Optional[str] = None
    files: Optional[str] = None
    commits: Optional[str] = None
    observations: Optional[str] = None
    status:Optional[str] = None
    raw_content: Optional[str] = None  # Full block text

    @property
    def searchable_text(self) -> str:
        """Returns all text fields concatenated for indexing."""
        parts = [
            self.title,
            self.objective or "",
            self.context or "",
            self.steps or "",
            self.result or "",
            self.decisions or "",
            self.observations or "",
        ]
        return " ".join(p for p in parts if p).strip()

    @property
    def day_of_week(self) -> str:
        """Returns day of week from session_date."""
        try:
            dt = datetime.strptime(self.session_date, "%Y-%m-%d")
            return dt.strftime("%A")
        except ValueError:
            return "unknown"


@dataclass
class SearchResult:
    """Represents a search result with ranking and snippet."""

    session_date: str
    timestamp: str
    title: str
    snippet: str  # Highlighted snippet showing match context
    rank: float  # BM25 rank score
    file_path: str
    document_type: str  # "sessions", "docs", "specs", "other"

    def __str__(self) -> str:
        type_label = f"[{self.document_type}]" if self.document_type != "sessions" else ""
        return f"{type_label}{self.session_date} {self.timestamp} — {self.title}\n{self.snippet}"


class SessionIndexer:
    """Indexes session documentation into SQLite FTS5 database."""

    # SQLite FTS5 schema
    SCHEMA = """
    CREATE VIRTUAL TABLE IF NOT EXISTS activities USING fts5(
        session_date,
        timestamp,
        title,
        objective,
        context,
        steps,
        result,
        decisions,
        files,
        commits,
        observations,
        status,
        document_type,
        searchable_text,
        file_path,
        tokenize = 'porter unicode61'
    );

    CREATE TABLE IF NOT EXISTS metadata (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """

    def __init__(self, index_path: Path | str):
        """Initialize indexer with database path."""
        self.index_path = Path(index_path)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.index_path))
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        """Create database schema if it doesn't exist."""
        self.conn.executescript(self.SCHEMA)
        self.conn.commit()

    def parse_daily_activities(self, file_path: Path) -> List[ActivityBlock]:
        """Parse DAILY_ACTIVITIES file and extract activity blocks."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"{YELLOW}⚠ Warning:{RESET} Could not read {file_path}: {e}")
            return []

        # Extract session date from filename or path
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', str(file_path))
        session_date = date_match.group(1) if date_match else "unknown"

        # Split by separator (---) to get blocks
        # Handle both formats: canonical (with separators) and legacy (without)
        blocks = []

        if "---\n\n###" in content:
            # Canonical format with separators
            parts = re.split(r'\n---\n\n### ', content)

            for part in parts:
                if not part.strip():
                    continue  # Skip empty parts

                # Skip document-level headers (# or ##), but NOT activity headers (###)
                if part.startswith('# ') or part.startswith('## '):
                    continue

                # Ensure part starts with title (remove leading ---)
                part = part.lstrip('-\n')
                if not part.startswith('###'):
                    part = '### ' + part

                block = self._parse_canonical_block(part, session_date, str(file_path))
                if block:
                    blocks.append(block)
        else:
            # Legacy format - try to extract activities
            # Look for ### headers as activity boundaries (including at start of file)
            activity_pattern = r'(?:^|\n)(### [^\n]+)'
            matches = list(re.finditer(activity_pattern, content, re.MULTILINE))

            for i, match in enumerate(matches):
                start = match.start()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
                block_text = content[start:end]

                block = self._parse_legacy_block(block_text, session_date, str(file_path))
                if block:
                    blocks.append(block)

        return blocks

    def _parse_canonical_block(self, block_text: str, session_date: str, file_path: str) -> Optional[ActivityBlock]:
        """Parse a canonical format activity block."""
        lines = block_text.split('\n')

        # Extract title (first line after ###)
        title_match = re.match(r'###\s+(.+)', lines[0] if lines else "")
        title = title_match.group(1).strip() if title_match else "Untitled Activity"

        # Extract timestamp from first few lines (search for **HH:MM** pattern)
        timestamp = "[time]"
        for line in lines[:5]:  # Check first 5 lines
            timestamp_match = re.search(r'\*\*(\d{1,2}:\d{2})\*\*', line)
            if timestamp_match:
                timestamp = timestamp_match.group(1)
                break

        # Extract fields using patterns
        objective = self._extract_field(block_text, "Objetivo")
        context = self._extract_field(block_text, "Contexto")
        result = self._extract_field(block_text, "Resultado")
        decisions = self._extract_field(block_text, "Decisões técnicas")
        observations = self._extract_field(block_text, "Observações")
        status = self._extract_field(block_text, "Status")

        # Extract multi-line fields
        steps = self._extract_list(block_text, "Passos executados")
        files = self._extract_list(block_text, "Arquivos modificados/criados")
        commits = self._extract_list(block_text, "Commits")

        return ActivityBlock(
            session_date=session_date,
            timestamp=timestamp,
            title=title,
            objective=objective,
            context=context,
            steps=steps,
            result=result,
            decisions=decisions,
            files=files,
            commits=commits,
            observations=observations,
            status=status,
            raw_content=block_text,
        )

    def _parse_legacy_block(self, block_text: str, session_date: str, file_path: str) -> Optional[ActivityBlock]:
        """Parse a legacy format activity block."""
        # Extract title from first line (should be ### Title)
        title_match = re.search(r'###\s+([^\n]+)', block_text)
        title = title_match.group(1).strip() if title_match else "Untitled Activity"

        # Try to extract timestamp
        timestamp = "[legacy]"
        lines = block_text.split('\n')
        for line in lines[:10]:  # Search first 10 lines
            time_match = re.search(r'\b(\d{1,2}:\d{2})\b', line)
            if time_match:
                timestamp = time_match.group(1)
                break

        # For legacy, use entire block as searchable text
        return ActivityBlock(
            session_date=session_date,
            timestamp=timestamp,
            title=title,
            raw_content=block_text,
        )

    def _extract_field(self, text: str, field_name: str) -> Optional[str]:
        """Extract single-line field value."""
        pattern = rf'\*\*{re.escape(field_name)}\*\*:\s*([^\n]+)'
        match = re.search(pattern, text)
        return match.group(1).strip() if match else None

    def _extract_list(self, text: str, header: str) -> Optional[str]:
        """Extract list items under a header."""
        pattern = rf'\*\*{re.escape(header)}\*\*:\s*\n((?:[\d\-\*]\s*[^\n]+\n?)+)'
        match = re.search(pattern, text, re.MULTILINE)
        return match.group(1).strip() if match else None

    def index_file(self, file_path: Path, document_type: str = "sessions") -> int:
        """Index a single DAILY_ACTIVITIES file. Returns number of blocks indexed.

        Args:
            file_path: Path to DAILY_ACTIVITIES file
            document_type: Type of document ("sessions", "docs", "specs", "other")
        """
        blocks = self.parse_daily_activities(file_path)

        for block in blocks:
            self.conn.execute("""
                INSERT INTO activities (
                    session_date, timestamp, title, objective, context,
                    steps, result, decisions, files, commits, observations,
                    status, searchable_text, file_path, document_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                block.session_date, block.timestamp, block.title,
                block.objective, block.context, block.steps,
                block.result, block.decisions, block.files,
                block.commits, block.observations, block.status,
                block.searchable_text, str(file_path), document_type
            ))

        self.conn.commit()
        return len(blocks)

    def index_markdown_document(self, file_path: Path, document_type: str = "docs") -> int:
        """Index a generic markdown document (README, TODO, specs, plans, etc.).

        Args:
            file_path: Path to markdown file
            document_type: Type of document ("docs", "specs", "other")

        Returns:
            Number of sections indexed (1 for whole document or count of ## headers)
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"{YELLOW}⚠ Warning:{RESET} Could not read {file_path}: {e}")
            return 0

        # Extract date from filename or use current date
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', str(file_path))
        doc_date = date_match.group(1) if date_match else datetime.now().strftime("%Y-%m-%d")

        # Parse document by sections (## headers)
        sections = self._split_into_sections(content, file_path.name)

        blocks_indexed = 0
        for section in sections:
            self.conn.execute("""
                INSERT INTO activities (
                    session_date, timestamp, title, objective, context,
                    steps, result, decisions, files, commits, observations,
                    status, searchable_text, file_path, document_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                doc_date,
                "[doc]",
                section["title"],
                None,  # No structured fields for generic docs
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                section["content"],  # Full text goes to searchable_text
                str(file_path),
                document_type
            ))
            blocks_indexed += 1

        self.conn.commit()
        return blocks_indexed

    def _split_into_sections(self, content: str, filename: str) -> List[dict]:
        """Split markdown document into searchable sections by ## headers.

        Returns list of dicts with 'title' and 'content' keys.
        """
        sections = []

        # Split by ## headers (but not ### or #)
        header_pattern = r'\n## ([^\n]+)'
        matches = list(re.finditer(header_pattern, content))

        if not matches:
            # No sections found - index entire document
            # Use first # header or filename as title
            title_match = re.search(r'^#\s+([^\n]+)', content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else filename

            sections.append({
                "title": title,
                "content": content.strip()
            })
        else:
            # Index each section separately
            for i, match in enumerate(matches):
                start = match.start()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
                section_content = content[start:end].strip()
                section_title = match.group(1).strip()

                sections.append({
                    "title": section_title,
                    "content": section_content
                })

        return sections

    def index_all_sessions(self, sessions_dir: Path | str, force_rebuild: bool = False) -> Tuple[int, int]:
        """
        Index all DAILY_ACTIVITIES files in sessions directory.

        Args:
            sessions_dir: Path to docs/SESSIONS directory
            force_rebuild: If True, clear existing index first

        Returns:
            (files_indexed, blocks_indexed)
        """
        sessions_dir = Path(sessions_dir)

        if force_rebuild:
            self.clear_index()

        files_indexed = 0
        blocks_indexed = 0

        # Find all DAILY_ACTIVITIES files
        activity_files = list(sessions_dir.glob("*/DAILY_ACTIVITIES_*.md"))
        activity_files.extend(sessions_dir.glob("*/TODAY_ACTIVITIES_*.md"))  # Legacy support

        print(f"{BLUE}Indexing {len(activity_files)} session activity files...{RESET}")

        for file_path in sorted(activity_files):
            try:
                blocks_count = self.index_file(file_path, document_type="sessions")
                files_indexed += 1
                blocks_indexed += blocks_count
                print(f"{GREEN}✓{RESET} {file_path.parent.name}/{file_path.name} ({blocks_count} blocks)")
            except Exception as e:
                print(f"{RED}✗{RESET} {file_path}: {e}")

        # Update metadata
        self._update_metadata(files_indexed, blocks_indexed)

        print(f"\n{CYAN}Summary:{RESET} {files_indexed} files, {blocks_indexed} blocks indexed")
        return (files_indexed, blocks_indexed)

    def index_docs(self, docs_dir: Path | str = "docs") -> Tuple[int, int]:
        """Index documentation markdown files (README, TODO, guides, etc.).

        Args:
            docs_dir: Path to docs directory (default: "docs")

        Returns:
            (files_indexed, sections_indexed)
        """
        docs_dir = Path(docs_dir)

        files_indexed = 0
        sections_indexed = 0

        # Find markdown files in docs (excluding SESSIONS subdirectory)
        doc_files = []
        for pattern in ["*.md", "*/*.md"]:
            for file_path in docs_dir.glob(pattern):
                # Skip SESSIONS directory (handled by index_all_sessions)
                if "SESSIONS" in file_path.parts:
                    continue
                # Skip templates and debates (can be indexed separately if needed)
                if "templates" in file_path.parts or file_path.name.startswith("."):
                    continue
                doc_files.append(file_path)

        print(f"{BLUE}Indexing {len(doc_files)} documentation files...{RESET}")

        for file_path in sorted(doc_files):
            try:
                sections_count = self.index_markdown_document(file_path, document_type="docs")
                files_indexed += 1
                sections_indexed += sections_count
                print(f"{GREEN}✓{RESET} {file_path.relative_to(docs_dir.parent)} ({sections_count} sections)")
            except Exception as e:
                print(f"{RED}✗{RESET} {file_path}: {e}")

        self._update_metadata(files_indexed, sections_indexed)

        print(f"\n{CYAN}Summary:{RESET} {files_indexed} files, {sections_indexed} sections indexed")
        return (files_indexed, sections_indexed)

    def index_specs(self, specify_dir: Path | str = ".specify") -> Tuple[int, int]:
        """Index SpecKit specification files (spec.md, plan.md, tasks.md).

        Args:
            specify_dir: Path to .specify directory (default: ".specify")

        Returns:
            (files_indexed, sections_indexed)
        """
        specify_dir = Path(specify_dir)

        if not specify_dir.exists():
            print(f"{YELLOW}⚠ Warning:{RESET} .specify directory not found, skipping specs")
            return (0, 0)

        files_indexed = 0
        sections_indexed = 0

        # Find spec files (spec.md, plan.md, tasks.md) in .specify/specs/*/
        spec_files = []
        if (specify_dir / "specs").exists():
            for spec_dir in (specify_dir / "specs").iterdir():
                if spec_dir.is_dir():
                    for md_file in spec_dir.glob("*.md"):
                        if md_file.name in ["spec.md", "plan.md", "tasks.md"]:
                            spec_files.append(md_file)

        print(f"{BLUE}Indexing {len(spec_files)} specification files...{RESET}")

        for file_path in sorted(spec_files):
            try:
                sections_count = self.index_markdown_document(file_path, document_type="specs")
                files_indexed += 1
                sections_indexed += sections_count
                print(f"{GREEN}✓{RESET} {file_path.relative_to(specify_dir.parent)} ({sections_count} sections)")
            except Exception as e:
                print(f"{RED}✗{RESET} {file_path}: {e}")

        self._update_metadata(files_indexed, sections_indexed)

        print(f"\n{CYAN}Summary:{RESET} {files_indexed} files, {sections_indexed} sections indexed")
        return (files_indexed, sections_indexed)

    def index_chats(self, sessions_dir: Path | str = "docs/SESSIONS") -> Tuple[int, int]:
        """Index CHAT-*.md conversation files (IMP-55).

        Args:
            sessions_dir: Path to docs/SESSIONS directory (default: "docs/SESSIONS")

        Returns:
            (files_indexed, messages_indexed)
        """
        sessions_dir = Path(sessions_dir)

        files_indexed = 0
        messages_indexed = 0

        # Find all CHAT-*.md files
        chat_files = list(sessions_dir.glob("*/CHAT-*.md"))

        print(f"{BLUE}Indexing {len(chat_files)} chat conversation files...{RESET}")

        for file_path in sorted(chat_files):
            try:
                sections_count = self.index_markdown_document(file_path, document_type="chats")
                files_indexed += 1
                messages_indexed += sections_count
                print(f"{GREEN}✓{RESET} {file_path.parent.name}/{file_path.name} ({sections_count} messages)")
            except Exception as e:
                print(f"{RED}✗{RESET} {file_path}: {e}")

        self._update_metadata(files_indexed, messages_indexed)

        print(f"\n{CYAN}Summary:{RESET} {files_indexed} files, {messages_indexed} messages indexed")
        return (files_indexed, messages_indexed)

    def index_by_scope(self, scope: str = "all", force_rebuild: bool = False) -> Tuple[int, int]:
        """Index documents by scope.

        Args:
            scope: One of "sessions", "docs", "specs", "chats", "all"
            force_rebuild: If True, clear existing index first

        Returns:
            (total_files_indexed, total_blocks_indexed)
        """
        if force_rebuild:
            self.clear_index()

        total_files = 0
        total_blocks = 0

        if scope in ["sessions", "all"]:
            files, blocks = self.index_all_sessions("docs/SESSIONS", force_rebuild=False)
            total_files += files
            total_blocks += blocks

        if scope in ["docs", "all"]:
            files, blocks = self.index_docs("docs")
            total_files += files
            total_blocks += blocks

        if scope in ["specs", "all"]:
            files, blocks = self.index_specs(".specify")
            total_files += files
            total_blocks += blocks

        if scope in ["chats", "all"]:
            files, blocks = self.index_chats("docs/SESSIONS")
            total_files += files
            total_blocks += blocks

        if scope == "all":
            print(f"\n{BOLD}{CYAN}Grand Total:{RESET} {total_files} files, {total_blocks} blocks/sections indexed")

        return (total_files, total_blocks)

    def _update_metadata(self, files_count: int, blocks_count: int):
        """Update metadata with indexing statistics."""
        self.conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES ('last_indexed', ?)",
            (datetime.now().isoformat(),)
        )
        # Increment cumulative counts (for statistics display)
        cursor = self.conn.execute("SELECT value FROM metadata WHERE key = 'total_files'")
        row = cursor.fetchone()
        total_files = int(row[0]) if row else 0
        total_files += files_count

        cursor = self.conn.execute("SELECT value FROM metadata WHERE key = 'total_blocks'")
        row = cursor.fetchone()
        total_blocks = int(row[0]) if row else 0
        total_blocks += blocks_count

        self.conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES ('total_files', ?)",
            (str(total_files),)
        )
        self.conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES ('total_blocks', ?)",
            (str(total_blocks),)
        )
        self.conn.commit()

    def clear_index(self):
        """Clear all indexed data and recreate schema."""
        # Drop tables if they exist
        self.conn.execute("DROP TABLE IF EXISTS activities")
        self.conn.execute("DROP TABLE IF EXISTS metadata")
        self.conn.commit()

        # Recreate schema
        self._init_db()

    def get_stats(self) -> dict:
        """Get index statistics."""
        cursor = self.conn.execute("SELECT COUNT(*) FROM activities")
        total_blocks = cursor.fetchone()[0]

        cursor = self.conn.execute("SELECT value FROM metadata WHERE key = 'last_indexed'")
        row = cursor.fetchone()
        last_indexed = row[0] if row else "never"

        cursor = self.conn.execute("SELECT COUNT(DISTINCT session_date) FROM activities")
        total_sessions = cursor.fetchone()[0]

        return {
            "total_blocks": total_blocks,
            "total_sessions": total_sessions,
            "last_indexed": last_indexed,
        }

    def close(self):
        """Close database connection."""
        self.conn.close()


class SessionSearcher:
    """Searches indexed session documentation using FTS5."""

    def __init__(self, index_path: Path | str):
        """Initialize searcher with database path."""
        self.index_path = Path(index_path)

        if not self.index_path.exists():
            raise FileNotFoundError(
                f"Index database not found: {self.index_path}\n"
                f"Run 'python scripts/session-index.py' first to build the index."
            )

        self.conn = sqlite3.connect(str(self.index_path))
        self.conn.row_factory = sqlite3.Row

    def search(
        self,
        query: str,
        limit: int = 20,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        scope: Optional[str] = None,
    ) -> List[SearchResult]:
        """
        Search indexed activities using FTS5 query syntax.

        Args:
            query: FTS5 query string (supports AND, OR, NOT, NEAR, phrase search)
            limit: Maximum number of results to return
            date_from: Filter by start date (YYYY-MM-DD)
            date_to: Filter by end date (YYYY-MM-DD)
            scope: Filter by document type ("sessions", "docs", "specs", or None for all)

        Returns:
            List of SearchResult objects ranked by relevance

        Examples:
            searcher.search("validador semver")
            searcher.search('"bug fix" AND python')
            searcher.search("IMP-47", date_from="2026-03-01", scope="sessions")
            searcher.search("architecture", scope="specs")
        """
        # Build SQL query
        sql = """
            SELECT
                session_date,
                timestamp,
                title,
                snippet(activities, 12, '<mark>', '</mark>', '…', 64) as snippet,
                rank,
                file_path,
                document_type
            FROM activities
            WHERE activities MATCH ?
        """

        params = [query]

        # Add date filters
        if date_from:
            sql += " AND session_date >= ?"
            params.append(date_from)

        if date_to:
            sql += " AND session_date <= ?"
            params.append(date_to)

        # Add scope filter
        if scope and scope != "all":
            sql += " AND document_type = ?"
            params.append(scope)

        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)

        try:
            cursor = self.conn.execute(sql, params)
            results = []

            for row in cursor.fetchall():
                results.append(SearchResult(
                    session_date=row["session_date"],
                    timestamp=row["timestamp"],
                    title=row["title"],
                    snippet=row["snippet"],
                    rank=row["rank"],
                    file_path=row["file_path"],
                    document_type=row["document_type"],
                ))

            return results

        except sqlite3.OperationalError as e:
            raise ValueError(f"Invalid FTS5 query: {e}")

    def get_activity_context(self, session_date: str, title: str) -> Optional[str]:
        """Retrieve full activity block content by session date and title."""
        cursor = self.conn.execute(
            """
            SELECT
                session_date, timestamp, title, objective, context,
                steps, result, decisions, files, commits, observations, status
            FROM activities
            WHERE session_date = ? AND title = ?
            LIMIT 1
            """,
            (session_date, title)
        )

        row = cursor.fetchone()
        if not row:
            return None

        # Reconstruct activity block
        parts = [
            f"### {row['title']}",
            f"\n**{row['timestamp']}**\n",
        ]

        if row["objective"]:
            parts.append(f"**Objetivo**: {row['objective']}\n")
        if row["context"]:
            parts.append(f"**Contexto**: {row['context']}\n")
        if row["steps"]:
            parts.append(f"**Passos executados**:\n{row['steps']}\n")
        if row["result"]:
            parts.append(f"**Resultado**: {row['result']}\n")
        if row["decisions"]:
            parts.append(f"**Decisões técnicas**: {row['decisions']}\n")
        if row["files"]:
            parts.append(f"**Arquivos modificados/criados**:\n{row['files']}\n")
        if row["commits"]:
            parts.append(f"**Commits**:\n{row['commits']}\n")
        if row["status"]:
            parts.append(f"**Status**: {row['status']}\n")

        return "".join(parts)

    def close(self):
        """Close database connection."""
        self.conn.close()
