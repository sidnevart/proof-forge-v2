# Generate Review

You are generating review questions from a capsule.

## Input
- Capsule content: {{capsule_md}}
- Number of questions: {{n_questions}}
- Difficulty range: {{difficulty}} (1=easy, 2=medium, 3=hard)

## Your job
Generate exactly {{n_questions}} questions that:
- Test conceptual understanding (not syntax memorization)
- Cover different sections of the capsule (summary, concept map, weak spots)
- Include the correct answer for each

## Output format (JSON array)
```json
[
  {
    "question": "...",
    "correct_answer": "...",
    "difficulty": 1
  }
]
```

## Constraints
- Questions must be answerable from the capsule content
- At least one question must target a listed weak spot
- Do not repeat questions from previous review sessions if possible
