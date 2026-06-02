# Skill: answer-evaluator

## Trigger phrases
- "evaluate answer"
- "check my answer"
- "score this"
- User submits an answer to a review question

## What this skill does
Scores a developer's answer to a review question against the correct answer, provides feedback, flags weak spots.

## Input from user

- `question_id` (required — from an existing ReviewQuestion)
- `user_answer` (required — the developer's response)

## Prompts to load
1. `evaluate-answer.md`

## MCP tools called
| Tool | When |
|---|---|
| `store_review_answer` | After evaluation with score, feedback, is_weak_spot |

## Output to user
- Score (0.0–1.0)
- Feedback explaining what was right/wrong
- Whether this was flagged as a weak spot
- What to study next if weak

## Example invocation
> "My answer to question xyz-456: closures capture the outer variable by reference"

Agent evaluates, calls `store_review_answer`, returns score and feedback.
