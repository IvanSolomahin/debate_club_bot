# repo.py
from datetime import datetime, timezone
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from db import User, Training, Registration


# ── Users ──────────────────────────────────────────────────────────────────

async def get_user_by_tg_id(session: AsyncSession, tg_id: int) -> User | None:
    result = await session.execute(select(User).where(User.tg_id == tg_id))
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    tg_id: int,
    username: str | None,
    full_name: str,
    is_native: bool,
    university: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    social_url: str | None = None,
    comment: str | None = None,
) -> User:
    user = User(
        tg_id=tg_id,
        username=username,
        full_name=full_name,
        is_native=is_native,
        university=university,
        phone=phone,
        email=email,
        social_url=social_url,
        comment=comment,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update_user(session: AsyncSession, tg_id: int, **kwargs) -> User | None:
    user = await get_user_by_tg_id(session, tg_id)
    if not user:
        return None
    for key, value in kwargs.items():
        setattr(user, key, value)
    await session.commit()
    await session.refresh(user)
    return user


async def get_all_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User))
    return list(result.scalars().all())


# ── Trainings ──────────────────────────────────────────────────────────────

async def get_upcoming_trainings(session: AsyncSession) -> list[Training]:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(Training).where(Training.dt >= now).order_by(Training.dt)
    )
    return list(result.scalars().all())


async def get_training_by_id(
    session: AsyncSession, training_id: int
) -> Training | None:
    result = await session.execute(select(Training).where(Training.id == training_id))
    return result.scalar_one_or_none()


async def create_training(
    session: AsyncSession,
    title: str,
    dt: datetime,
    created_by: int,
    description: str | None = None,
    location: str | None = None,
) -> Training:
    training = Training(
        title=title,
        dt=dt,
        created_by=created_by,
        description=description,
        location=location,
    )
    session.add(training)
    await session.commit()
    await session.refresh(training)
    return training


async def update_training(
    session: AsyncSession,
    training_id: int,
    **kwargs,
) -> Training | None:
    """Update fields of a future training only. Returns None if not found or already past."""
    training = await get_training_by_id(session, training_id)
    if not training:
        return None
    if training.dt < datetime.now(timezone.utc):
        return None
    for key, value in kwargs.items():
        setattr(training, key, value)
    await session.commit()
    await session.refresh(training)
    return training


async def delete_training(session: AsyncSession, training_id: int) -> bool:
    """Delete a future training only. Returns False if not found or already past."""
    training = await get_training_by_id(session, training_id)
    if not training:
        return False
    if training.dt < datetime.now(timezone.utc):
        return False
    await session.delete(training)
    await session.commit()
    return True


# ── Registrations ──────────────────────────────────────────────────────────

async def register_user_for_training(
    session: AsyncSession, user_id: int, training_id: int
) -> tuple[Registration | None, str]:
    """
    Returns (registration, status) where status is:
      'ok' | 'already_registered' | 'training_not_found'
    """
    training = await get_training_by_id(session, training_id)
    if not training:
        return None, "training_not_found"

    reg = Registration(user_id=user_id, training_id=training_id)
    session.add(reg)
    try:
        await session.commit()
        await session.refresh(reg)
        return reg, "ok"
    except IntegrityError:
        await session.rollback()
        return None, "already_registered"


async def cancel_registration(
    session: AsyncSession, user_id: int, training_id: int
) -> bool:
    result = await session.execute(
        delete(Registration).where(
            Registration.user_id == user_id,
            Registration.training_id == training_id,
        )
    )
    await session.commit()
    return result.rowcount > 0


async def get_user_registrations(
    session: AsyncSession, user_id: int
) -> list[Registration]:
    result = await session.execute(
        select(Registration).where(Registration.user_id == user_id)
    )
    return list(result.scalars().all())


async def get_training_participants(
    session: AsyncSession, training_id: int
) -> list[User]:
    result = await session.execute(
        select(User)
        .join(Registration, Registration.user_id == User.id)
        .where(Registration.training_id == training_id)
        .order_by(Registration.registered_at)
    )
    return list(result.scalars().all())


async def is_registered(session: AsyncSession, user_id: int, training_id: int) -> bool:
    result = await session.execute(
        select(Registration).where(
            Registration.user_id == user_id,
            Registration.training_id == training_id,
        )
    )
    return result.scalar_one_or_none() is not None
