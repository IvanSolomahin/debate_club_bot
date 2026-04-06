# tests/test_reminders.py
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch, Mock

from services.reminders import ReminderService


class _FakeAsyncContextManager:
    """Proper async context manager mock."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        pass


@pytest.fixture
def bot():
    b = AsyncMock()
    b.send_message = AsyncMock()
    return b


@pytest.fixture
def session():
    return AsyncMock()


@pytest.fixture
def session_factory(session):
    factory = Mock()
    factory.return_value = _FakeAsyncContextManager(session)
    return factory, session


@pytest.fixture
def reminder_service(bot, session_factory):
    factory, _ = session_factory
    return ReminderService(
        bot=bot,
        session_factory=factory,
        reminder_hours=[24, 1],
    )


class TestReminderService:
    @pytest.mark.asyncio
    async def test_no_upcoming_trainings(self, reminder_service, session_factory):
        """No trainings → no messages sent"""
        _, session = session_factory

        with patch("services.reminders.repo") as repo_mock:
            repo_mock.get_upcoming_trainings = AsyncMock(return_value=[])

            await reminder_service._send_reminders()

        repo_mock.get_upcoming_trainings.assert_called()
        bot = reminder_service.bot
        bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_reminder_sent_24h_before(self, reminder_service, session_factory):
        """Training in 24h → 24h reminder sent"""
        _, session = session_factory
        bot = reminder_service.bot

        training = MagicMock()
        training.id = 1
        training.title = "Debate 101"
        training.dt = datetime.now(timezone.utc) + timedelta(hours=24)
        training.location = "Room 101"

        participant = MagicMock()
        participant.tg_id = 12345
        participant.reminders_enabled = True

        with patch("services.reminders.repo") as repo_mock:
            repo_mock.get_upcoming_trainings = AsyncMock(return_value=[training])
            repo_mock.get_training_participants = AsyncMock(return_value=[participant])

            await reminder_service._send_reminders()

        bot.send_message.assert_called_once()
        call_args = bot.send_message.call_args
        assert call_args.args[0] == 12345
        assert "Debate 101" in call_args.args[1]
        assert "завтра" in call_args.args[1].lower()

    @pytest.mark.asyncio
    async def test_reminder_sent_1h_before(self, reminder_service, session_factory):
        """Training in 1h → 1h reminder sent"""
        _, session = session_factory
        bot = reminder_service.bot

        training = MagicMock()
        training.id = 1
        training.title = "Debate 101"
        training.dt = datetime.now(timezone.utc) + timedelta(hours=1)
        training.location = "Room 101"

        participant = MagicMock()
        participant.tg_id = 12345
        participant.reminders_enabled = True

        with patch("services.reminders.repo") as repo_mock:
            repo_mock.get_upcoming_trainings = AsyncMock(return_value=[training])
            repo_mock.get_training_participants = AsyncMock(return_value=[participant])

            await reminder_service._send_reminders()

        bot.send_message.assert_called_once()
        call_args = bot.send_message.call_args
        assert call_args.args[0] == 12345
        assert "Debate 101" in call_args.args[1]
        assert "через час" in call_args.args[1].lower()

    @pytest.mark.asyncio
    async def test_reminders_disabled_user_skipped(self, reminder_service, session_factory):
        """User with reminders disabled → no message sent"""
        _, session = session_factory
        bot = reminder_service.bot

        training = MagicMock()
        training.id = 1
        training.title = "Debate 101"
        training.dt = datetime.now(timezone.utc) + timedelta(hours=24)
        training.location = "Room 101"

        participant = MagicMock()
        participant.tg_id = 12345
        participant.reminders_enabled = False

        with patch("services.reminders.repo") as repo_mock:
            repo_mock.get_upcoming_trainings = AsyncMock(return_value=[training])
            repo_mock.get_training_participants = AsyncMock(return_value=[participant])

            await reminder_service._send_reminders()

        bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_reminder_outside_window_not_sent(self, reminder_service, session_factory):
        """Training in 5 days → no reminder sent"""
        _, session = session_factory
        bot = reminder_service.bot

        training = MagicMock()
        training.id = 1
        training.title = "Debate 101"
        training.dt = datetime.now(timezone.utc) + timedelta(days=5)
        training.location = "Room 101"

        participant = MagicMock()
        participant.tg_id = 12345
        participant.reminders_enabled = True

        with patch("services.reminders.repo") as repo_mock:
            repo_mock.get_upcoming_trainings = AsyncMock(return_value=[training])
            repo_mock.get_training_participants = AsyncMock(return_value=[participant])

            await reminder_service._send_reminders()

        bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_error_logged(self, reminder_service, session_factory):
        """Send failure → error logged, continues"""
        _, session = session_factory
        bot = reminder_service.bot
        bot.send_message = AsyncMock(side_effect=Exception("Network error"))

        training = MagicMock()
        training.id = 1
        training.title = "Debate 101"
        training.dt = datetime.now(timezone.utc) + timedelta(hours=24)
        training.location = "Room 101"

        participant = MagicMock()
        participant.tg_id = 12345
        participant.reminders_enabled = True

        with patch("services.reminders.repo") as repo_mock:
            repo_mock.get_upcoming_trainings = AsyncMock(return_value=[training])
            repo_mock.get_training_participants = AsyncMock(return_value=[participant])

            # Should not raise
            await reminder_service._send_reminders()

        bot.send_message.assert_called_once()

    def test_start_adds_job(self, reminder_service):
        """start() → scheduler job added"""
        reminder_service.scheduler.add_job = MagicMock()
        reminder_service.scheduler.start = MagicMock()

        reminder_service.start()

        reminder_service.scheduler.add_job.assert_called_once()
        call_kwargs = reminder_service.scheduler.add_job.call_args.kwargs
        assert call_kwargs["id"] == "training_reminders"
        reminder_service.scheduler.start.assert_called_once()

    def test_stop_shuts_down_scheduler(self, reminder_service):
        """stop() → scheduler shutdown"""
        reminder_service.scheduler.shutdown = MagicMock()

        reminder_service.stop()

        reminder_service.scheduler.shutdown.assert_called_once_with(wait=False)


# Needed for MagicMock in tests
from unittest.mock import MagicMock  # noqa: F811
