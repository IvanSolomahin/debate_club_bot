# tests/test_repo.py
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from db import Base
import repo

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as s:
        yield s
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ── helpers ────────────────────────────────────────────────────────────────

async def make_user(session, tg_id: int = 1, is_native: bool = True):
    return await repo.create_user(
        session,
        tg_id=tg_id,
        username="test",
        full_name="Test User",
        is_native=is_native,
        university=None if is_native else "HSE",
        phone=None if is_native else "+79991234567",
        email=None if is_native else "test@example.com",
    )


async def make_training(session, user_id: int, future: bool = True):
    delta = timedelta(days=1) if future else timedelta(days=-1)
    return await repo.create_training(
        session,
        title="Test Training",
        dt=datetime.now(timezone.utc) + delta,
        created_by=user_id,
        location="Room 101",
    )


# ── Users ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_and_get_user(session):
    user = await make_user(session, tg_id=42)
    found = await repo.get_user_by_tg_id(session, 42)
    assert found is not None
    assert found.tg_id == 42
    assert found.full_name == "Test User"


@pytest.mark.asyncio
async def test_get_user_not_found(session):
    result = await repo.get_user_by_tg_id(session, 9999)
    assert result is None


@pytest.mark.asyncio
async def test_update_user(session):
    await make_user(session, tg_id=1)
    updated = await repo.update_user(session, tg_id=1, full_name="New Name")
    assert updated.full_name == "New Name"


@pytest.mark.asyncio
async def test_get_all_users(session):
    await make_user(session, tg_id=1)
    await make_user(session, tg_id=2)
    users = await repo.get_all_users(session)
    assert len(users) == 2


# ── Trainings ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_upcoming_trainings_excludes_past(session):
    user = await make_user(session)
    await make_training(session, user.id, future=True)
    await make_training(session, user.id, future=False)
    upcoming = await repo.get_upcoming_trainings(session)
    assert len(upcoming) == 1


@pytest.mark.asyncio
async def test_update_training_future(session):
    user = await make_user(session)
    training = await make_training(session, user.id, future=True)
    updated = await repo.update_training(session, training.id, title="Updated")
    assert updated is not None
    assert updated.title == "Updated"


@pytest.mark.asyncio
async def test_update_training_past_returns_none(session):
    user = await make_user(session)
    training = await make_training(session, user.id, future=False)
    result = await repo.update_training(session, training.id, title="Nope")
    assert result is None


@pytest.mark.asyncio
async def test_delete_training_future(session):
    user = await make_user(session)
    training = await make_training(session, user.id, future=True)
    deleted = await repo.delete_training(session, training.id)
    assert deleted is True
    assert await repo.get_training_by_id(session, training.id) is None


@pytest.mark.asyncio
async def test_delete_training_past_returns_false(session):
    user = await make_user(session)
    training = await make_training(session, user.id, future=False)
    result = await repo.delete_training(session, training.id)
    assert result is False


# ── Registrations ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_ok(session):
    user = await make_user(session)
    training = await make_training(session, user.id)
    _, status = await repo.register_user_for_training(session, user.id, training.id)
    assert status == "ok"


@pytest.mark.asyncio
async def test_register_duplicate(session):
    user = await make_user(session)
    training = await make_training(session, user.id)
    await repo.register_user_for_training(session, user.id, training.id)
    _, status = await repo.register_user_for_training(session, user.id, training.id)
    assert status == "already_registered"


@pytest.mark.asyncio
async def test_register_training_not_found(session):
    user = await make_user(session)
    _, status = await repo.register_user_for_training(session, user.id, 9999)
    assert status == "training_not_found"


@pytest.mark.asyncio
async def test_cancel_registration(session):
    user = await make_user(session)
    training = await make_training(session, user.id)
    await repo.register_user_for_training(session, user.id, training.id)
    result = await repo.cancel_registration(session, user.id, training.id)
    assert result is True
    assert not await repo.is_registered(session, user.id, training.id)


@pytest.mark.asyncio
async def test_cancel_nonexistent_registration(session):
    user = await make_user(session)
    training = await make_training(session, user.id)
    result = await repo.cancel_registration(session, user.id, training.id)
    assert result is False


@pytest.mark.asyncio
async def test_get_training_participants(session):
    user1 = await make_user(session, tg_id=1)
    user2 = await make_user(session, tg_id=2)
    training = await make_training(session, user1.id)
    await repo.register_user_for_training(session, user1.id, training.id)
    await repo.register_user_for_training(session, user2.id, training.id)
    participants = await repo.get_training_participants(session, training.id)
    assert len(participants) == 2
