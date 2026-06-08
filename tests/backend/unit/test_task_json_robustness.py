"""Robustness of task-JSON extraction — the path that, when it fails, drops the
learner to useless template tasks. Covers the two real-world failure modes from a
free reasoning model: raw newlines inside string values, and truncation mid-array."""
import json

import pytest

from app.services.llm_utils import extract_json
from app.services.practice_generation import _salvage_tasks_json


def test_extract_json_accepts_raw_newlines_in_strings():
    # Model writes multi-line instructions_md WITHOUT escaping every \n. Strict JSON
    # rejects this; the lenient decoder must accept it.
    raw = '{"theory_task": {"instructions_md": "### Q1\nline two\n```kotlin\nval x = 1\n```"}}'
    out = extract_json(raw)
    assert "line two" in out["theory_task"]["instructions_md"]


def test_extract_json_ignores_fence_wrapper_and_preamble():
    raw = 'Sure!\n```json\n{"practice_tasks": [{"title": "A"}]}\n```'
    out = extract_json(raw)
    assert out["practice_tasks"][0]["title"] == "A"


def test_extract_json_respects_braces_inside_code_strings():
    raw = '{"x": {"code": "class A { val y = 1 }"}, "after": true}'
    out = extract_json(raw)
    assert out["after"] is True
    assert out["x"]["code"] == "class A { val y = 1 }"


def test_salvage_recovers_theory_and_complete_tasks_from_truncation():
    truncated = (
        '{"learning_goals": ["g1"],'
        '"theory_task": {"title": "T", "instructions_md": "q"},'
        '"practice_tasks": ['
        '{"title": "Task 1", "difficulty": 1, "instructions_md": "one"},'
        '{"title": "Task 2", "difficulty": 2, "instructions_md": "two"},'
        '{"title": "Task 3", "difficulty": 3, "instructions_md": "INCOMPLE'  # cut off
    )
    # Whole-object parse must fail...
    with pytest.raises(Exception):
        extract_json(truncated)
    # ...but salvage recovers everything before the cut.
    out = _salvage_tasks_json(truncated)
    assert out["theory_task"]["title"] == "T"
    assert out["learning_goals"] == ["g1"]
    assert [t["title"] for t in out["practice_tasks"]] == ["Task 1", "Task 2"]


def test_salvage_returns_empty_on_garbage():
    assert _salvage_tasks_json("not json at all") == {}
