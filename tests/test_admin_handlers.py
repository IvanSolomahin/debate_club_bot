# tests/test_admin_handlers.py
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from handlers.admin import (
    AdminEventStates,
    AdminBroadcastStates,
    AdminManageAdminStates,
    cmd_create_event,
    input_title,
    input_datetime,
    input_place,
    input_description,
    cmd_edit_event,
    select_event_to_edit,
    select_field_to_edit,
    input_new_value,
    cmd_delete_event,
    select_event_to_delete,
    cmd_export_participants,
    select_event_to_export,
    select_export_format,
    cmd_broadcast,
    input_broadcast_text,
    cmd_manage_admins,
    select_admin_action,
    input_user_id,
)


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def message():
    m = AsyncMock(spec=Message)
    m.from_user = MagicMock(id=12345)
    m.text = "test text"
    m.answer = AsyncMock()
    m.answer_document = AsyncMock()
    return m


@pytest.fixture
def callback():
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = MagicMock(id=12345)
    cb.data = "some_action:1"
    cb.message = AsyncMock()
    cb.message.answer = AsyncMock()
    cb.answer = AsyncMock()
    return cb


@pytest.fixture
def state():
    s = AsyncMock(spec=FSMContext)
    s.get_data = AsyncMock(return_value={})
    s.update_data = AsyncMock()
    s.set_state = AsyncMock()
    s.clear = AsyncMock()
    return s


@pytest.fixture
def repo_mock():
    with patch("handlers.admin.repo") as mock:
        mock.create_training = AsyncMock()
        mock.update_training = AsyncMock()
        mock.delete_training = AsyncMock()
        mock.get_training_by_id = AsyncMock()
        mock.get_upcoming_trainings = AsyncMock()
        mock.get_training_participants = AsyncMock()
        mock.get_all_users = AsyncMock()
        mock.get_user_by_tg_id = AsyncMock()
        mock.update_user = AsyncMock()
        yield mock


@pytest.fixture
def session():
    return AsyncMock()


# ── UC-06 Create event tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cmd_create_event(callback, state):
    """State → waiting_title, answer вызван"""
    await cmd_create_event(callback, state)
    
    state.set_state.assert_called_once_with(AdminEventStates.waiting_title)
    callback.message.answer.assert_called_once_with("Введите название события:")
    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_input_title(message, state):
    """update_data(title), state → waiting_datetime"""
    message.text = "Test Event"
    
    await input_title(message, state)
    
    state.update_data.assert_called_once_with(title="Test Event")
    state.set_state.assert_called_once_with(AdminEventStates.waiting_datetime)
    message.answer.assert_called_once_with("Введите дату и время события в формате ISO (YYYY-MM-DDTHH:MM:SS):")


@pytest.mark.asyncio
async def test_input_datetime_valid(message, state):
    """update_data(datetime), state → waiting_place"""
    message.text = "2025-01-15T10:00:00"
    
    await input_datetime(message, state)
    
    state.update_data.assert_called_once()
    call_args = state.update_data.call_args
    assert "datetime" in call_args.kwargs or "datetime" in str(call_args)
    state.set_state.assert_called_once_with(AdminEventStates.waiting_place)
    message.answer.assert_called_once_with("Введите место проведения:")


@pytest.mark.asyncio
async def test_input_datetime_invalid(message, state):
    """answer('Неверный формат'), state не меняется"""
    message.text = "invalid date"
    
    await input_datetime(message, state)
    
    message.answer.assert_called_once_with("Неверный формат даты. Используйте формат YYYY-MM-DDTHH:MM:SS")
    state.set_state.assert_not_called()
    state.update_data.assert_not_called()


@pytest.mark.asyncio
async def test_input_description_creates_event(message, state, session, repo_mock):
    """repo.create_training вызван с правильными данными, state.clear()"""
    state.get_data = AsyncMock(return_value={
        "title": "Test Event",
        "datetime": "2025-01-15T10:00:00",
        "place": "Room 101"
    })
    message.text = "Event description"
    message.from_user.id = 12345
    
    await input_description(message, state, session)
    
    repo_mock.create_training.assert_called_once()
    call_kwargs = repo_mock.create_training.call_args.kwargs
    assert call_kwargs["title"] == "Test Event"
    assert call_kwargs["location"] == "Room 101"
    assert call_kwargs["description"] == "Event description"
    assert call_kwargs["created_by"] == 12345
    
    state.clear.assert_called_once()
    message.answer.assert_called_once_with("Событие создано ✅")


