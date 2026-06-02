#!/usr/bin/env python3
"""
Eval runner for Proof-Forge agent skills.
Uses Ollama (OpenAI-compatible API) to simulate an agent session with MCP tools.
No ANTHROPIC_API_KEY needed. Backend is not required — tool calls use mock responses.

Usage:
    python tests/evals/run_evals.py
    python tests/evals/run_evals.py --scenario scenario_start_topic

Environment:
    OLLAMA_BASE_URL  — default: http://localhost:11434/v1
    OLLAMA_API_KEY   — required only for cloud-hosted models (e.g. glm-5:cloud)
    OLLAMA_MODEL     — default: glm-5:cloud
"""
import argparse
import json
import os
import sys
from pathlib import Path

from openai import OpenAI

SCENARIOS_DIR = Path(__file__).parent / "scenarios"
PROMPTS_DIR = Path(__file__).parent.parent.parent / "packages" / "agent-prompts"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY", "ollama")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "glm-5:cloud")

MOCK_TOOL_RESULTS = {
    "create_user": {"id": "user-eval-001", "email": "eval@example.com", "display_name": "Eval"},
    "get_profile": {"id": "prof-001", "user_id": "user-eval-001", "known_topics": [], "weak_spots": [], "skill_level": "beginner", "updated_at": "2026-06-02T00:00:00Z"},
    "start_topic": {"id": "topic-eval-001", "user_id": "user-eval-001", "name": "Test Topic", "status": "active", "started_at": "2026-06-02T00:00:00Z"},
    "log_event": {"id": "event-eval-001", "user_id": "user-eval-001", "event_type": "note_added", "payload": {}, "occurred_at": "2026-06-02T00:00:00Z"},
    "store_code_artifact": {"id": "event-eval-002", "user_id": "user-eval-001", "event_type": "code_artifact", "payload": {}, "occurred_at": "2026-06-02T00:00:00Z"},
    "store_capsule": {"id": "cap-eval-001", "user_id": "user-eval-001", "topic_id": "topic-eval-001", "content_md": "...", "content_html": "<p>...</p>", "summary": "...", "created_at": "2026-06-02T00:00:00Z", "review_questions": []},
    "get_capsule": {"id": "cap-eval-001", "user_id": "user-eval-001", "topic_id": "topic-eval-001", "content_md": "## Summary\nTest", "content_html": "<h2>Summary</h2><p>Test</p>", "summary": "Test", "created_at": "2026-06-02T00:00:00Z", "review_questions": []},
    "store_review_answer": {"id": "att-eval-001", "question_id": "q-001", "user_id": "user-eval-001", "user_answer": "...", "score": 0.5, "feedback": "...", "is_weak_spot": True, "answered_at": "2026-06-02T00:00:00Z"},
    "get_agent_context": {"user_id": "user-eval-001", "topic": None, "profile": {}, "capsules": [], "weak_spots": [], "recent_events": [], "generated_at": "2026-06-02T00:00:00Z"},
    "record_mastery": {"id": "cm-001", "concept": "closures", "mastery_level": "apply", "theory_reps": 1, "practice_reps": 2, "practice_quality": 0.75, "max_difficulty": 2, "struggle_passed": 0},
    "get_mastery_progress": {"concepts": [{"concept": "closures", "badge": "🟩", "mastery_level": "apply", "practice_reps": 2, "practice_quality": 0.75}], "rollup": {"total_concepts": 1, "apply_plus": 1, "expert": 0, "total_practice_reps": 2, "avg_quality": 0.75, "blocking_expert": [{"concept": "closures", "level": "apply", "badge": "🟩"}]}},
    "get_next_focus": {"concept": "closures", "badge": "🟩", "mastery_level": "apply", "reason": "нужны задания сложнее (difficulty 3) + struggle-check для уровня explain"},
    "create_cards_from_capsule": {"created": 5},
    "complete_topic": {"id": "topic-eval-001", "status": "completed"},
    "get_due_cards": [{"card_id": "card-001", "question": "What is a closure?", "correct_answer": "...", "difficulty": 1, "topic_name": "Closures"}],
    "log_card_attempt": {"card_id": "card-001", "next_review_at": "2026-06-09T00:00:00Z", "interval_days": 6},
}

