import pytest

from app.repositories import user_repo
from app.schemas.user import UserCreate


@pytest.mark.asyncio
async def test_create_and_list_folder_serializes(client, db):
    """Regression: FolderOut.created_at was typed `str` but the ORM stores a
    datetime, so create/list 500'd on response serialization (surfacing as a
    fake CORS error in the browser). Exercise the real create→list path."""
    user = await user_repo.create_user(db, UserCreate(email="folder@example.com", display_name="F"))

    created = await client.post("/api/topic-folders", json={"user_id": user.id, "name": "KMP"})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == "KMP"
    assert body["user_id"] == user.id
    assert isinstance(body["created_at"], str) and body["created_at"]  # ISO string

    listed = await client.get(f"/api/topic-folders?user_id={user.id}")
    assert listed.status_code == 200, listed.text
    folders = listed.json()
    assert len(folders) == 1
    assert folders[0]["id"] == body["id"]
    assert folders[0]["name"] == "KMP"


@pytest.mark.asyncio
async def test_move_topic_into_and_out_of_folder(client, db):
    from app.repositories import topic_repo
    from app.schemas.topic import TopicStart

    user = await user_repo.create_user(db, UserCreate(email="move@example.com", display_name="M"))
    topic = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="Rust traits"))
    folder = await client.post("/api/topic-folders", json={"user_id": user.id, "name": "Systems"})
    folder_id = folder.json()["id"]

    moved = await client.patch(f"/api/topics/{topic.id}", json={"folder_id": folder_id})
    assert moved.status_code == 200, moved.text
    assert moved.json()["folder_id"] == folder_id

    removed = await client.patch(f"/api/topics/{topic.id}", json={"folder_id": ""})
    assert removed.status_code == 200, removed.text
    assert removed.json()["folder_id"] is None