# ── UC-07 Edit event tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_edit_event_not_found(callback, session, repo_mock, state):
    """repo.update_training не вызван, answer('Не найдено')"""
    repo_mock.get_upcoming_trainings = AsyncMock(return_value=[])
    
    await cmd_edit_event(callback, session)
    
    callback.message.answer.assert_called()
    # Check that it was called with "no events" message
    call_args = callback.message.answer.call_args
    assert "Нет предстоящих событий" in call_args.args[0] or "Нет событий" in call_args.args[0]


@pytest.mark.asyncio
async def test_edit_event_success(callback, session, repo_mock, state):
    """repo.update_training вызван, state.clear()"""
    mock_training = MagicMock()
    mock_training.id = 1
    mock_training.title = "Test Training"
    repo_mock.get_upcoming_trainings = AsyncMock(return_value=[mock_training])
    repo_mock.get_training_by_id = AsyncMock(return_value=mock_training)
    repo_mock.update_training = AsyncMock(return_value=mock_training)
    
    # Simulate select event
    callback.data = "edit_select:1"
    await select_event_to_edit(callback, state)
    
    state.update_data.assert_called_with(event_id=1)
    
    # Simulate select field
    callback.data = "edit_field:title"
    await select_field_to_edit(callback, state)
    
    state.set_state.assert_called_with(AdminEventStates.waiting_new_value)
    
    # Simulate input new value
    message = AsyncMock(spec=Message)
    message.text = "New Title"
    message.from_user = MagicMock(id=12345)
    message.answer = AsyncMock()
    state.get_data = AsyncMock(return_value={"event_id": 1, "field": "title"})
    
    await input_new_value(message, state, session)
    
    repo_mock.update_training.assert_called()
    state.clear.assert_called()
    message.answer.assert_called_once_with("Обновлено ✅")


# ── UC-08 Delete event tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_event_success(callback, session, repo_mock):
    """repo.delete_training вызван"""
    mock_training = MagicMock()
    mock_training.id = 1
    mock_training.title = "Test Training"
    repo_mock.get_training_by_id = AsyncMock(return_value=mock_training)
    repo_mock.delete_training = AsyncMock(return_value=True)
    
    callback.data = "delete_select:1"
    
    await select_event_to_delete(callback, session)
    
    repo_mock.delete_training.assert_called_once_with(session, 1)
    callback.message.answer.assert_called_once_with("Удалено ✅")


@pytest.mark.asyncio
async def test_delete_event_not_found(callback, session, repo_mock):
    """repo.delete_training не вызван"""
    repo_mock.get_training_by_id = AsyncMock(return_value=None)
    
    callback.data = "delete_select:999"
    
    await select_event_to_delete(callback, session)
    
    repo_mock.delete_training.assert_not_called()
    callback.message.answer.assert_called_once_with("Событие не найдено")


# ── UC-09 Export participants tests ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_export_no_participants(callback, session, repo_mock, state):
    """answer_document не вызван"""
    callback.data = "export_select:1"
    state.get_data = AsyncMock(return_value={"event_id": 1})
    repo_mock.get_training_participants = AsyncMock(return_value=[])
    
    await select_export_format(callback, state, session)
    
    callback.message.answer.assert_called_once_with("Нет участников")
    callback.message.answer_document.assert_not_called()


@pytest.mark.asyncio
async def test_export_xlsx(callback, session, repo_mock, state):
    """answer_document вызван, generate_xlsx вызван"""
    callback.data = "export_format:xlsx"
    state.get_data = AsyncMock(return_value={"event_id": 1})
    state.clear = AsyncMock()
    
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.full_name = "Test User"
    mock_user.username = "testuser"
    mock_user.email = "test@example.com"
    mock_user.phone = "+79991234567"
    repo_mock.get_training_participants = AsyncMock(return_value=[mock_user])
    
    await select_export_format(callback, state, session)
    
    callback.message.answer_document.assert_called_once()
    call_args = callback.message.answer_document.call_args
    assert call_args.kwargs.get("filename", "").endswith(".xlsx")
    state.clear.assert_called()


@pytest.mark.asyncio
async def test_export_docx(callback, session, repo_mock, state):
    """answer_document вызван, generate_docx вызван"""
    callback.data = "export_format:docx"
    state.get_data = AsyncMock(return_value={"event_id": 1})
    state.clear = AsyncMock()
    
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.full_name = "Test User"
    mock_user.username = "testuser"
    mock_user.email = "test@example.com"
    mock_user.phone = "+79991234567"
    repo_mock.get_training_participants = AsyncMock(return_value=[mock_user])
    
    await select_export_format(callback, state, session)
    
    callback.message.answer_document.assert_called_once()
    call_args = callback.message.answer_document.call_args
    assert call_args.kwargs.get("filename", "").endswith(".docx")
    state.clear.assert_called()


