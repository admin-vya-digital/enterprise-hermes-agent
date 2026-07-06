"""
knowledge.py — extração de texto e gestão da base de conhecimento.
Suporta PDF, DOCX, Markdown e URL.
"""

import re
import urllib.request
from pathlib import Path


def extract_text(source: str | bytes, filename: str) -> str:
    """
    Extrai texto de um arquivo (PDF, DOCX, MD, TXT) ou URL.
    source: bytes do arquivo ou str de URL.
    """
    ext = Path(filename).suffix.lower()

    if isinstance(source, str) and source.startswith(("http://", "https://")):
        return _extract_url(source)

    if ext == ".pdf":
        return _extract_pdf(source)
    elif ext in (".docx", ".doc"):
        return _extract_docx(source)
    else:
        if isinstance(source, bytes):
            return source.decode("utf-8", errors="replace")
        return source


def _extract_pdf(data: bytes) -> str:
    try:
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n\n".join(pages)
    except ImportError:
        raise RuntimeError("pypdf não instalado. Execute: pip install pypdf")


def _extract_docx(data: bytes) -> str:
    try:
        import io
        from docx import Document
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        raise RuntimeError("python-docx não instalado. Execute: pip install python-docx")


def _extract_url(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read()
        if "text/html" in content_type:
            return _strip_html(raw.decode("utf-8", errors="replace"))
        return raw.decode("utf-8", errors="replace")
    except Exception as e:
        raise RuntimeError(f"Erro ao buscar URL: {e}")


def _strip_html(html: str) -> str:
    html = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", "", html,
                  flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<[^>]+>", " ", html)
    html = re.sub(r"\s{3,}", "\n\n", html)
    return html.strip()


def save_knowledge(d: Path, filename: str, content: str) -> Path:
    """Salva o texto extraído em profiles/<id>/knowledge/<filename>.md"""
    kdir = d / "knowledge"
    kdir.mkdir(parents=True, exist_ok=True)
    stem = Path(filename).stem
    dest = kdir / f"{stem}.md"
    dest.write_text(content, encoding="utf-8")
    return dest
