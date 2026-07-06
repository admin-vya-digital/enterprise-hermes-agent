#!/usr/bin/env python3
"""
Create .memory directory structure for IMP-59 mini-Engram Python.

Usage:
    python scripts/create_memory_structure.py
"""

import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
MEMORY_ROOT = PROJECT_ROOT / ".memory"

# Directory structure
DIRECTORIES = [
    MEMORY_ROOT / "memories" / "project",
    MEMORY_ROOT / "memories" / "team",
    MEMORY_ROOT / "memories" / "sessions",
    MEMORY_ROOT / "memories" / ".templates",
    MEMORY_ROOT / "index",
]

# Files to create
FILES = {
    MEMORY_ROOT / "index" / ".gitignore": "# Ignore SQLite index files\n*.db\n*.db-*\n",
    MEMORY_ROOT / "memories" / ".templates" / "example_decision.md": """---
title: Example Architectural Decision
category: project
tags: architecture, example
date: 2026-04-20
---

# Decision: [Title Here]

## Context
Why was this decision needed?

## Decision
What was decided?

## Rationale
Why this choice over alternatives?

## Consequences
What are the implications?
""",
}


def create_structure():
    """Create .memory directory structure."""
    log.info("Creating .memory structure at %s", MEMORY_ROOT)

    # Create directories
    for directory in DIRECTORIES:
        directory.mkdir(parents=True, exist_ok=True)
        log.info("✅ %s", directory.relative_to(PROJECT_ROOT))

    # Create files
    for file_path, content in FILES.items():
        file_path.write_text(content)
        log.info("✅ %s", file_path.relative_to(PROJECT_ROOT))

    log.info("✅ .memory structure created successfully")


if __name__ == "__main__":
    create_structure()
