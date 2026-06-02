# Skill: learner-profile-updater

## Trigger phrases
- "update my profile"
- "sync profile"
- "update my progress"

## What this skill does
Reads the current learner profile and recent events, determines what changed, and logs a `profile_updated` event with the delta.

## Input from user


## Prompts to load
1. `update-profile.md`

## MCP tools called
| Tool | When |
|---|---|
| `get_profile` | At start to read current state |
| `log_event` | To record `profile_updated` with changes |

## Output to user
- What changed in the profile (new topics, resolved weak spots, skill level change)
- Current profile summary

## Example invocation
> "Update my profile"

Agent fetches profile + recent events, synthesizes changes, logs the update event.
