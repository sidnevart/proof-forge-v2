# Skill: code-analyzer

## Trigger phrases
- "analyze my code"
- "check this file"
- "what concepts does this show"
- Developer pastes code or drops a file

## What this skill does
Reads a code file, identifies what learning concepts it demonstrates, detects weak signals, and persists the artifact.

## Input from user

- `topic_id` (required)
- `filename` (required)
- `content` — code content (required)
- `language` — programming language (required)

## Prompts to load
1. `analyze-code.md`

## MCP tools called
| Tool | When |
|---|---|
| `store_code_artifact` | To persist the file |
| `log_event` | To record `code_analyzed` with concepts and weak_signals |

## Output to user
- Concepts demonstrated in the code
- Weak signals detected
- Follow-up questions to deepen understanding

## Example invocation
> "Analyze this file: closure.js"

Agent identifies concepts, stores artifact, logs analysis, returns findings.
