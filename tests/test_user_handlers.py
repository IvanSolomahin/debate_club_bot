# tests/test_user_handlers.py
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from handlers.user import (
    OnboardingStates,
    cmd_start,
    input_full_name,
    handle_native_yes,
    handle_native_no,
    input_university,
    input_phone,
    input_email,
    input_social,
    skip_social,
    cmd_my,
    view_trainings,
    select_training_to_register,
    confirm_registration,
    cancel_registration_from_list,
    select_training_to_cancel,
    confirm_cancellation,
    cmd_reminders,
    toggle_reminders,
)


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def message():
    m = AsyncMock(spec=Message)
    m.from_user = MagicMock(id=12345)
    m.text = "test text"
    m.answer = AsyncMock()
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
def native_callback():
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = MagicMock(id=12345)
    cb.data = "native_yes"
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
    with patch("handlers.user.repo") as mock:
        mock.get_user_by_tg_id = AsyncMock()
        mock.create_user = AsyncMock()
        mock.update_user = AsyncMock()
        mock.get_upcoming_trainings = AsyncMock()
        mock.get_training_by_id = AsyncMock()
        mock.register_user_for_training = AsyncMock()
        mock.cancel_registration = AsyncMock()
        mock.get_user_registrations = AsyncMock()
        mock.is_registered = AsyncMock()
        yield mock


@pytest.fixture
def session():
    return AsyncMock()


# ── UC-01 Onboarding tests ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cmd_start_new_user_not_registered(message, session, repo_mock, state):
    """New user → ask for full name"""
    repo_mock.get_user_by_tg_id = AsyncMock(return_value=None)

    await cmd_start(message, state, session)

    state.set_state.assert_called_once()
    message.answer.assert_called_once()
    call_args = message.answer.call_args
    assert "Как вас зовут" in call_args.args[0] or "имя" in call_args.args[0].lower()


@pytest.mark.asyncio
async def test_cmd_start_existing_user(message, session, repo_mock, state):
    """Registered user → welcome back message"""
    mock_user = MagicMock()
    mock_user.full_name = "Test User"
    repo_mock.get_user_by_tg_id = AsyncMock(return_value=mock_user)

    await cmd_start(message, state, session)

    state.set_state.assert_not_called()
    message.answer.assert_called_once()
    call_args = message.answer.call_args
    assert "рады" in call_args.args[0].lower() or "снова" in call_args.args[0].lower()


@pytest.mark.asyncio
async def test_input_full_name(message, state):
    """Store full name → ask if from native org"""
    message.text = "Ivan Ivanov"

    await input_full_name(message, state)

    state.update_data.assert_called_once_with(full_name="Ivan Ivanov")
    state.set_state.assert_called_once()
    message.answer.assert_called_once()


@pytest.mark.asyncio
async def test_handle_native_yes(native_callback, state):
    """User is from native org → ask for university"""
    await handle_native_yes(native_callback, state)

    state.update_data.assert_called_once_with(is_native=True)
    state.set_state.assert_called_once()
    native_callback.message.answer.assert_called_once()


@pytest.mark.asyncio
async def test_handle_native_no(callback, state):
    """User is not from native org → ask for university"""
    callback.data = "native_no"
    await handle_native_no(callback, state)

    state.update_data.assert_called_once_with(is_native=False)
    state.set_state.assert_called_once()
    callback.message.answer.assert_called_once()


@pytest.mark.asyncio
async def test_input_university(message, state):
    """Store university → ask for phone"""
    message.text = "HSE"

    await input_university(message, state)

    state.update_data.assert_called_once_with(university="HSE")
    state.set_state.assert_called_once()
    message.answer.assert_called_once()


@pytest.mark.asyncio
async def test_input_phone(message, state):
    """Store phone → ask for email"""
    message.text = "+79991234567"

    await input_phone(message, state)

    state.update_data.assert_called_once_with(phone="+79991234567")
    state.set_state.assert_called_once()
    message.answer.assert_called_once()


