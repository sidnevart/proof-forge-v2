import pytest

from app.services import content_reduction as cr


def test_split_chunks_small_text_single_chunk():
    text = "short"
    assert cr.split_chunks(text, 100) == ["short"]


def test_split_chunks_respects_size_and_covers_all_text():
    text = "\n\n".join(f"paragraph {i} " + "x" * 200 for i in range(20))
    chunks = cr.split_chunks(text, 500)
    assert len(chunks) > 1
    assert all(len(c) <= 500 for c in chunks)
    # No content is lost (modulo whitespace stripping at boundaries)
    assert "paragraph 0" in chunks[0]
    assert "paragraph 19" in chunks[-1]


def test_plan_chunks_under_cap_keeps_all():
    materials = [("mat", "\n\n".join("y" * 100 for _ in range(3)))]
    planned, dropped = cr.plan_chunks(materials, chunk_size=120, max_chunks=16)
    assert dropped == 0
    assert all(name == "mat" for name, _ in planned)


def test_plan_chunks_over_cap_samples_and_reports_dropped():
    # One big material that splits into far more than the cap.
    big = "\n\n".join(f"para{i} " + "z" * 200 for i in range(100))
    planned, dropped = cr.plan_chunks([("big", big)], chunk_size=250, max_chunks=8)
    assert len(planned) == 8
    assert dropped > 0
    # Sampling is spread across the corpus, not just the front.
    assert planned[0][1] != planned[-1][1]


def test_plan_chunks_skips_empty_chunks():
    materials = [("a", "   "), ("b", "real content here")]
    planned, dropped = cr.plan_chunks(materials, chunk_size=100, max_chunks=16)
    assert dropped == 0
    assert [name for name, _ in planned] == ["b"]


async def test_map_reduce_digest_caps_calls_and_notes_drop(monkeypatch):
    calls = {"n": 0}

    async def fake_call(client, settings, prompt, max_tokens=800):
        calls["n"] += 1
        return f"concept-{calls['n']}"

    monkeypatch.setattr(cr, "_digest_llm_call", fake_call)

    big = "\n\n".join(f"para{i} " + "q" * 300 for i in range(200))
    digest = await cr.map_reduce_digest(
        client=None,
        settings=object(),
        topic_name="T",
        materials=[("big", big)],
        chunk_size=350,
        max_chunks=5,
    )

    # Never exceeds the cap, regardless of how large the input is.
    assert calls["n"] == 5
    assert "concept-1" in digest
    # Drop note is appended when chunks were sampled out.
    assert "пропущено" in digest


async def test_map_reduce_digest_reports_progress(monkeypatch):
    async def fake_call(client, settings, prompt, max_tokens=800):
        return "c"

    monkeypatch.setattr(cr, "_digest_llm_call", fake_call)

    seen: list[tuple[int, int]] = []

    async def progress(current, total):
        seen.append((current, total))

    await cr.map_reduce_digest(
        client=None,
        settings=object(),
        topic_name="T",
        materials=[("m", "a\n\nb\n\nc")],
        chunk_size=2,
        max_chunks=16,
        progress=progress,
    )
    assert seen  # progress callback fired
    assert seen[0][0] == 1
    assert all(total == seen[0][1] for _, total in seen)
