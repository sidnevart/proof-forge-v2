import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.main import app
from app.database import Base, get_db

TEST_DB_URL = "sqlite+aiosqlite:///./test.db"

test_engine = create_async_engine(TEST_DB_URL, echo=False)
test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db():
    async with test_session_factory() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def patch_bg_session_factory():
    """Route background tasks to the test DB and drain them after each test."""
    import asyncio
    import app.services.card_generation as cg
    import app.routers.practice as pr
    import app.routers.topics as tr
    from app.database import async_session_factory as orig
    pr.async_session_factory = test_session_factory
    tr.async_session_factory = test_session_factory
    cg.async_session_factory = test_session_factory
    yield
    # Drain any background asyncio tasks spawned during the test to avoid DB locking
    pending = [t for t in asyncio.all_tasks() if t != asyncio.current_task()]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    pr.async_session_factory = orig
    tr.async_session_factory = orig
    cg.async_session_factory = orig


@pytest_asyncio.fixture
async def client(db):
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