@pytest.mark.asyncio
async def test_input_email(message, state):
    """Store email → ask for social"""
    message.text = "test@example.com"

    await input_email(message, state)

    state.update_data.assert_called_once_with(email="test@example.com")
    state.set_state.assert_called_once()
    message.answer.assert_called_once()


@pytest.mark.asyncio
async def test_input_social(message, state, session, repo_mock):
    """Store social → create user → finish"""
    message.text = "@telegram_user"
    message.from_user = MagicMock(id=12345, username="testuser")
    # Simulate state storing social_url and then returning it in get_data
    stored_data = {
        "full_name": "Ivan Ivanov",
        "is_native": True,
        "university": "HSE",
        "phone": "+79991234567",
        "email": "test@example.com",
    }

    async def mock_update_data(**kwargs):
        stored_data.update(kwargs)

    state.update_data = AsyncMock(side_effect=mock_update_data)
    state.get_data = AsyncMock(side_effect=lambda: stored_data.copy())

    mock_user = MagicMock()
    mock_user.full_name = "Ivan Ivanov"
    repo_mock.create_user = AsyncMock(return_value=mock_user)

    await input_social(message, state, session)

    repo_mock.create_user.assert_called_once()
    call_kwargs = repo_mock.create_user.call_args.kwargs
    assert call_kwargs["full_name"] == "Ivan Ivanov"
    assert call_kwargs["tg_id"] == 12345
    assert call_kwargs["social_url"] == "@telegram_user"

    state.clear.assert_called_once()
    message.answer.assert_called_once()


@pytest.mark.asyncio
async def test_finish_onboarding_via_input_social(message, state, session, repo_mock):
    """Social input → create user → finish"""
    message.text = "@telegram_user"
    message.from_user = MagicMock(id=12345, username="testuser")
    stored_data = {
        "full_name": "Ivan Ivanov",
        "is_native": True,
        "university": "HSE",
        "phone": "+79991234567",
        "email": "test@example.com",
    }

    async def mock_update_data(**kwargs):
        stored_data.update(kwargs)

    state.update_data = AsyncMock(side_effect=mock_update_data)
    state.get_data = AsyncMock(side_effect=lambda: stored_data.copy())

    mock_user = MagicMock()
    mock_user.full_name = "Ivan Ivanov"
    repo_mock.create_user = AsyncMock(return_value=mock_user)

    from handlers.user import input_social
    await input_social(message, state, session)

    repo_mock.create_user.assert_called_once()
    call_kwargs = repo_mock.create_user.call_args.kwargs
    assert call_kwargs["full_name"] == "Ivan Ivanov"
    assert call_kwargs["tg_id"] == 12345
    assert call_kwargs["social_url"] == "@telegram_user"

    state.clear.assert_called_once()
    message.answer.assert_called_once()


# ── UC-02 View trainings tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_view_trainings_no_upcoming(callback, session, repo_mock):
    """No upcoming trainings → friendly message"""
    repo_mock.get_upcoming_trainings = AsyncMock(return_value=[])

    await view_trainings(callback, session)

    callback.message.answer.assert_called_once()
    call_args = callback.message.answer.call_args
    assert "нет" in call_args.args[0].lower() or "предстоя" in call_args.args[0].lower()
    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_view_trainings_with_upcoming(callback, session, repo_mock):
    """Upcoming trainings → list with inline buttons"""
    mock_training = MagicMock()
    mock_training.id = 1
    mock_training.title = "Debate 101"
    mock_training.dt = datetime.now(timezone.utc) + timedelta(days=1)
    mock_training.location = "Room 101"
    repo_mock.get_upcoming_trainings = AsyncMock(return_value=[mock_training])

    await view_trainings(callback, session)

    callback.message.answer.assert_called_once()
    call_args = callback.message.answer.call_args
    assert "reply_markup" in call_args.kwargs
    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_view_trainings_shows_registered_status(callback, session, repo_mock):
    """Registered training shows 'already registered' status"""
    mock_training = MagicMock()
    mock_training.id = 1
    mock_training.title = "Debate 101"
    mock_training.dt = datetime.now(timezone.utc) + timedelta(days=1)
    mock_training.location = "Room 101"
    repo_mock.get_upcoming_trainings = AsyncMock(return_value=[mock_training])
    repo_mock.is_registered = AsyncMock(return_value=True)

    await view_trainings(callback, session)

    callback.message.answer.assert_called_once()
    call_args = callback.message.answer.call_args
    # Should indicate already registered
    text = call_args.args[0]
    assert "уже записаны" in text.lower() or "записаны" in text.lower()