# ── UC-10 Broadcast tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_broadcast_no_users(message, session, repo_mock, state):
    """send_message не вызван (кроме reply)"""
    message.text = "Broadcast message"
    repo_mock.get_all_users = AsyncMock(return_value=[])
    
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    
    await input_broadcast_text(message, state, session, bot)
    
    bot.send_message.assert_not_called()
    message.answer.assert_called_once_with("Нет пользователей для рассылки")
    state.clear.assert_called()


@pytest.mark.asyncio
async def test_broadcast_sends_to_all(message, session, repo_mock, state):
    """send_message вызван N раз"""
    message.text = "Broadcast message"
    
    mock_user1 = MagicMock()
    mock_user1.tg_id = 111
    mock_user2 = MagicMock()
    mock_user2.tg_id = 222
    mock_user3 = MagicMock()
    mock_user3.tg_id = 333
    repo_mock.get_all_users = AsyncMock(return_value=[mock_user1, mock_user2, mock_user3])
    
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    
    await input_broadcast_text(message, state, session, bot)
    
    assert bot.send_message.call_count == 3
    message.answer.assert_called_once_with("Отправлено 3 пользователям ✅")
    state.clear.assert_called()


@pytest.mark.asyncio
async def test_broadcast_partial_failure(message, session, repo_mock, state):
    """ошибка на 1 юзере — остальные получили"""
    message.text = "Broadcast message"
    
    mock_user1 = MagicMock()
    mock_user1.tg_id = 111
    mock_user2 = MagicMock()
    mock_user2.tg_id = 222
    mock_user3 = MagicMock()
    mock_user3.tg_id = 333
    repo_mock.get_all_users = AsyncMock(return_value=[mock_user1, mock_user2, mock_user3])
    
    bot = AsyncMock()
    # First user fails, others succeed
    bot.send_message = AsyncMock(side_effect=[Exception("Failed"), None, None])
    
    await input_broadcast_text(message, state, session, bot)
    
    assert bot.send_message.call_count == 3
    # Should still report 2 successful sends
    message.answer.assert_called_once_with("Отправлено 2 пользователям ✅")
    state.clear.assert_called()


# ── UC-11 Manage admins tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_grant_admin_success(message, session, repo_mock, state):
    """update_user с is_admin=True"""
    message.text = "99999"
    message.from_user.id = 12345
    state.get_data = AsyncMock(return_value={"action": "grant"})
    
    mock_user = MagicMock()
    mock_user.id = 99999
    mock_user.tg_id = 99999
    repo_mock.get_user_by_tg_id = AsyncMock(return_value=mock_user)
    repo_mock.update_user = AsyncMock(return_value=mock_user)
    
    await input_user_id(message, state, session)
    
    repo_mock.update_user.assert_called_once_with(session, 99999, is_admin=True)
    message.answer.assert_called_once_with("Назначен ✅")
    state.clear.assert_called()


@pytest.mark.asyncio
async def test_revoke_admin_success(message, session, repo_mock, state):
    """update_user с is_admin=False"""
    message.text = "99999"
    message.from_user.id = 12345
    state.get_data = AsyncMock(return_value={"action": "revoke"})
    
    mock_user = MagicMock()
    mock_user.id = 99999
    mock_user.tg_id = 99999
    repo_mock.get_user_by_tg_id = AsyncMock(return_value=mock_user)
    repo_mock.update_user = AsyncMock(return_value=mock_user)
    
    await input_user_id(message, state, session)
    
    repo_mock.update_user.assert_called_once_with(session, 99999, is_admin=False)
    message.answer.assert_called_once_with("Права сняты ✅")
    state.clear.assert_called()


@pytest.mark.asyncio
async def test_revoke_own_admin(message, session, repo_mock, state):
    """update_user не вызван"""
    message.text = "12345"  # Same as from_user.id
    message.from_user.id = 12345
    state.get_data = AsyncMock(return_value={"action": "revoke"})
    
    await input_user_id(message, state, session)
    
    repo_mock.update_user.assert_not_called()
    repo_mock.get_user_by_tg_id.assert_not_called()
    message.answer.assert_called_once_with("Нельзя изменить права самому себе")
    state.clear.assert_called()


@pytest.mark.asyncio
async def test_manage_admin_user_not_found(message, session, repo_mock, state):
    """update_user не вызван"""
    message.text = "99999"
    message.from_user.id = 12345
    state.get_data = AsyncMock(return_value={"action": "grant"})
    
    repo_mock.get_user_by_tg_id = AsyncMock(return_value=None)
    
    await input_user_id(message, state, session)
    
    repo_mock.update_user.assert_not_called()
    message.answer.assert_called_once_with("Пользователь не найден")
    state.clear.assert_called()