# OpenAI tool format (Ollama-compatible)
ALL_TOOLS = [
    {"type": "function", "function": {"name": "create_user", "description": "Create a new learner user.", "parameters": {"type": "object", "properties": {"email": {"type": "string"}, "display_name": {"type": "string"}}, "required": ["email", "display_name"]}}},
    {"type": "function", "function": {"name": "get_profile", "description": "Get the learner profile.", "parameters": {"type": "object", "properties": {"user_id": {"type": "string"}}, "required": ["user_id"]}}},
    {"type": "function", "function": {"name": "start_topic", "description": "Start a learning topic session.", "parameters": {"type": "object", "properties": {"user_id": {"type": "string"}, "topic_name": {"type": "string"}}, "required": ["user_id", "topic_name"]}}},
    {"type": "function", "function": {"name": "log_event", "description": "Log a learning event.", "parameters": {"type": "object", "properties": {"user_id": {"type": "string"}, "event_type": {"type": "string"}, "payload": {"type": "object"}}, "required": ["user_id", "event_type", "payload"]}}},
    {"type": "function", "function": {"name": "store_code_artifact", "description": "Store a code artifact.", "parameters": {"type": "object", "properties": {"user_id": {"type": "string"}, "topic_id": {"type": "string"}, "filename": {"type": "string"}, "content": {"type": "string"}, "language": {"type": "string"}}, "required": ["user_id", "topic_id", "filename", "content", "language"]}}},
    {"type": "function", "function": {"name": "store_capsule", "description": "Store a capsule generated by the agent.", "parameters": {"type": "object", "properties": {"user_id": {"type": "string"}, "topic_id": {"type": "string"}, "content_md": {"type": "string"}, "summary": {"type": "string"}, "review_questions": {"type": "array", "items": {"type": "object"}}}, "required": ["user_id", "topic_id", "content_md", "summary", "review_questions"]}}},
    {"type": "function", "function": {"name": "get_capsule", "description": "Fetch a stored capsule.", "parameters": {"type": "object", "properties": {"capsule_id": {"type": "string"}}, "required": ["capsule_id"]}}},
    {"type": "function", "function": {"name": "store_review_answer", "description": "Store a review answer.", "parameters": {"type": "object", "properties": {"user_id": {"type": "string"}, "question_id": {"type": "string"}, "user_answer": {"type": "string"}, "score": {"type": "number"}, "feedback": {"type": "string"}, "is_weak_spot": {"type": "boolean"}}, "required": ["user_id", "question_id", "user_answer", "score", "feedback", "is_weak_spot"]}}},
    {"type": "function", "function": {"name": "get_agent_context", "description": "Get agent context bundle.", "parameters": {"type": "object", "properties": {"user_id": {"type": "string"}, "topic": {"type": "string"}}, "required": ["user_id"]}}},
    {"type": "function", "function": {"name": "record_mastery", "description": "Record a theory or practice rep for a concept to track mastery progress. kind: 'theory' or 'practice'. For practice pass difficulty (1-3), quality_score (0-1), struggle_passed (0/1).", "parameters": {"type": "object", "properties": {"topic_id": {"type": "string"}, "concept": {"type": "string"}, "kind": {"type": "string"}, "difficulty": {"type": "integer"}, "quality_score": {"type": "number"}, "struggle_passed": {"type": "integer"}}, "required": ["topic_id", "concept", "kind"]}}},
    {"type": "function", "function": {"name": "get_mastery_progress", "description": "Get mastery progress with per-concept badges and what blocks expert level. Call when user asks about progress or how far to expert.", "parameters": {"type": "object", "properties": {"topic": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "get_next_focus", "description": "Get the concept that needs the most work next.", "parameters": {"type": "object", "properties": {"topic": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "create_cards_from_capsule", "description": "Create spaced-repetition cards from a capsule.", "parameters": {"type": "object", "properties": {"capsule_id": {"type": "string"}}, "required": ["capsule_id"]}}},
    {"type": "function", "function": {"name": "complete_topic", "description": "Mark a topic as completed.", "parameters": {"type": "object", "properties": {"topic_id": {"type": "string"}}, "required": ["topic_id"]}}},
    {"type": "function", "function": {"name": "get_due_cards", "description": "Get cards due for review today.", "parameters": {"type": "object", "properties": {"limit": {"type": "integer"}}, "required": []}}},
    {"type": "function", "function": {"name": "log_card_attempt", "description": "Log a card review attempt and update SM-2 interval.", "parameters": {"type": "object", "properties": {"card_id": {"type": "string"}, "rating": {"type": "integer"}, "user_answer": {"type": "string"}}, "required": ["card_id", "rating", "user_answer"]}}},
]

# directories searched for system_prompt_file (by basename)
PROMPT_DIRS = [
    PROMPTS_DIR,
    Path(__file__).parent.parent.parent / "packages" / "skills",
]


SKILLS_DIR = Path(__file__).parent.parent.parent / "packages" / "skills"


def load_prompt(prompt_file: str, template_vars: dict) -> str:
    name = Path(prompt_file).name
    path = next((d / name for d in PROMPT_DIRS if (d / name).exists()), PROMPTS_DIR / name)
    text = path.read_text()
    # In a real session the agent can read referenced skill files; inline _pedagogy.md so evals
    # exercise the real combined behavior (hint ladder, diagrams, struggle-check, calibration).
    if "_pedagogy.md" in text:
        ped = SKILLS_DIR / "_pedagogy.md"
        if ped.exists():
            text += "\n\n---\n# Reference: _pedagogy.md\n\n" + ped.read_text()
    for k, v in template_vars.items():
        text = text.replace(f"{{{{{k}}}}}", str(v))
    return text


def run_single_turn(client: OpenAI, system_prompt: str, user_message: str) -> tuple[list[dict], str]:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    tool_calls_made = []
    final_text = ""

    while True:
        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=messages,
            tools=ALL_TOOLS,
            tool_choice="auto",
        )

        choice = response.choices[0]
        message = choice.message
        final_text = message.content or final_text

        if not message.tool_calls:
            break

        messages.append(message)

        for tc in message.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            tool_calls_made.append({"name": tc.function.name, "input": args})
            result = MOCK_TOOL_RESULTS.get(tc.function.name, {})
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })

        if choice.finish_reason != "tool_calls":
            break

    return tool_calls_made, final_text


def check_single_turn(scenario: dict, tool_calls: list[dict], final_text: str = "") -> tuple[bool, str]:
    text_lower = final_text.lower()
    for needle in scenario.get("expected_text_contains", []):
        if needle.lower() not in text_lower:
            return False, f"Expected text to contain {needle!r}. Got: {final_text[:200]!r}"
    any_list = scenario.get("expected_text_contains_any", [])
    if any_list and not any(n.lower() in text_lower for n in any_list):
        return False, f"Expected text to contain any of {any_list}. Got: {final_text[:200]!r}"
    for needle in scenario.get("expected_text_absent", []):
        if needle.lower() in text_lower:
            return False, f"Expected text to NOT contain {needle!r}. Got: {final_text[:200]!r}"

    expected = scenario.get("expected_tool_calls", [])
    actual_names = [tc["name"] for tc in tool_calls]

    for name in expected:
        if name not in actual_names:
            return False, f"Missing expected tool call: {name}. Got: {actual_names}"

    for tool_name, required_keys in scenario.get("required_args_present", {}).items():
        call = next((tc for tc in tool_calls if tc["name"] == tool_name), None)
        if not call:
            return False, f"Tool {tool_name} not called"
        for key in required_keys:
            if key not in call["input"]:
                return False, f"Tool {tool_name} missing arg: {key}"

    for tool_name, expected_values in scenario.get("expected_arg_values", {}).items():
        call = next((tc for tc in tool_calls if tc["name"] == tool_name), None)
        if not call:
            return False, f"Tool {tool_name} not called"
        for key, val in expected_values.items():
            actual_val = call["input"].get(key)
            if actual_val != val:
                return False, f"Tool {tool_name} arg {key}: expected {val}, got {actual_val}"

    for tool_name, expected_args in scenario.get("expected_tool_args", {}).items():
        call = next((tc for tc in tool_calls if tc["name"] == tool_name), None)
        if not call:
            return False, f"Tool {tool_name} not called"
        for key, val in expected_args.items():
            actual_val = call["input"].get(key)
            if actual_val != val:
                return False, f"Tool {tool_name} arg {key}: expected {val!r}, got {actual_val!r}"

    return True, "pass"


def run_scenario(client: OpenAI, scenario_path: Path) -> dict:
    scenario = json.loads(scenario_path.read_text())
    name = scenario["name"]
    print(f"  Running: {name}")

    if "turns" in scenario:
        all_passed = True
        failures = []
        for i, turn in enumerate(scenario["turns"]):
            prompt_file = Path(turn["system_prompt_file"]).name
            template_vars = turn.get("template_vars", {})
            system_prompt = load_prompt(prompt_file, template_vars)
            tool_calls, final_text = run_single_turn(client, system_prompt, turn["user_message"])
            passed, msg = check_single_turn(turn, tool_calls, final_text)
            if not passed:
                all_passed = False
                failures.append(f"Turn {i+1}: {msg}")
        return {"name": name, "passed": all_passed, "message": "; ".join(failures) if failures else "pass"}
    else:
        prompt_file = Path(scenario["system_prompt_file"]).name
        template_vars = scenario.get("template_vars", {})
        system_prompt = load_prompt(prompt_file, template_vars)
        tool_calls, final_text = run_single_turn(client, system_prompt, scenario["user_message"])
        passed, msg = check_single_turn(scenario, tool_calls, final_text)
        return {"name": name, "passed": passed, "message": msg, "tool_calls": tool_calls}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", help="Run a single scenario by name prefix")
    parser.add_argument("--retries", type=int, default=2, help="Retry failed scenarios N times (default: 2)")
    args = parser.parse_args()

    print(f"Model: {OLLAMA_MODEL}")

    client = OpenAI(base_url=OLLAMA_BASE_URL, api_key=OLLAMA_API_KEY)

    scenario_files = sorted(SCENARIOS_DIR.glob("*.json"))
    if args.scenario:
        scenario_files = [f for f in scenario_files if args.scenario in f.stem]

    if not scenario_files:
        print("No scenarios found.")
        sys.exit(1)

    results = []
    for path in scenario_files:
        result = run_scenario(client, path)
        for attempt in range(args.retries):
            if result["passed"]:
                break
            print(f"    retry {attempt + 1}/{args.retries}...")
            result = run_scenario(client, path)
        results.append(result)
        status = "PASS" if result["passed"] else "FAIL"
        print(f"  [{status}] {result['name']}: {result['message']}")

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print(f"\nResults: {passed}/{total} passed")

    output = RESULTS_DIR / "latest.json"
    output.write_text(json.dumps(results, indent=2, default=str))
    print(f"Results saved to {output}")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
