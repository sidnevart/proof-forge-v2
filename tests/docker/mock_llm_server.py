"""
Mock OpenAI-compatible /v1/chat/completions server for integration tests.

Returns deterministic, controlled responses based on prompt keywords.
Supports both streaming (SSE) and non-streaming modes.

Usage:
    python mock_llm_server.py
    # or
    uvicorn mock_llm_server:app --host 0.0.0.0 --port 8000
"""
import asyncio
import json
import os
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI()

PORT = int(os.environ.get("MOCK_LLM_PORT", "8000"))


# ── canned responses ──────────────────────────────────────────────────────────

FLASHCARD_CONTENT = """```js
const [count, setCount] = useState(0);
```
Что возвращает useState?"""

FILL_BLANK_FRONT = """В React функция ___ вызывается после каждого рендера и позволяет синхронизировать компонент с внешней системой."""

CODE_REVIEW_FRONT = """```jsx
useEffect(() => {
  fetch('/api/data').then(setData)
}, []);
```
Что здесь может привести к утечке памяти?"""

PRACTICAL_FRONT = """У тебя форма с 10 полями. Каждый ввод вызывает ререндер всех полей. Как оптимизировать?"""


CARDS_RESPONSE = [
    {"type": "FLASHCARD", "front": FLASHCARD_CONTENT, "back": "Массив [count, setCount] — кортеж из текущего значения и функции-сеттера.", "difficulty": 1},
    {"type": "FILL_BLANK", "front": FILL_BLANK_FRONT, "back": "useEffect", "difficulty": 1},
    {"type": "CODE_REVIEW", "front": CODE_REVIEW_FRONT, "back": "Компонент размонтируется раньше, чем fetch завершится. setData вызовется на уже размонтированном компоненте.", "difficulty": 2},
    {"type": "PRACTICAL", "front": PRACTICAL_FRONT, "back": "Мемоизировать значения (useMemo), разделить на подкомпоненты, использовать React.memo или useCallback. Главная причина — создание новых объектов-значений при каждом рендере.", "difficulty": 2},
]

CAPSULE_RESPONSE = {
    "summary": "React hooks: управление состоянием и побочными эффектами в функциональных компонентах.",
    "content_md": "## Обзор\n\nReact Hooks — функции, которые позволяют использовать состояние и другие возможности React без классов.\n\n## Ключевые концепции\n\n### useState\n\n```jsx\nconst [state, setState] = useState(initialValue)\n```\n\nВозвращает кортеж из текущего значения и функции для его обновления.\n\n### useEffect\n\n```jsx\nuseEffect(() => {\n  // эффект\n  return () => { /* очистка */ }\n}, [deps])\n```\n\nЗапускается после каждого рендера, если изменились зависимости.\n\n## Практическое применение\n\n1. Формы: `useState` для каждого поля.\n2. Загрузка данных: `useEffect` + `fetch`.\n3. Анимации: `useEffect` для работы с RAF.\n\n## Типичные ошибки\n\n- Забыть массив зависимостей → бесконечный цикл.\n- Мутация state напрямую → React не видит изменений.\n\n## Важно запомнить\n\n- Хуки можно вызывать только на верхнем уровне компонента.\n- Хуки нельзя вызывать в циклах и условиях.",
    "review_questions": [
        {"question": "Что такое React Hook?", "correct_answer": "Функция, дающая функциональным компонентам доступ к состоянию и жизненному циклу.", "difficulty": 1},
        {"question": "Что возвращает useState?", "correct_answer": "Кортеж [значение, функция-сеттер].", "difficulty": 1},
        {"question": "Когда вызывается useEffect без массива зависимостей?", "correct_answer": "После каждого рендера компонента.", "difficulty": 2},
        {"question": "Зачем нужна функция очистки в useEffect?", "correct_answer": "Чтобы отменить подписки, таймеры или запросы при размонтировании.", "difficulty": 2},
        {"question": "Почему setInterval внутри useEffect без очистки — проблема?", "correct_answer": "Каждый рендер создаёт новый интервал, старые не очищаются.", "difficulty": 3},
        {"question": "Объясни на примере: почему замыкание в useEffect может читать устаревшее состояние?", "correct_answer": "useEffect захватывает значения на момент рендера. Если не указать зависимости, колбэк читает стейт из первого рендера.", "difficulty": 3},
    ],
}

