from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu for regular users."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Просмотр мастерок", callback_data="user_trainings")
    builder.button(text="📝 Мои записи", callback_data="user_my")
    builder.button(text="❌ Отменить запись", callback_data="user_cancel")
    builder.button(text="🔔 Напоминания", callback_data="user_reminders")
    builder.adjust(1)
    return builder.as_markup()


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu for admin users."""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Создать событие", callback_data="admin_create_event")
    builder.button(text="✏️ Редактировать", callback_data="admin_edit_event")
    builder.button(text="🗑 Удалить событие", callback_data="admin_delete_event")
    builder.button(text="📊 Экспорт участников", callback_data="admin_export_participants")
    builder.button(text="📢 Рассылка", callback_data="admin_broadcast")
    builder.button(text="👤 Управление админами", callback_data="admin_manage_admins")
    builder.adjust(1)
    return builder.as_markup()


def combined_menu_keyboard(is_admin: bool) -> InlineKeyboardMarkup:
    """Combined menu for users who are both regular and admin."""
    builder = InlineKeyboardBuilder()
    # User buttons
    builder.button(text="📋 Просмотр мастерок", callback_data="user_trainings")
    builder.button(text="📝 Мои записи", callback_data="user_my")
    builder.button(text="❌ Отменить запись", callback_data="user_cancel")
    builder.button(text="🔔 Напоминания", callback_data="user_reminders")
    # Separator
    builder.button(text="───── Админ-панель ─────", callback_data="admin_separator")
    # Admin buttons
    builder.button(text="➕ Создать событие", callback_data="admin_create_event")
    builder.button(text="✏️ Редактировать", callback_data="admin_edit_event")
    builder.button(text="🗑 Удалить событие", callback_data="admin_delete_event")
    builder.button(text="📊 Экспорт участников", callback_data="admin_export_participants")
    builder.button(text="📢 Рассылка", callback_data="admin_broadcast")
    builder.button(text="👤 Управление админами", callback_data="admin_manage_admins")
    builder.adjust(1)
    return builder.as_markup()
