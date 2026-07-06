# Backend Availability for Web Extraction

## Extraction Backends

| Backend | Can extract full page content? | Use case |
|---------|--------------------------------|------------|
| **Firecrawl** | ✅ Yes | Full-page HTML → markdown conversion, dynamic content handling |
| **Tavily** | ✅ Yes | Research-focused extraction with summarization |
| **Exa** | ✅ Yes | Structured extraction with metadata |
| **Parallel** | ✅ Yes | Multi-source concurrent extraction |
| **Brave Search (Free)** | ❌ No | Search-only; can find URLs but cannot extract page content |

## Decision Tree

```
web_extract() called
├── Backend supports extraction? → Return content
└── Backend is search-only (e.g., Brave Search Free)
    ├── Fallback to browser_navigate()
    ├── Inspect with browser_snapshot()
    └── Interact if needed (browser_click, browser_scroll)
```

## Practical Notes

- If you see the error "search-only backend cannot extract URL content", do NOT retry `web_extract`. Switch immediately to browser tools.
- Some backends have size limits (e.g., 2M chars per page). For very large pages, use `browser_snapshot(full=true)`.
- When backend configuration changes (e.g., switching from Brave to Firecrawl), update your `web.extract_backend` setting.