# ── UC-03 Register for training tests ──────────────────────────────────────

@pytest.mark.asyncio
async def test_select_training_to_register_already_registered(callback, state, session, repo_mock):
    """Already registered → informative message"""
    callback.data = "register:1"
    state.get_data = AsyncMock(return_value={"action": "register"})
    repo_mock.is_registered = AsyncMock(return_value=True)

    mock_training = MagicMock()
    mock_training.id = 1
    mock_training.title = "Debate 101"
    mock_training.dt = datetime.now(timezone.utc) + timedelta(days=1)
    mock_training.location = "Room 101"
    repo_mock.get_training_by_id = AsyncMock(return_value=mock_training)

    await select_training_to_register(callback, state, session)

    callback.message.answer.assert_called_once()
    call_args = callback.message.answer.call_args
    assert "уже записаны" in call_args.args[0].lower()
    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_select_training_to_register_not_found(callback, state, session, repo_mock):
    """Training not found → error message"""
    callback.data = "register:999"
    state.get_data = AsyncMock(return_value={"action": "register"})
    repo_mock.is_registered = AsyncMock(return_value=False)
    repo_mock.get_training_by_id = AsyncMock(return_value=None)

    await select_training_to_register(callback, state, session)

    callback.message.answer.assert_called_once()
    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_select_training_to_register_success(callback, state, session, repo_mock):
    """Show confirmation keyboard"""
    callback.data = "register:1"
    state.get_data = AsyncMock(return_value={"action": "register"})
    repo_mock.is_registered = AsyncMock(return_value=False)

    mock_training = MagicMock()
    mock_training.id = 1
    mock_training.title = "Debate 101"
    mock_training.dt = datetime.now(timezone.utc) + timedelta(days=1)
    mock_training.location = "Room 101"
    repo_mock.get_training_by_id = AsyncMock(return_value=mock_training)

    await select_training_to_register(callback, state, session)

    callback.message.answer.assert_called_once()
    call_args = callback.message.answer.call_args
    assert "reply_markup" in call_args.kwargs
    state.update_data.assert_called_once_with(training_id=1, action="register")
    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_confirm_registration_yes(callback, state, session, repo_mock):
    """Confirm → register user → success message"""
    callback.data = "reg_confirm:yes"
    callback.from_user = MagicMock(id=12345)
    state.get_data = AsyncMock(return_value={"training_id": 1, "action": "register"})
    repo_mock.register_user_for_training = AsyncMock(return_value=(MagicMock(), "ok"))

    await confirm_registration(callback, state, session)

    repo_mock.register_user_for_training.assert_called_once_with(session, 12345, 1)
    callback.message.answer.assert_called_once()
    call_args = callback.message.answer.call_args
    assert "записаны" in call_args.args[0].lower()
    state.clear.assert_called_once()
    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_confirm_registration_already_registered(callback, state, session, repo_mock):
    """Already registered → friendly message"""
    callback.data = "reg_confirm:yes"
    callback.from_user = MagicMock(id=12345)
    state.get_data = AsyncMock(return_value={"training_id": 1, "action": "register"})
    repo_mock.register_user_for_training = AsyncMock(return_value=(None, "already_registered"))

    await confirm_registration(callback, state, session)

    callback.message.answer.assert_called_once()
    call_args = callback.message.answer.call_args
    assert "уже записаны" in call_args.args[0].lower()
    state.clear.assert_called_once()


