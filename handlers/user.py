# handlers/user.py
from datetime import datetime, timezone
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

import repo
from config import settings
from keyboards.main_menu import main_menu_keyboard


router = Router()


# ── States ──────────────────────────────────────────────────────────────────

class OnboardingStates(StatesGroup):
    waiting_full_name = State()
    waiting_native = State()
    waiting_university = State()
    waiting_phone = State()
    waiting_email = State()
    waiting_social = State()


# ── Helpers ─────────────────────────────────────────────────────────────────

def _format_training_info(training) -> str:
    """Format training details for display"""
    dt = training.dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt_str = dt.astimezone().strftime("%d.%m.%Y %H:%M")
    return f"📅 **{training.title}**\n🕐 {dt_str}\n📍 {training.location or 'Не указано'}"


def _generate_trainings_keyboard(trainings, registered_map, action_prefix: str) -> InlineKeyboardMarkup:
    """Generate inline keyboard for trainings list"""
    builder = InlineKeyboardBuilder()
    for t in trainings:
        status = " ✅" if registered_map.get(t.id, False) else ""
        builder.button(
            text=f"{t.title}{status}",
            callback_data=f"{action_prefix}:{t.id}"
        )
    builder.adjust(1)
    return builder.as_markup()


def _generate_confirmation_keyboard(yes_callback: str, no_callback: str) -> InlineKeyboardMarkup:
    """Generate yes/no confirmation keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data=yes_callback)],
        [InlineKeyboardButton(text="❌ Нет", callback_data=no_callback)],
    ])


# ── UC-01 Onboarding ───────────────────────────────────────────────────────

@router.message(F.command == "start")
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Handle /start command — onboarding for new users, welcome for existing"""
    if message.from_user is None:
        return

    tg_id = message.from_user.id
    existing_user = await repo.get_user_by_tg_id(session, tg_id)

    if existing_user:
        keyboard = main_menu_keyboard()
        await message.answer(
            f"👋 Рады видеть вас снова, {existing_user.full_name}!\n"
            f"Используйте кнопки меню для навигации.",
            reply_markup=keyboard,
        )
        return

    await state.set_state(OnboardingStates.waiting_full_name)
    await message.answer(
        "👋 Добро пожаловать в клуб дебатов!\n\n"
        "Давайте познакомимся. Как вас зовут? (Имя и фамилия)"
    )


@router.message(OnboardingStates.waiting_full_name)
async def input_full_name(message: Message, state: FSMContext) -> None:
    if message.text is None:
        return
    await state.update_data(full_name=message.text.strip())
    await state.set_state(OnboardingStates.waiting_native)

    org_name = settings.NATIVE_ORG_NAME
    await message.answer(
        f"Вы являетесь членом организации {org_name}?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data="native_yes")],
            [InlineKeyboardButton(text="❌ Нет", callback_data="native_no")],
        ])
    )


@router.callback_query(F.data == "native_yes")
async def handle_native_yes(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(is_native=True)
    await state.set_state(OnboardingStates.waiting_university)
    await callback.message.answer("Укажите ваш университет/учебное заведение:")
    await callback.answer()


@router.callback_query(F.data == "native_no")
async def handle_native_no(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(is_native=False)
    await state.set_state(OnboardingStates.waiting_university)
    await callback.message.answer("Укажите ваш университет/учебное заведение:")
    await callback.answer()


@router.message(OnboardingStates.waiting_university)
async def input_university(message: Message, state: FSMContext) -> None:
    if message.text is None:
        return
    await state.update_data(university=message.text.strip())
    await state.set_state(OnboardingStates.waiting_phone)
    await message.answer("Укажите ваш номер телефона (например: +79991234567):")


@router.message(OnboardingStates.waiting_phone)
async def input_phone(message: Message, state: FSMContext) -> None:
    if message.text is None:
        return
    await state.update_data(phone=message.text.strip())
    await state.set_state(OnboardingStates.waiting_email)
    await message.answer("Укажите ваш email:")


@router.message(OnboardingStates.waiting_email)
async def input_email(message: Message, state: FSMContext) -> None:
    if message.text is None:
        return
    await state.update_data(email=message.text.strip())
    await state.set_state(OnboardingStates.waiting_social)
    await message.answer(
        "Укажите ссылку на соцсеть или Telegram (например: @username или https://vk.com/id123).\n"
        "Можно пропустить кнопкой ниже.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="social_skip")],
        ])
    )