CONSPECT_FALLBACK = """## Обзор

Это конспект по изучаемой теме.

### Аналогия
Представь, что это инструмент, который решает практическую задачу.

## Ключевые концепции

### Концепция 1

Описание первой ключевой концепции.

### Концепция 2

Описание второй ключевой концепции.

```python
# пример кода
def example():
    return "hello"
```

## Практическое применение

Применяется в production-проектах для решения типовых задач.

## Типичные ошибки

1. Первая ошибка — как её избежать.
2. Вторая ошибка — правильный подход.

## Важно запомнить

- Ключевой тезис 1
- Ключевой тезис 2
- Ключевой тезис 3"""

CHAT_RESPONSE = "Отличный вопрос! Давай разберёмся по шагам. Что ты уже знаешь об этом? Попробуй сначала сформулировать своими словами, а потом я помогу уточнить."


# ── detection ─────────────────────────────────────────────────────────────────

def _get_user_message(messages: list[dict]) -> str:
    """Extract the last user message from the messages list."""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg.get("content", "")
    return messages[-1].get("content", "") if messages else ""


def _detect_prompt_type(messages: list[dict]) -> str:
    """Determine what kind of response to generate based on the prompt."""
    combined = " ".join(
        m.get("content", "") for m in messages
    ).lower()

    if "карточки" in combined and ("интервального повторения" in combined or "сгенерируй" in combined):
        return "cards"
    if "обучающую капсулу" in combined or "создай обучающую капсулу" in combined:
        return "capsule"
    if "конспект" in combined or "структурированный конспект" in combined:
        return "conspect"
    return "chat"


def _make_usage() -> dict:
    return {
        "prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150
    }


def _make_choice(content: str, finish_reason: str = "stop") -> list[dict]:
    return [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": finish_reason}]


# ── endpoints ─────────────────────────────────────────────────────────────────

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    messages: list[dict] = body.get("messages", [])
    stream: bool = body.get("stream", False)
    prompt_type = _detect_prompt_type(messages)

    if prompt_type == "cards":
        content = json.dumps(CARDS_RESPONSE, ensure_ascii=False)
    elif prompt_type == "capsule":
        content = json.dumps(CAPSULE_RESPONSE, ensure_ascii=False)
    elif prompt_type == "conspect":
        content = CONSPECT_FALLBACK
    else:
        content = CHAT_RESPONSE

    if stream:
        return _stream_response(content, prompt_type)
    else:
        return {"choices": _make_choice(content), "usage": _make_usage()}


def _stream_response(content: str, prompt_type: str):
    """Return a streaming SSE response."""

    async def event_stream():
        # For card/capsule prompt types, send the whole JSON at once
        if prompt_type in ("cards", "capsule"):
            chunk = json.dumps({
                "choices": [{"delta": {"content": content}, "index": 0}]
            })
            yield f"data: {chunk}\n\n"
        else:
            # Stream content token by token (sentence-chunked)
            for token in _tokenize(content):
                chunk = json.dumps({
                    "choices": [{"delta": {"content": token}, "index": 0}]
                })
                yield f"data: {chunk}\n\n"
                await asyncio.sleep(0.02)  # small delay to simulate streaming
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


def _tokenize(text: str, max_chunk: int = 60) -> list[str]:
    """Split text into small chunks for streaming simulation."""
    words = text.split(" ")
    chunks = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 > max_chunk and current:
            chunks.append(current + " ")
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        chunks.append(current)
    return chunks


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
