from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
import repo


class AdminFilterMiddleware(BaseMiddleware):
    """Blocks access to admin router for non-admin users."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_id: int | None = None

        if isinstance(event, Message) and event.from_user:
            tg_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            tg_id = event.from_user.id

        # First check: is user in ADMIN_IDS config?
        if tg_id is not None and tg_id in settings.ADMIN_IDS:
            # User is a config admin, allow access
            return await handler(event, data)

        # Second check: is user an admin in database?
        session: AsyncSession = data.get("session")  # type: ignore[assignment]
        if tg_id is not None and session is not None:
            user = await repo.get_user_by_tg_id(session, tg_id)
            if user is not None and user.is_admin:
                # User is an admin in DB, allow access
                return await handler(event, data)

        # Block access for non-admin users
        if isinstance(event, Message):
            await event.answer("⛔ У вас нет прав администратора.")
        elif isinstance(event, CallbackQuery):
            await event.answer("⛔ У вас нет прав администратора.", show_alert=True)
        return  # block handler
