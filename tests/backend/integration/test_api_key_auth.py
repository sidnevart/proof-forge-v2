import pytest


@pytest.mark.asyncio
async def test_create_api_key_requires_auth(client):
    """POST /api/auth/api-keys without auth must return 401."""
    res = await client.post("/api/auth/api-keys", json={"name": "test-key"})
    assert res.status_code == 401, res.text


@pytest.mark.asyncio
async def test_list_keys_requires_auth(client):
    """GET /api/auth/api-keys without auth must return 401."""
    res = await client.get("/api/auth/api-keys")
    assert res.status_code == 401, res.text


@pytest.mark.asyncio
async def test_delete_key_requires_auth(client):
    """DELETE /api/auth/api-keys/<id> without auth must return 401."""
    res = await client.delete("/api/auth/api-keys/nonexistent-id")
    assert res.status_code == 401, res.text