@pytest.mark.asyncio
async def test_confirm_registration_cancel(callback, state, session):
    """User cancels → clear state"""
    callback.data = "reg_confirm:no"

    await confirm_registration(callback, state, session)

    state.clear.assert_called_once()
    callback.answer.assert_called_once()


# ── UC-04 Cancel registration tests ────────────────────────────────────────

@pytest.mark.asyncio
async def test_cancel_registration_from_list_no_registrations(callback, session, repo_mock):
    """No registrations → friendly message"""
    callback.data = "my_cancel"
    repo_mock.get_user_registrations = AsyncMock(return_value=[])

    await cancel_registration_from_list(callback, session)

    callback.message.answer.assert_called_once()
    call_args = callback.message.answer.call_args
    assert "нет" in call_args.args[0].lower() or "запис" in call_args.args[0].lower()
    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_registration_from_list_with_registrations(callback, session, repo_mock):
    """Has registrations → show list with cancel buttons"""
    mock_reg = MagicMock()
    mock_reg.training = MagicMock()
    mock_reg.training.id = 1
    mock_reg.training.title = "Debate 101"
    mock_reg.training.dt = datetime.now(timezone.utc) + timedelta(days=1)
    repo_mock.get_user_registrations = AsyncMock(return_value=[mock_reg])

    await cancel_registration_from_list(callback, session)

    callback.message.answer.assert_called_once()
    call_args = callback.message.answer.call_args
    assert "reply_markup" in call_args.kwargs
    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_select_training_to_cancel(callback, state, session, repo_mock):
    """Show confirmation for cancellation"""
    callback.data = "cancel:1"

    mock_training = MagicMock()
    mock_training.id = 1
    mock_training.title = "Debate 101"
    mock_training.dt = datetime.now(timezone.utc) + timedelta(days=1)
    repo_mock.get_training_by_id = AsyncMock(return_value=mock_training)
    repo_mock.is_registered = AsyncMock(return_value=True)

    await select_training_to_cancel(callback, state, session)

    callback.message.answer.assert_called_once()
    call_args = callback.message.answer.call_args
    assert "reply_markup" in call_args.kwargs
    state.update_data.assert_called_once()
    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_confirm_cancellation_yes(callback, state, session, repo_mock):
    """Confirm → cancel registration → success"""
    callback.data = "cancel_confirm:yes"
    callback.from_user = MagicMock(id=12345)
    state.get_data = AsyncMock(return_value={"training_id": 1, "action": "cancel"})
    repo_mock.cancel_registration = AsyncMock(return_value=True)

    await confirm_cancellation(callback, state, session)

    repo_mock.cancel_registration.assert_called_once_with(session, 12345, 1)
    callback.message.answer.assert_called_once()
    call_args = callback.message.answer.call_args
    assert "отменена" in call_args.args[0].lower() or "запись отменена" in call_args.args[0].lower()
    state.clear.assert_called_once()
    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_confirm_cancellation_no(callback, state, session):
    """User cancels → clear state"""
    callback.data = "cancel_confirm:no"

    await confirm_cancellation(callback, state, session)

    state.clear.assert_called_once()
    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_confirm_cancellation_failed(callback, state, session, repo_mock):
    """Cancellation fails → error message"""
    callback.data = "cancel_confirm:yes"
    callback.from_user = MagicMock(id=12345)
    state.get_data = AsyncMock(return_value={"training_id": 1, "action": "cancel"})
    repo_mock.cancel_registration = AsyncMock(return_value=False)

    await confirm_cancellation(callback, state, session)

    callback.message.answer.assert_called_once()
    call_args = callback.message.answer.call_args
    assert "не удалось" in call_args.args[0].lower() or "ошибка" in call_args.args[0].lower()
    state.clear.assert_called_once()


