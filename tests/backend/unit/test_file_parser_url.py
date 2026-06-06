import httpx
import pytest

from app.services import file_parser as fp


class _FakeStreamResponse:
    def __init__(self, *, content_type: str, body: bytes, status: int = 200):
        self.headers = {"content-type": content_type}
        self._body = body
        self._status = status

    def raise_for_status(self):
        if self._status >= 400:
            raise httpx.HTTPStatusError(
                "err", request=httpx.Request("GET", "http://x"),
                response=httpx.Response(self._status),
            )

    async def aiter_bytes(self, chunk_size: int = 65536):
        # Yield in small pieces so the size cap logic is exercised.
        step = 4096
        for i in range(0, len(self._body), step):
            yield self._body[i:i + step]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeClient:
    def __init__(self, response: _FakeStreamResponse):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def stream(self, method, url, headers=None):
        return self._response


def _patch_client(monkeypatch, response: _FakeStreamResponse):
    monkeypatch.setattr(
        fp.httpx, "AsyncClient", lambda *a, **k: _FakeClient(response)
    )


async def test_extract_from_url_parses_html(monkeypatch):
    # Article body must exceed _MIN_USEFUL_CHARS or it's treated as an empty SPA shell.
    article = ("Real article content. " * 30).encode()
    html = b"<html><head><title>My Page</title></head><body><article>" \
           + article + b"</article></body></html>"
    _patch_client(monkeypatch, _FakeStreamResponse(content_type="text/html", body=html))

    title, content = await fp.extract_from_url("http://example.com")
    assert title == "My Page"
    assert "Real article content" in content


async def test_extract_from_url_empty_spa_returns_hint(monkeypatch):
    html = b"<html><head><title>App</title></head><body><div id='root'></div></body></html>"
    _patch_client(monkeypatch, _FakeStreamResponse(content_type="text/html", body=html))

    title, content = await fp.extract_from_url("http://spa.example.com")
    assert title == "App"
    assert "JavaScript" in content or "SPA" in content


async def test_extract_from_url_plain_text(monkeypatch):
    body = b"# Markdown\n\nsome notes"
    _patch_client(monkeypatch, _FakeStreamResponse(content_type="text/markdown", body=body))

    title, content = await fp.extract_from_url("http://example.com/readme.md")
    assert "Markdown" in content


async def test_extract_from_url_unsupported_type(monkeypatch):
    _patch_client(
        monkeypatch,
        _FakeStreamResponse(content_type="application/octet-stream", body=b"\x00\x01\x02"),
    )
    title, content = await fp.extract_from_url("http://example.com/blob")
    assert "Неподдерживаемый тип" in content


async def test_extract_from_url_oversized_is_capped(monkeypatch):
    # Body larger than the download cap — must not blow up, just truncate.
    big = b"a" * (fp.MAX_DOWNLOAD_BYTES + 100_000)
    _patch_client(monkeypatch, _FakeStreamResponse(content_type="text/plain", body=big))

    title, content = await fp.extract_from_url("http://example.com/big.txt")
    # Stored content is bounded by MAX_CHARS, and download stopped at the byte cap.
    assert len(content) <= fp.MAX_CHARS + len(fp._TRUNCATION_NOTE)


async def test_extract_from_url_network_error_is_graceful(monkeypatch):
    class _BoomClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def stream(self, *a, **k):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(fp.httpx, "AsyncClient", lambda *a, **k: _BoomClient())
    title, content = await fp.extract_from_url("http://unreachable.example.com")
    assert "Не удалось загрузить" in content
