"""Extract plain text from uploaded files and URLs."""
import io

import httpx

MAX_CHARS = 200_000
_TRUNCATION_NOTE = "\n\n[... контент обрезан до 200 000 символов ...]"

# Stop downloading a URL after this many bytes — a page bigger than this is almost
# never useful as a single learning material and risks loading the whole thing into
# memory before we truncate.
MAX_DOWNLOAD_BYTES = 5_000_000
# Below this many extracted chars we assume the page was JS-rendered (SPA) and the
# fetch returned an empty shell.
_MIN_USEFUL_CHARS = 200

TEXT_EXTENSIONS = {".md", ".py", ".java", ".csv", ".txt", ".js", ".ts", ".go",
                   ".rs", ".c", ".cpp", ".h", ".json", ".yaml", ".yml", ".toml",
                   ".sh", ".sql", ".html", ".xml", ".rb", ".php", ".kt"}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_IMAGE_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def _ext(filename: str) -> str:
    return "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def is_image(filename: str) -> bool:
    """True if the filename's extension is a supported image type."""
    return _ext(filename) in IMAGE_EXTENSIONS


def image_mime(filename: str) -> str:
    """Best-effort MIME type for an image filename."""
    return _IMAGE_MIME.get(_ext(filename), "image/png")


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


async def _download_capped(client: httpx.AsyncClient, url: str) -> tuple[bytes, str]:
    """Stream a URL, stopping after MAX_DOWNLOAD_BYTES. Returns (body, content_type)."""
    async with client.stream(
        "GET", url, headers={"User-Agent": "Mozilla/5.0 (compatible; Grasp/1.0)"}
    ) as resp:
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        chunks: list[bytes] = []
        size = 0
        async for chunk in resp.aiter_bytes():
            chunks.append(chunk)
            size += len(chunk)
            if size > MAX_DOWNLOAD_BYTES:
                break
        return b"".join(chunks)[:MAX_DOWNLOAD_BYTES], content_type


async def extract_from_url(url: str) -> tuple[str, str]:
    """Fetch URL and extract text. Returns (title, content_text)."""
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            body, content_type = await _download_capped(client, url)
        ctype = content_type.lower()

        if "application/pdf" in ctype or url.lower().endswith(".pdf"):
            return url, _extract_pdf(body)

        # Decode text once for the remaining text-like types.
        text = body.decode("utf-8", errors="replace")

        if "text/html" in ctype or (not ctype and "<html" in text[:2000].lower()):
            title, content = _parse_html(text, url)
            if len(content.strip()) < _MIN_USEFUL_CHARS:
                return title, (
                    "[Страница почти пустая — вероятно, контент подгружается через "
                    "JavaScript (SPA). Скопируй текст вручную или загрузи файлом.]"
                )
            return title, content

        if (
            ctype.startswith("text/")
            or "json" in ctype
            or "xml" in ctype
            or "markdown" in ctype
            or not ctype
        ):
            return url, _truncate(text)

        return url, f"[Неподдерживаемый тип содержимого: {content_type or 'неизвестно'}]"
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
