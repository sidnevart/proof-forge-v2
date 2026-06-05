from app.routers.chat import get_system_prompt


def test_chat_system_prompt_is_compact_and_learning_focused():
    prompt = get_system_prompt()

    assert len(prompt) < 8_000
    assert "учебный ментор" in prompt.lower()
    assert "сократ" in prompt.lower()
    assert "ученик" in prompt.lower()
