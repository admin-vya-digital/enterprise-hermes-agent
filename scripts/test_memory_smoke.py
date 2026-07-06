#!/usr/bin/env python3
"""Smoke test for memory system (IMP-59 Phase 1).

Tests:
1. Create memory
2. Save to database and file
3. Search
4. Rebuild index

Usage:
    python scripts/test_memory_smoke.py
"""

import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.lib.memory import Memory, MemoryStore

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def test_save():
    """Test saving a memory."""
    log.info("Test 1: Save memory")

    store = MemoryStore()

    memory = Memory(
        title="Test Memory — API Authentication",
        content="""# API Authentication Pattern

## Decision
Use JWT tokens with 1h expiration for API authentication.

## Rationale
- Stateless (no server-side session storage)
- Short expiration minimizes risk
- Refresh tokens allow seamless renewal

## Implementation
JWT tokens stored in Authorization header.
Refresh tokens in httpOnly cookies.
""",
        category="project",
        tags=["test", "api", "authentication", "jwt"],
    )

    memory_id = store.save(memory)
    log.info("✅ Memory saved with ID: %d", memory_id)
    log.info("   File: %s", memory.file_path)

    # Verify file exists
    if not memory.file_path.exists():
        log.error("❌ FAILED: Memory file not created")
        return False

    log.info("✅ Memory file created successfully")
    store.close()
    return True


def test_search():
    """Test searching memories."""
    log.info("\nTest 2: Search memories")

    store = MemoryStore()

    # Search for "JWT"
    results = store.search("JWT authentication")

    if not results:
        log.error("❌ FAILED: No results found for 'JWT authentication'")
        return False

    log.info("✅ Found %d results", len(results))

    for i, result in enumerate(results, 1):
        log.info("   %d. %s (score: %.2f)", i, result.title, result.score)
        log.info("      Category: %s | Tags: %s", result.category, ", ".join(result.tags))
        log.info("      Snippet: %s", result.snippet[:80])

    store.close()
    return True


def test_stats():
    """Test statistics."""
    log.info("\nTest 3: Statistics")

    store = MemoryStore()
    stats = store.get_stats()

    log.info("✅ Statistics:")
    for key, value in stats.items():
        log.info("   %s: %d", key, value)

    store.close()
    return True


def test_rebuild():
    """Test index rebuild."""
    log.info("\nTest 4: Rebuild index")

    store = MemoryStore()
    count = store.rebuild_index()

    log.info("✅ Index rebuilt: %d memories", count)

    store.close()
    return True


def main():
    """Run all smoke tests."""
    log.info("=" * 60)
    log.info("Memory System Smoke Test (IMP-59 Phase 1)")
    log.info("=" * 60)

    tests = [
        ("Save memory", test_save),
        ("Search memories", test_search),
        ("Statistics", test_stats),
        ("Rebuild index", test_rebuild),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            log.error("❌ Test '%s' failed with exception: %s", name, e)
            import traceback
            traceback.print_exc()
            failed += 1

    log.info("\n" + "=" * 60)
    log.info("Summary: %d passed, %d failed", passed, failed)
    log.info("=" * 60)

    if failed > 0:
        log.error("❌ SMOKE TEST FAILED")
        return 1
    else:
        log.info("✅ SMOKE TEST PASSED")
        return 0


if __name__ == "__main__":
    sys.exit(main())
