# tests/test_middlewares.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock

from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from middlewares.session_middleware import SessionMiddleware
from middlewares.admin_filter import AdminFilterMiddleware


# ── Session Middleware tests ────────────────────────────────────────────────

@pytest.fixture
def session_factory():
    session = AsyncMock(spec=AsyncSession)

    # Use Mock (not AsyncMock) so calling factory() returns the context manager directly
    factory = Mock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory, session


@pytest.fixture
def handler():
    h = AsyncMock()
    h.return_value = "handler_result"
    return h


@pytest.fixture
def message():
    m = MagicMock()
    m.from_user = MagicMock(id=12345)
    return m


class TestSessionMiddleware:
    @pytest.mark.asyncio
    async def test_session_passed_to_handler(self, handler, session_factory, message):
        """Session is injected into handler data"""
        factory, session = session_factory
        middleware = SessionMiddleware(factory)
        data = {}

        result = await middleware(handler, message, data)

        assert data["session"] is session
        assert result == "handler_result"
        handler.assert_called_once_with(message, data)

    @pytest.mark.asyncio
    async def test_session_context_manager_used(self, handler, session_factory, message):
        """Session context manager is entered and exited"""
        factory, session = session_factory
        middleware = SessionMiddleware(factory)
        data = {}

        await middleware(handler, message, data)

        factory.return_value.__aenter__.assert_awaited_once()
        factory.return_value.__aexit__.assert_awaited_once()


# ── Admin Filter Middleware tests ───────────────────────────────────────────

class TestAdminFilterMiddleware:
    @pytest.fixture
    def middleware(self):
        return AdminFilterMiddleware()

    @pytest.mark.asyncio
    async def test_admin_user_allowed(self, middleware):
        """Admin user passes through to handler"""
        session = AsyncMock()
        handler = AsyncMock(return_value="ok")

        msg = MagicMock(spec=Message)
        msg.from_user = MagicMock(id=12345)
        msg.answer = AsyncMock()

        data = {"session": session}

        with patch("middlewares.admin_filter.repo") as repo_mock:
            mock_user = MagicMock()
            mock_user.is_admin = True
            repo_mock.get_user_by_tg_id = AsyncMock(return_value=mock_user)

            result = await middleware(handler, msg, data)

        assert result == "ok"
        handler.assert_called_once_with(msg, data)
        msg.answer.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_admin_user_blocked(self, middleware):
        """Non-admin user is blocked"""
        session = AsyncMock()
        handler = AsyncMock(return_value="ok")

        msg = MagicMock(spec=Message)
        msg.from_user = MagicMock(id=12345)
        msg.answer = AsyncMock()

        data = {"session": session}

        with patch("middlewares.admin_filter.repo") as repo_mock:
            mock_user = MagicMock()
            mock_user.is_admin = False
            repo_mock.get_user_by_tg_id = AsyncMock(return_value=mock_user)

            result = await middleware(handler, msg, data)

        assert result is None
        handler.assert_not_called()
        msg.answer.assert_called_once()
        call_args = msg.answer.call_args
        assert "администратора" in call_args.args[0]

    @pytest.mark.asyncio
    async def test_unregistered_user_blocked(self, middleware):
        """Unregistered user is blocked"""
        session = AsyncMock()
        handler = AsyncMock(return_value="ok")

        msg = MagicMock(spec=Message)
        msg.from_user = MagicMock(id=12345)
        msg.answer = AsyncMock()

        data = {"session": session}

        with patch("middlewares.admin_filter.repo") as repo_mock:
            repo_mock.get_user_by_tg_id = AsyncMock(return_value=None)

            result = await middleware(handler, msg, data)

        assert result is None
        handler.assert_not_called()
        msg.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_callback_query_admin_allowed(self, middleware):
        """Admin callback query passes through"""
        session = AsyncMock()
        handler = AsyncMock(return_value="ok")

        cb = MagicMock(spec=CallbackQuery)
        cb.from_user = MagicMock(id=12345)
        cb.answer = AsyncMock()

        data = {"session": session}

        with patch("middlewares.admin_filter.repo") as repo_mock:
            mock_user = MagicMock()
            mock_user.is_admin = True
            repo_mock.get_user_by_tg_id = AsyncMock(return_value=mock_user)

            result = await middleware(handler, cb, data)

        assert result == "ok"
        handler.assert_called_once_with(cb, data)

    @pytest.mark.asyncio
    async def test_callback_query_non_admin_blocked(self, middleware):
        """Non-admin callback query is blocked"""
        session = AsyncMock()
        handler = AsyncMock(return_value="ok")

        cb = MagicMock(spec=CallbackQuery)
        cb.from_user = MagicMock(id=12345)
        cb.answer = AsyncMock()

        data = {"session": session}

        with patch("middlewares.admin_filter.repo") as repo_mock:
            mock_user = MagicMock()
            mock_user.is_admin = False
            repo_mock.get_user_by_tg_id = AsyncMock(return_value=mock_user)

            result = await middleware(handler, cb, data)

        assert result is None
        handler.assert_not_called()
        cb.answer.assert_called_once_with("⛔ У вас нет прав администратора.", show_alert=True)

    @pytest.mark.asyncio
    async def test_no_user_info_passed_through(self, middleware):
        """Event without user info passes through"""
        handler = AsyncMock(return_value="ok")

        # Event with no from_user
        event = MagicMock()
        event.from_user = None
        data = {}

        result = await middleware(handler, event, data)

        assert result == "ok"
        handler.assert_called_once_with(event, data)