# ── UC-05 Manage reminders tests ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_cmd_reminders_enabled(message, session, repo_mock):
    """Reminders enabled → show toggle with 'enabled' status"""
    mock_user = MagicMock()
    mock_user.reminders_enabled = True
    repo_mock.get_user_by_tg_id = AsyncMock(return_value=mock_user)

    await cmd_reminders(message, session)

    message.answer.assert_called_once()
    call_args = message.answer.call_args
    assert "включены" in call_args.args[0].lower() or "enabled" in call_args.args[0].lower()


@pytest.mark.asyncio
async def test_cmd_reminders_disabled(message, session, repo_mock):
    """Reminders disabled → show toggle with 'disabled' status"""
    mock_user = MagicMock()
    mock_user.reminders_enabled = False
    repo_mock.get_user_by_tg_id = AsyncMock(return_value=mock_user)

    await cmd_reminders(message, session)

    message.answer.assert_called_once()
    call_args = message.answer.call_args
    assert "отключены" in call_args.args[0].lower() or "disabled" in call_args.args[0].lower()


@pytest.mark.asyncio
async def test_toggle_reminders_enable(callback, state, session, repo_mock):
    """Enable reminders → update user → success"""
    callback.data = "reminders:enable"
    callback.from_user = MagicMock(id=12345)
    mock_user = MagicMock()
    mock_user.reminders_enabled = False
    repo_mock.get_user_by_tg_id = AsyncMock(return_value=mock_user)
    repo_mock.update_user = AsyncMock(return_value=mock_user)

    await toggle_reminders(callback, state, session)

    repo_mock.update_user.assert_called_once_with(session, 12345, reminders_enabled=True)
    callback.message.answer.assert_called_once()
    call_args = callback.message.answer.call_args
    assert "включены" in call_args.args[0].lower()
    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_toggle_reminders_disable(callback, state, session, repo_mock):
    """Disable reminders → update user → success"""
    callback.data = "reminders:disable"
    callback.from_user = MagicMock(id=12345)
    mock_user = MagicMock()
    mock_user.reminders_enabled = True
    repo_mock.get_user_by_tg_id = AsyncMock(return_value=mock_user)
    repo_mock.update_user = AsyncMock(return_value=mock_user)

    await toggle_reminders(callback, state, session)

    repo_mock.update_user.assert_called_once_with(session, 12345, reminders_enabled=False)
    callback.message.answer.assert_called_once()
    call_args = callback.message.answer.call_args
    assert "отключены" in call_args.args[0].lower()
    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_toggle_reminders_user_not_found(callback, state, session, repo_mock):
    """User not found → error"""
    callback.data = "reminders:enable"
    callback.from_user = MagicMock(id=12345)
    repo_mock.get_user_by_tg_id = AsyncMock(return_value=None)

    await toggle_reminders(callback, state, session)

    repo_mock.update_user.assert_not_called()
    callback.message.answer.assert_called_once()
    callback.answer.assert_called_once()


# ── /my command tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cmd_my_no_registrations(message, session, repo_mock):
    """No registrations → friendly message"""
    message.from_user = MagicMock(id=12345)
    repo_mock.get_user_registrations = AsyncMock(return_value=[])

    await cmd_my(message, session)

    message.answer.assert_called_once()
    call_args = message.answer.call_args
    assert "нет" in call_args.args[0].lower() or "запис" in call_args.args[0].lower()


@pytest.mark.asyncio
async def test_cmd_my_with_registrations(message, session, repo_mock):
    """Has registrations → list them"""
    message.from_user = MagicMock(id=12345)
    mock_reg = MagicMock()
    mock_reg.training = MagicMock()
    mock_reg.training.title = "Debate 101"
    mock_reg.training.dt = datetime.now(timezone.utc) + timedelta(days=1)
    mock_reg.training.location = "Room 101"
    repo_mock.get_user_registrations = AsyncMock(return_value=[mock_reg])

    await cmd_my(message, session)

    message.answer.assert_called_once()
    call_args = message.answer.call_args
    assert "Debate 101" in call_args.args[0]