@router.message(OnboardingStates.waiting_social)
async def input_social(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if message.text is None or message.from_user is None:
        return
    await state.update_data(social_url=message.text.strip())
    await _create_user_and_finish(message, state, session)


@router.callback_query(F.data == "social_skip", OnboardingStates.waiting_social)
async def skip_social(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await _create_user_and_finish(callback.message, state, session, is_callback=True)


async def _create_user_and_finish(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    is_callback: bool = False,
) -> None:
    """Create user in DB and finish onboarding"""
    if message.from_user is None:
        return

    data = await state.get_data()

    user = await repo.create_user(
        session=session,
        tg_id=message.from_user.id,
        username=message.from_user.username,
        full_name=data["full_name"],
        is_native=data["is_native"],
        university=data.get("university"),
        phone=data.get("phone"),
        email=data.get("email"),
        social_url=data.get("social_url"),
    )

    await state.clear()
    await message.answer(
        f"🎉 Отлично, {user.full_name}! Регистрация завершена.\n"
        f"Теперь вы можете записываться на мастерки и управлять напоминаниями."
    )


# ── UC-02 View trainings ───────────────────────────────────────────────────

@router.callback_query(F.data == "user_trainings")
async def view_trainings(callback: CallbackQuery, session: AsyncSession) -> None:
    """Show list of upcoming trainings"""
    trainings = await repo.get_upcoming_trainings(session)

    if not trainings:
        await callback.message.answer(
            "📭 На данный момент нет предстоящих мастерок.\n"
            "Следите за объявлениями!"
        )
        await callback.answer()
        return

    # Check which trainings user is registered for
    registered_map = {}
    if callback.from_user:
        for t in trainings:
            is_reg = await repo.is_registered(session, callback.from_user.id, t.id)
            registered_map[t.id] = is_reg

    keyboard = _generate_trainings_keyboard(trainings, registered_map, "register")

    lines = []
    for t in trainings:
        dt = t.dt
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt_str = dt.astimezone().strftime("%d.%m %H:%M")
        status = " ✅ Вы записаны" if registered_map.get(t.id) else ""
        lines.append(f"📅 **{t.title}** — {dt_str}, {t.location or 'ТБА'}{status}")

    text = "📋 **Предстоящие мастерки:**\n\n" + "\n\n".join(lines)

    await callback.message.answer(
        text,
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("register:"))
async def select_training_to_register(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """Show registration confirmation for selected training"""
    if callback.data is None or callback.from_user is None:
        return

    training_id = int(callback.data.split(":")[1])
    training = await repo.get_training_by_id(session, training_id)

    if training is None:
        await callback.message.answer("❌ Мастерка не найдена.")
        await callback.answer()
        return

    # Check if already registered
    is_reg = await repo.is_registered(session, callback.from_user.id, training_id)
    if is_reg:
        dt = training.dt
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt_str = dt.astimezone().strftime("%d.%m %H:%M")
        await callback.message.answer(
            f"ℹ️ Вы уже записаны на **{training.title}** ({dt_str})."
        )
        await callback.answer()
        return

    await state.update_data(training_id=training_id, action="register")

    dt = training.dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt_str = dt.astimezone().strftime("%d.%m %H:%M")

    desc_line = f"\n📝 Описание: {training.description}" if training.description else ""
    await callback.message.answer(
        f"📝 Записаться на мастерку?\n\n"
        f"**{training.title}**\n"
        f"🕐 {dt_str}\n"
        f"📍 {training.location or 'Не указано'}"
        f"{desc_line}",
        reply_markup=_generate_confirmation_keyboard("reg_confirm:yes", "reg_confirm:no"),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "reg_confirm:yes")
async def confirm_registration(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """Confirm and register user for training"""
    if callback.from_user is None:
        return

    data = await state.get_data()
    training_id = data.get("training_id")

    if training_id is None:
        await callback.message.answer("❌ Ошибка: мастерка не выбрана.")
        await state.clear()
        await callback.answer()
        return

    reg, status = await repo.register_user_for_training(
        session, callback.from_user.id, training_id
    )

    if status == "ok":
        await callback.message.answer("✅ Вы успешно записаны на мастерку!")
    elif status == "already_registered":
        await callback.message.answer("ℹ️ Вы уже записаны на эту мастерку.")
    else:
        await callback.message.answer("❌ Не удалось записаться. Попробуйте позже.")

    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "reg_confirm:no")
async def cancel_registration_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    """User declined registration"""
    await callback.message.answer("👌 Запись отменена.")
    await state.clear()
    await callback.answer()


# ── UC-04 Cancel registration ──────────────────────────────────────────────

@router.callback_query(F.data == "user_cancel")
async def cancel_registration_from_list(callback: CallbackQuery, session: AsyncSession) -> None:
    """Show list of user's registrations to cancel"""
    if callback.from_user is None:
        return

    registrations = await repo.get_user_registrations(session, callback.from_user.id)

    if not registrations:
        await callback.message.answer(
            "📭 У вас нет записей на предстоящие мастерки.\n"
            "Используйте /trainings, чтобы увидеть предстоящие события."
        )
        await callback.answer()
        return

    # Filter to only future trainings and build keyboard
    future_regs = []
    for reg in registrations:
        if reg.training and reg.training.dt >= datetime.now(timezone.utc):
            future_regs.append(reg)

    if not future_regs:
        await callback.message.answer(
            "📭 У вас нет записей на предстоящие мастерки."
        )
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()
    for reg in future_regs:
        t = reg.training
        dt = t.dt
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt_str = dt.astimezone().strftime("%d.%m %H:%M")
        builder.button(
            text=f"❌ {t.title} ({dt_str})",
            callback_data=f"cancel:{t.id}"
        )
    builder.adjust(1)

    await callback.message.answer(
        "📋 Ваши записи на мастерки. Выберите, чтобы отменить:",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cancel:"))
async def select_training_to_cancel(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """Show cancellation confirmation"""
    if callback.data is None:
        return

    training_id = int(callback.data.split(":")[1])
    training = await repo.get_training_by_id(session, training_id)

    if training is None:
        await callback.message.answer("❌ Мастерка не найдена.")
        await callback.answer()
        return

    await state.update_data(training_id=training_id, action="cancel")

    dt = training.dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt_str = dt.astimezone().strftime("%d.%m %H:%M")

    await callback.message.answer(
        f"Отменить запись на мастерку?\n\n"
        f"**{training.title}**\n"
        f"🕐 {dt_str}\n"
        f"📍 {training.location or 'Не указано'}",
        reply_markup=_generate_confirmation_keyboard("cancel_confirm:yes", "cancel_confirm:no"),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_confirm:yes")
async def confirm_cancellation(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """Confirm and cancel registration"""
    if callback.from_user is None:
        return

    data = await state.get_data()
    training_id = data.get("training_id")

    if training_id is None:
        await callback.message.answer("❌ Ошибка: мастерка не выбрана.")
        await state.clear()
        await callback.answer()
        return

    result = await repo.cancel_registration(session, callback.from_user.id, training_id)

    if result:
        await callback.message.answer("✅ Запись отменена.")
    else:
        await callback.message.answer("❌ Не удалось отменить запись. Возможно, вы не были записаны.")

    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "cancel_confirm:no")
async def cancel_cancellation_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    """User declined cancellation"""
    await callback.message.answer("👌 Отмена отменена.")
    await state.clear()
    await callback.answer()


# ── UC-05 Manage reminders ─────────────────────────────────────────────────

@router.callback_query(F.data == "user_reminders")
@router.message(F.command == "reminders")
async def cmd_reminders(message: Message, session: AsyncSession) -> None:
    """Show current reminders status with toggle button"""
    if message.from_user is None:
        return

    user = await repo.get_user_by_tg_id(session, message.from_user.id)

    if user is None:
        await message.answer("❌ Вы не зарегистрированы. Используйте /start.")
        return

    status_text = "включены" if user.reminders_enabled else "отключены"
    emoji = "🔔" if user.reminders_enabled else "🔕"

    action = "disable" if user.reminders_enabled else "enable"
    action_text = "Отключить" if user.reminders_enabled else "Включить"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{action_text} напоминания", callback_data=f"reminders:{action}")],
    ])

    await message.answer(
        f"{emoji} Напоминания сейчас **{status_text}**.\n"
        f"Они приходят за 24 часа и за 1 час до начала мастерки.",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


@router.callback_query(F.data.startswith("reminders:"))
async def toggle_reminders(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """Toggle reminders on/off"""
    if callback.from_user is None or callback.data is None:
        return

    action = callback.data.split(":")[1]
    new_value = action == "enable"

    user = await repo.get_user_by_tg_id(session, callback.from_user.id)
    if user is None:
        await callback.message.answer("❌ Вы не зарегистрированы.")
        await callback.answer()
        return

    await repo.update_user(session, callback.from_user.id, reminders_enabled=new_value)

    status_text = "включены" if new_value else "отключены"
    emoji = "🔔" if new_value else "🔕"

    await callback.message.answer(f"{emoji} Напоминания {status_text}.")
    await callback.answer()


# ── /my command — show user's registrations ────────────────────────────────

@router.message(F.command == "my")
async def cmd_my(message: Message, session: AsyncSession) -> None:
    """Show user's upcoming registrations"""
    if message.from_user is None:
        return

    registrations = await repo.get_user_registrations(session, message.from_user.id)

    if not registrations:
        await message.answer(
            "📭 У вас нет записей на мастерки.\n"
            "Используйте /trainings, чтобы увидеть предстоящие события."
        )
        return

    lines = []
    for reg in registrations:
        t = reg.training
        if t is None:
            continue
        # Only show future trainings
        dt = t.dt
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if dt < datetime.now(timezone.utc):
            continue

        dt_str = dt.astimezone().strftime("%d.%m %H:%M")
        lines.append(f"📅 **{t.title}** — {dt_str}, {t.location or 'ТБА'}")

    if not lines:
        await message.answer("📭 У вас нет записей на предстоящие мастерки.")
        return

    text = "📋 **Ваши записи на мастерки:**\n\n" + "\n\n".join(lines)
    await message.answer(text, parse_mode="Markdown")


# ── /my command from inline button ─────────────────────────────────────────

@router.callback_query(F.data == "user_my")
async def cmd_my_from_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    """Show user's upcoming registrations from menu button."""
    if callback.from_user is None:
        return

    registrations = await repo.get_user_registrations(session, callback.from_user.id)

    if not registrations:
        await callback.message.answer(
            "📭 У вас нет записей на мастерки.\n"
            "Используйте /trainings, чтобы увидеть предстоящие события."
        )
        await callback.answer()
        return

    lines = []
    for reg in registrations:
        t = reg.training
        if t is None:
            continue
        # Only show future trainings
        dt = t.dt
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if dt < datetime.now(timezone.utc):
            continue

        dt_str = dt.astimezone().strftime("%d.%m %H:%M")
        lines.append(f"📅 **{t.title}** — {dt_str}, {t.location or 'ТБА'}")

    if not lines:
        await callback.message.answer("📭 У вас нет записей на предстоящие мастерки.")
        await callback.answer()
        return

    text = "📋 **Ваши записи на мастерки:**\n\n" + "\n\n".join(lines)
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()


# ── /cancel command ─────────────────────────────────────────────────────────

@router.message(F.command == "cancel")
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Cancel current FSM state and show main menu."""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("ℹ️ Нет активного состояния для отмены.")
        return

    await state.clear()
    await message.answer(
        "✅ Операция отменена.",
        reply_markup=main_menu_keyboard(),
    )


# ── Fallback for unknown messages ───────────────────────────────────────────

@router.message()
async def echo_unknown(message: Message, state: FSMContext) -> None:
    """Handle messages when not in FSM state — show main menu."""
    current_state = await state.get_state()
    # Only respond if not in any FSM state (let FSM handlers handle their states)
    if current_state is not None:
        return

    await message.answer(
        "🤔 Я не понимаю эту команду. Используйте кнопки меню для навигации.",
        reply_markup=main_menu_keyboard(),
    )

