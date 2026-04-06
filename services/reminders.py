import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import repo

logger = logging.getLogger(__name__)


class ReminderService:
    """Sends reminder notifications for upcoming trainings."""

    def __init__(
        self,
        bot: Bot,
        session_factory: async_sessionmaker,
        reminder_hours: list[int] | None = None,
    ) -> None:
        self.bot = bot
        self.session_factory = session_factory
        self.reminder_hours = reminder_hours or [24, 1]
        self.scheduler = AsyncIOScheduler()

    async def _send_reminders(self) -> None:
        """Scan upcoming trainings and send reminders to registered users."""
        async with self.session_factory() as session:
            trainings = await repo.get_upcoming_trainings(session)

        now = datetime.now(timezone.utc)

        for training in trainings:
            dt = training.dt
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            time_until = dt - now

            for hours_before in self.reminder_hours:
                # Check if we're within the reminder window (±5 min tolerance)
                target = timedelta(hours=hours_before)
                tolerance = timedelta(minutes=5)

                if abs(time_until - target) > tolerance:
                    continue

                # Get participants who have reminders enabled
                async with self.session_factory() as session:
                    participants = await repo.get_training_participants(
                        session, training.id
                    )

                for participant in participants:
                    if not participant.reminders_enabled:
                        continue

                    dt_display = dt.astimezone().strftime("%d.%m.%Y %H:%M")
                    if hours_before >= 24:
                        text = (
                            f"🔔 Напоминание: завтра мастерка **"
                            f"{training.title}"
                            f"**!\n\n"
                            f"🕐 {dt_display}\n"
                            f"📍 {training.location or 'Не указано'}"
                        )
                    else:
                        text = (
                            f"🔔 Напоминание: мастерка **"
                            f"{training.title}"
                            f"** начнётся через час!\n\n"
                            f"🕐 {dt_display}\n"
                            f"📍 {training.location or 'Не указано'}"
                        )

                    try:
                        await self.bot.send_message(
                            participant.tg_id, text, parse_mode="Markdown"
                        )
                        logger.info(
                            "Reminder sent to user %d for training %d",
                            participant.tg_id,
                            training.id,
                        )
                    except Exception as e:
                        logger.error(
                            "Failed to send reminder to user %d: %s",
                            participant.tg_id,
                            e,
                        )

    def start(self) -> None:
        """Start the scheduler job (runs every 5 minutes)."""
        self.scheduler.add_job(
            self._send_reminders,
            "interval",
            minutes=5,
            id="training_reminders",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info("Reminder scheduler started (checking every 5 minutes)")

    def stop(self) -> None:
        """Stop the scheduler."""
        self.scheduler.shutdown(wait=False)
        logger.info("Reminder scheduler stopped")
