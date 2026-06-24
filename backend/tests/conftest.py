"""Shared test fixtures for pytest + httpx AsyncClient tests."""

import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Override DATABASE_URL to use in-memory SQLite BEFORE importing app modules
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-for-unit-tests-only"
os.environ["DEBUG"] = "true"
os.environ["TUNNEL_ENABLED"] = "false"

from app.database import engine, async_session, Base, get_db
from app.main import app
from app.routers.auth import get_password_hash
from app.security import _rate_limit_store, _login_attempts


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test and drop them after."""
    # Reset rate limiter and login lockout state between tests
    _rate_limit_store.clear()
    _login_attempts.clear()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    """Provide an async database session for tests that need direct DB access."""
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    """Provide an httpx AsyncClient for testing the FastAPI app."""
    async with async_session() as session:
        async def override_get_db():
            yield session

        app.dependency_overrides[get_db] = override_get_db
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(client):
    """Create a test user with known credentials and return user info + token."""
    register_data = {
        "username": "testuser",
        "password": "Testpass1",
        "email": "test@example.com",
    }
    response = await client.post("/api/auth/register", json=register_data)
    assert response.status_code == 200
    data = response.json()
    return {
        "id": data["user"]["id"],
        "username": data["user"]["username"],
        "token": data["token"],
    }


@pytest_asyncio.fixture
async def auth_headers(test_user):
    """Return Authorization headers for the test user."""
    return {"Authorization": f"Bearer {test_user['token']}"}
