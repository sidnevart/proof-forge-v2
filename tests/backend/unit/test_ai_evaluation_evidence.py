"""Regression tests for AI evaluation building the user content from IDE evidence.

HIGH-2: evaluate_submission_ai previously passed only submission.reflection to the
LLM, so IDE-plugin submissions (which carry their work in files/diff/test_output/
exit_code and create no attachments) were graded against an empty answer.
"""
from types import SimpleNamespace

from app.services import ai_evaluation as ae


def _task():
    return SimpleNamespace(
        title="Implement quicksort",
        instructions_md="Write quicksort and test it.",
        target_concepts=["quicksort", "recursion"],
        expected_evidence=["test_output"],
    )


def _submission(**overrides):
    base = dict(
        reflection="",
        check_command="pytest -q",
        exit_code=0,
        test_output="3 passed in 0.1s",
        diff="--- a/sort.py\n+++ b/sort.py\n+def quicksort(xs): ...",
        files=[{"path": "sort.py", "content": "def quicksort(xs): return xs"}],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_build_user_content_includes_ide_evidence():
    content, has_images = ae._build_user_content(_task(), _submission(), attachments=[])
    assert has_images is False
    assert isinstance(content, str)
    # All IDE evidence fields must reach the model.
    assert "pytest -q" in content
    assert "Exit code:** 0" in content
    assert "3 passed in 0.1s" in content
    assert "def quicksort" in content
    assert "sort.py" in content
    # Not the empty-answer placeholder.
    assert "(текст не указан)" not in content


def test_build_user_content_includes_reflection_and_evidence_together():
    sub = _submission(reflection="I used Lomuto partition.")
    content, _ = ae._build_user_content(_task(), sub, attachments=[])
    assert "Lomuto partition" in content
    assert "3 passed in 0.1s" in content


def test_build_user_content_empty_submission_is_placeholder():
    sub = SimpleNamespace(
        reflection="", check_command="", exit_code=None,
        test_output="", diff="", files=[],
    )
    content, _ = ae._build_user_content(_task(), sub, attachments=[])
    assert "(текст не указан)" in content


def test_build_user_content_image_attachment_triggers_vision_list():
    img = SimpleNamespace(
        kind="image", data_b64="AAAA", mime_type="image/png",
        name="shot.png", content_text="",
    )
    content, has_images = ae._build_user_content(_task(), _submission(), attachments=[img])
    assert has_images is True
    assert isinstance(content, list)
    assert any(p.get("type") == "image_url" for p in content)
    # The text part still carries the IDE evidence.
    text_part = next(p["text"] for p in content if p.get("type") == "text")
    assert "3 passed in 0.1s" in text_part
