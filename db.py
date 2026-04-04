# db.py
from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    validates,
)

from config import settings

engine = create_async_engine(settings.DATABASE_URL)
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "is_native = 1 OR phone IS NOT NULL", name="check_non_hse_phone"
        ),
        CheckConstraint(
            "is_native = 1 OR email IS NOT NULL", name="check_non_hse_email"
        ),
        CheckConstraint(
            "is_native = 1 OR university IS NOT NULL", name="check_non_hse_university"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # может не быть у TG-аккаунта

    # Обязательно для всех
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    is_native: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # Обязательно для не-ВШЭ, NULL для ВШЭ
    university: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)

    # Опционально для всех
    social_url: Mapped[str | None] = mapped_column(String, nullable=True)
    comment: Mapped[str | None] = mapped_column(String, nullable=True)

    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    registrations: Mapped[list["Registration"]] = relationship(back_populates="user")

    @validates("email")
    def validate_email(self, key, value):
        if value and "@" not in value:
            raise ValueError("Некорректный email")
        return value

    @validates("phone")
    def validate_phone(self, key, value):
        if value:
            digits = value.replace("+", "").replace("-", "").replace(" ", "")
            if not digits.isdigit() or len(digits) < 10:
                raise ValueError("Некорректный телефон")
        return value


class Training(Base):
    __tablename__ = "trainings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # опционально
    location: Mapped[str] = mapped_column(String, nullable=False)
    dt: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    registrations: Mapped[list["Registration"]] = relationship(
        back_populates="training"
    )


class Registration(Base):
    __tablename__ = "registrations"
    __table_args__ = (UniqueConstraint("user_id", "training_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    training_id: Mapped[int] = mapped_column(ForeignKey("trainings.id"), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(back_populates="registrations")
    training: Mapped["Training"] = relationship(back_populates="registrations")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
