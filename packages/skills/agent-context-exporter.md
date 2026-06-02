# Skill: agent-context-exporter

## Trigger phrases
- "export context"
- "get my context"
- "show my learning summary"
- "prepare next session context"

## What this skill does
Retrieves the full agent context bundle from the backend: profile, recent capsule summaries, weak spots, and recent events. Presents it in a readable format and gives recommendations for the next session.

## Input from user

- `topic` (optional — filter context to a specific topic)

## Prompts to load
1. `export-agent-context.md`

## MCP tools called
| Tool | When |
|---|---|
| `get_agent_context` | To fetch the full context bundle |

## Output to user
- Current skill level and known topics
- Last 3 capsule summaries
- Top weak spots to focus on
- Recent activity summary
- Recommended next topic

## Example invocation
> "Export context for topic JavaScript Closures"

Agent fetches context, formats it, presents recommendations.
