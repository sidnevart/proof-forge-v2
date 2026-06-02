# Export Agent Context

You are preparing the context block for the next agent session.

## Input
- User ID: {{user_id}}
- Topic filter (optional): {{topic}}

## Your job
1. Call `get_agent_context` with `user_id: {{user_id}}` and `topic: {{topic}}`.
2. Present the returned context to the developer in a readable format:
   - Current skill level and known topics
   - Recent capsule summaries (last 3)
   - Top weak spots to revisit
   - Recent learning events

## Output
Show the context block and tell the developer:
- "This context will be available in your next session"
- Which weak spots they should focus on next
- Suggested next topic based on progression

## Constraints
- Do not fabricate data — only surface what the API returned
- If no capsules exist yet, prompt the developer to build one first
