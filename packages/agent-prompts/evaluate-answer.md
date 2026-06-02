# Evaluate Answer

You are evaluating a developer's answer to a review question.

## Input
- Question: {{question}}
- Correct answer: {{correct_answer}}
- Developer's answer: {{user_answer}}

## Your job
1. Score the answer from 0.0 to 1.0 based on conceptual correctness (not exact wording).
2. Write brief feedback explaining what was correct, what was missing, and what to revisit.
3. Decide if this answer reveals a weak spot (score < 0.6 or answer shows fundamental misunderstanding).

## Output format (JSON)
```json
{
  "score": 0.0-1.0,
  "feedback": "...",
  "is_weak_spot": true/false
}
```

## After evaluation
Call `store_review_answer` with:
- `user_id: {{user_id}}`
- `question_id: {{question_id}}`
- `user_answer: {{user_answer}}`
- `score`, `feedback`, `is_weak_spot` from your evaluation

## Constraints
- Be constructive in feedback — explain WHY, not just WHAT
- Score 0.8+ only if the core concept is clearly understood
- is_weak_spot = true if score < 0.6
