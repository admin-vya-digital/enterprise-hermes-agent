---
name: web-content-extraction
level: class
title: Web Content Extraction
area: research
description: Standardized workflow for retrieving and summarizing web content with fallback between direct extraction and browser-based approaches.
tags: [scraping, web, extraction, browser, research]
---

# Web Content Extraction

A standardized approach to retrieving and summarizing web content for research, analysis, or documentation. Handles both static pages and dynamic sites with a fallback strategy when direct extraction isn't possible.

## When to Use

- Extracting articles, blog posts, documentation, or reference pages
- Needing structured summaries of web content
- Encountering pages that may require interaction (clicks, logins, scrolling)
- Backend limitations prevent direct extraction

## Workflow

### 1. Try Direct Extraction First

Attempt `web_extract(urls=[...])` as the primary method. It's faster, cheaper, and preserves formatting.

**Success**: Content returned → proceed to summarization.

**Failure with backend limitation** (e.g., "search-only backend cannot extract URL content") → proceed to Step 2.

**Failure with timeout/network error** → try browser-based approach (Step 2) or retry with alternative URL.

### 2. Fallback to Browser Navigation

If direct extraction fails due to backend constraints:

1. Call `browser_navigate(url=...)` to load the page
2. Inspect the snapshot for content structure and interactive elements
3. If needed, interact (click buttons, scroll, type) using browser tools
4. Extract content from the snapshot or via `browser_console(expression=...)` for structured data

### 3. Summarize and Structure

Present extracted content clearly:

- Article title, author, publish date
- Key sections with concise bullet summaries
- Code blocks verbatim when technically relevant
- Links to referenced tools/resources

### 4. Advanced Cases

For pages requiring login, CAPTCHA, or heavy JS:

- Use `browser_vision` for visual inspection
- For programmatic scraping, use Python scripts (requests + BeautifulSoup) via `execute_code`

## Pitfalls

⚠️ **Never fabricate content.** If extraction fails, report the blocker honestly.

⚠️ **Backend ≠ tool failure.** A "search-only" backend means direct extraction isn't supported — switch to browser tools rather than retrying `web_extract`.

⚠️ **Lazy-loaded content.** Some pages load more content on scroll. Use `browser_scroll` if the snapshot seems incomplete.

⚠️ **Respect site policies.** Avoid aggressive scraping; research use only.

## Verification

- Cross-check extracted content against the original page
- Verify technical snippets in a safe environment before reporting
- Use `browser_snapshot(full=true)` for complete content when needed

## See Also

- `references/backend-availability.md`: Backend capabilities and when to use each
- `references/browser-interaction-patterns.md`: Common navigation/interaction sequences
