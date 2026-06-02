# Update Profile

You are updating the learner profile based on recent session activity.

## Input
- Current profile: {{current_profile}}
- Recent events: {{recent_events}}
- User ID: {{user_id}}

## Your job
Analyze the recent events and determine:
1. Which new topics were studied (add to known_topics if not present)
2. Which weak spots were confirmed or resolved
3. Whether skill_level should change (beginner → intermediate → advanced)

Then call `log_event` with:
- `user_id: {{user_id}}`
- `event_type: "profile_updated"`
- `payload: { "changes": { "known_topics": [...], "resolved_weak_spots": [...], "new_skill_level": "..." } }`

## Constraints
- Only upgrade skill_level if at least 3 topics show strong review scores
- Do not downgrade skill_level based on a single weak session
- Report what changed and why
