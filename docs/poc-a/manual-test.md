# Manual Test Guide — PoC A

## Prerequisites

- Docker installed and running
- Python 3.12+
- Claude Desktop (for MCP plugin test) or curl (for REST-only test)

---

## 1. Start the backend

```bash
cp .env.example .env
docker-compose up -d postgres
docker-compose up backend
```

Verify:
```bash
curl http://localhost:8000/health
# Expected: {"status": "ok"}
```

OpenAPI docs: http://localhost:8000/docs

---

## 2. Create a user

```bash
curl -X POST http://localhost:8000/api/users \
  -H "Content-Type: application/json" \
  -d '{"email": "dev@example.com", "display_name": "Alex"}'
```

Expected: `{"id": "<UUID>", "email": "dev@example.com", ...}`

Save the `id` as `USER_ID`.

---

## 3. Start a topic

```bash
curl -X POST http://localhost:8000/api/topics/start \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"$USER_ID\", \"name\": \"JavaScript Closures\"}"
```

Expected: `{"id": "<UUID>", "name": "JavaScript Closures", "status": "active", ...}`

Save the `id` as `TOPIC_ID`.

---

## 4. Send a learning event (note)

```bash
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d "{
    \"user_id\": \"$USER_ID\",
    \"event_type\": \"note_added\",
    \"payload\": {\"text\": \"Closures capture outer scope by reference\", \"topic_id\": \"$TOPIC_ID\"}
  }"
```

Expected: `{"id": "<UUID>", "event_type": "note_added", ...}`

---

## 5. Send a code artifact

```bash
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d "{
    \"user_id\": \"$USER_ID\",
    \"event_type\": \"code_artifact\",
    \"payload\": {
      \"topic_id\": \"$TOPIC_ID\",
      \"filename\": \"counter.js\",
      \"content\": \"function makeCounter() { let n = 0; return () => ++n; }\",
      \"language\": \"javascript\"
    }
  }"
```

Expected: `{"id": "<UUID>", "event_type": "code_artifact", ...}`

---

## 6. Build and store a capsule

In a real session the agent generates this. For manual testing, send pre-written content:

```bash
curl -X POST http://localhost:8000/api/capsules \
  -H "Content-Type: application/json" \
  -d "{
    \"user_id\": \"$USER_ID\",
    \"topic_id\": \"$TOPIC_ID\",
    \"content_md\": \"## Summary\nClosures capture outer scope by reference.\n\n## Concept Map\n- Closure = function + lexical environment\n\n## Weak Spots\n- Difference between value capture and reference capture\n\n## Code Map\n| counter.js | factory pattern, closure state |\n\n## Review Tasks\nSee review_questions.\n\n## Replay\n1. Read about scope\n2. Wrote counter.js\n\n## Next Steps\n- Study module pattern\",
    \"summary\": \"Closures capture outer scope by reference.\",
    \"review_questions\": [
      {\"question\": \"What is a closure?\", \"correct_answer\": \"A function that captures its lexical environment.\", \"difficulty\": 1},
      {\"question\": \"Does a closure capture value or reference?\", \"correct_answer\": \"Reference — the variable binding, not a snapshot.\", \"difficulty\": 2}
    ]
  }"
```

Expected: `{"id": "<UUID>", "content_html": "<h2>Summary</h2>...", "review_questions": [{...}, {...}]}`

Save the `id` as `CAPSULE_ID` and a question `id` as `QUESTION_ID`.

---

## 7. Fetch the capsule

```bash
curl http://localhost:8000/api/capsules/$CAPSULE_ID
```

Expected: full capsule JSON with `content_md`, `content_html`, `review_questions`.

---

## 8. Submit a review answer

```bash
curl -X POST http://localhost:8000/api/reviews/answer \
  -H "Content-Type: application/json" \
  -d "{
    \"user_id\": \"$USER_ID\",
    \"question_id\": \"$QUESTION_ID\",
    \"user_answer\": \"A closure is a function that remembers its outer scope variables.\",
    \"score\": 0.85,
    \"feedback\": \"Correct — captures lexical environment including variable bindings.\",
    \"is_weak_spot\": false
  }"
```

Expected: `{"id": "<UUID>", "score": 0.85, "is_weak_spot": false, ...}`

---

## 9. Check agent context export

```bash
curl "http://localhost:8000/api/agent-context?userId=$USER_ID&topic=JavaScript+Closures"
```

Expected JSON with:
- `profile.skill_level`: "beginner"
- `capsules`: array with at least 1 entry
- `recent_events`: array with at least 2 entries
- `weak_spots`: empty (score was high)

---

## 10. Test MCP plugin (Claude Desktop)

Install the plugin:
```bash
pip install -e apps/mcp-server
```

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "proof-forge": {
      "command": "proof-forge-mcp",
      "env": { "BACKEND_URL": "http://localhost:8000" }
    }
  }
}
```

Restart Claude Desktop. In a new conversation:

1. "Create user: email test@example.com, display_name Dev" → agent calls `create_user`
2. "Start topic: Async/Await" → agent calls `get_profile` + `start_topic`
3. "I learned that await pauses execution until a promise resolves" → agent calls `log_event`
4. "Build capsule" → agent calls `store_capsule`
5. "Export my context" → agent calls `get_agent_context`

Each step should show tool use in Claude Desktop's tool call view.

---

## 11. Run tests

```bash
cd apps/backend
pip install -e ".[test]"
cd ../..
pytest tests/backend/ -v
```

Expected: all tests green.

---

## Expected results

| Step | Expected outcome |
|---|---|
| Health check | `{"status": "ok"}` |
| Create user | User row + LearnerProfile row created |
| Start topic | Topic row with status=active |
| Log event | LearningEvent row created |
| Code artifact event | LearningEvent + CodeArtifact rows created |
| Store capsule | Capsule row + ReviewQuestion rows, HTML rendered |
| Fetch capsule | Full capsule with questions |
| Review answer (high score) | ReviewAttempt created, no WeakSpot |
| Review answer (low score) | ReviewAttempt + WeakSpot created |
| Agent context | Profile + capsules + events aggregated |
| MCP plugin | Agent calls tools, data persists in DB |
| Tests | All unit + integration tests pass |
