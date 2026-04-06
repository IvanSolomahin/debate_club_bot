# tests/test_keyboards.py
import pytest

from keyboards.main_menu import (
    main_menu_keyboard,
    admin_menu_keyboard,
    combined_menu_keyboard,
)


class TestMainMenuKeyboard:
    def test_main_menu_has_user_buttons(self):
        """Main menu contains user-specific buttons"""
        keyboard = main_menu_keyboard()

        callback_data_list = [
            button.callback_data
            for row in keyboard.inline_keyboard
            for button in row
            if button.callback_data
        ]

        assert "user_trainings" in callback_data_list
        assert "user_my" in callback_data_list
        assert "user_cancel" in callback_data_list
        assert "user_reminders" in callback_data_list

    def test_main_menu_layout(self):
        """Main menu has 4 buttons in single column"""
        keyboard = main_menu_keyboard()

        assert len(keyboard.inline_keyboard) == 4
        for row in keyboard.inline_keyboard:
            assert len(row) == 1

    def test_main_menu_callback_prefixes(self):
        """All callbacks start with 'user_'"""
        keyboard = main_menu_keyboard()

        for row in keyboard.inline_keyboard:
            for button in row:
                if button.callback_data:
                    assert button.callback_data.startswith("user_")


class TestAdminMenuKeyboard:
    def test_admin_menu_has_admin_buttons(self):
        """Admin menu contains admin-specific buttons"""
        keyboard = admin_menu_keyboard()

        callback_data_list = [
            button.callback_data
            for row in keyboard.inline_keyboard
            for button in row
            if button.callback_data
        ]

        assert "admin_create_event" in callback_data_list
        assert "admin_edit_event" in callback_data_list
        assert "admin_delete_event" in callback_data_list
        assert "admin_export_participants" in callback_data_list
        assert "admin_broadcast" in callback_data_list
        assert "admin_manage_admins" in callback_data_list

    def test_admin_menu_layout(self):
        """Admin menu has 6 buttons in single column"""
        keyboard = admin_menu_keyboard()

        assert len(keyboard.inline_keyboard) == 6
        for row in keyboard.inline_keyboard:
            assert len(row) == 1

    def test_admin_menu_callback_prefixes(self):
        """All callbacks start with 'admin_'"""
        keyboard = admin_menu_keyboard()

        for row in keyboard.inline_keyboard:
            for button in row:
                if button.callback_data:
                    assert button.callback_data.startswith("admin_")


class TestCombinedMenuKeyboard:
    def test_combined_has_both_sections(self):
        """Combined menu has user and admin buttons"""
        keyboard = combined_menu_keyboard(is_admin=True)

        callback_data_list = [
            button.callback_data
            for row in keyboard.inline_keyboard
            for button in row
            if button.callback_data
        ]

        # User buttons
        assert "user_trainings" in callback_data_list
        assert "user_reminders" in callback_data_list
        # Admin buttons
        assert "admin_create_event" in callback_data_list
        assert "admin_broadcast" in callback_data_list

    def test_combined_has_separator(self):
        """Combined menu has a separator button"""
        keyboard = combined_menu_keyboard(is_admin=True)

        callback_data_list = [
            button.callback_data
            for row in keyboard.inline_keyboard
            for button in row
            if button.callback_data
        ]

        assert "admin_separator" in callback_data_list
