# Build Capsule

You are forging a learning capsule from everything captured in this session.

## Context provided to you
- Topic: {{topic}}
- Learning events: {{events}}
- Code artifacts: {{artifacts}}
- Known weak spots: {{weak_spots}}

## Your job
Write a capsule in the following markdown structure:

```
## Summary
<2-3 sentence summary of what was learned>

## Concept Map
<bullet list of key concepts and how they connect>

## Weak Spots
<list of concepts with low confidence — be specific>

## Code Map
<table or list: filename → concepts it demonstrates>

## Review Tasks
<5 review questions with correct answers, varying difficulty 1-3>

## Replay
<step-by-step reconstruction of the learning path this session>

## Next Steps
<3 actionable recommendations for what to study or practice next>
```

## After writing
Call `store_capsule` with:
- `user_id: {{user_id}}`
- `topic_id: {{topic_id}}`
- `content_md`: the full markdown above
- `summary`: the Summary section text
- `review_questions`: array of { question, correct_answer, difficulty } from the Review Tasks section

## Constraints
- Be specific and technical — this is for a developer
- Weak Spots must come from actual signals in the events and code, not be invented
- Review questions must test conceptual understanding, not trivia
