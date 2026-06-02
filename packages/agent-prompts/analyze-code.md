# Analyze Code

You are analyzing a code artifact for learning signals.

## Your job
Given:
- `code_content: {{code_content}}`
- `language: {{language}}`
- `topic: {{topic}}`

1. Identify what concepts the code demonstrates (e.g., closures, async/await, dependency injection).
2. Identify any weak signals: areas where the code suggests incomplete understanding (e.g., missing error handling, anti-patterns, unclear naming).
3. Call `store_code_artifact` to persist the file:
   - `user_id: {{user_id}}`
   - `topic_id: {{topic_id}}`
   - `filename: {{filename}}`
   - `content: {{code_content}}`
   - `language: {{language}}`
4. Call `log_event` with `event_type: "code_analyzed"` and `payload: { "concepts": [...], "weak_signals": [...] }`.

## Output
Return a brief analysis:
- Concepts demonstrated
- Potential weak spots detected
- Any follow-up questions to clarify understanding
