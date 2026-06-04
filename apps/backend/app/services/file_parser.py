"""Extract plain text from uploaded files and URLs."""
import io

import httpx

MAX_CHARS = 50_000
_TRUNCATION_NOTE = "\n\n[... контент обрезан до 50 000 символов ...]"

TEXT_EXTENSIONS = {".md", ".py", ".java", ".csv", ".txt", ".js", ".ts", ".go",
                   ".rs", ".c", ".cpp", ".h", ".json", ".yaml", ".yml", ".toml",
                   ".sh", ".sql", ".html", ".xml", ".rb", ".php", ".kt"}


def _truncate(text: str) -> str:
    if len(text) <= MAX_CHARS:
        return text
    return text[:MAX_CHARS] + _TRUNCATION_NOTE


def extract_from_bytes(filename: str, data: bytes) -> str:
    """Extract text from file bytes based on extension."""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == ".pdf":
        return _extract_pdf(data)

    # All other types — treat as UTF-8 text
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:
        text = data.decode("latin-1", errors="replace")
    return _truncate(text)


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
        reader = PdfReader(io.BytesIO(data))
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text)
        return _truncate("\n\n".join(pages))
    except ImportError:
        return "[PDF parsing requires pypdf — установи зависимость]"
    except Exception as e:
        return f"[Не удалось прочитать PDF: {e}]"


async def extract_from_url(url: str) -> tuple[str, str]:
    """Fetch URL and extract text. Returns (title, content_text)."""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; Grasp/1.0)"},
            )
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")

            if "text/html" in content_type:
                return _parse_html(resp.text, url)
            else:
                # Plain text / markdown / code
                return url, _truncate(resp.text)
    except Exception as e:
        return url, f"[Не удалось загрузить ссылку: {e}]"


def _parse_html(html: str, url: str) -> tuple[str, str]:
    try:
        from bs4 import BeautifulSoup  # type: ignore
        soup = BeautifulSoup(html, "html.parser")

        # Extract title
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else url

        # Remove noise
        for tag in soup(["script", "style", "nav", "footer", "header",
                         "aside", "ads", "noscript", "iframe"]):
            tag.decompose()

        # Prefer main content
        main = (soup.find("article") or soup.find("main")
                or soup.find(id="content") or soup.find(class_="content")
                or soup.find("body") or soup)

        text = main.get_text(separator="\n", strip=True)
        # Collapse blank lines
        lines = [l for l in text.splitlines() if l.strip()]
        return title, _truncate("\n".join(lines))
    except ImportError:
        # fallback: strip all tags
        import re
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return url, _truncate(text)
