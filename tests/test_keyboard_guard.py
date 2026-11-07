import unittest
from unittest.mock import patch
import keyboard_guard as guard

class KeyboardGuardTests(unittest.TestCase):
    def test_standalone_block(self):
        for key in ('F1', 'F3', 'F5', 'F6', 'F10', 'F11', 'F12', 'PRINTSCREEN', 'META', 'MENU', 'BROWSER_BACK', 'BROWSER_HOME', 'LAUNCH_APP1'):
            self.assertTrue(guard.should_block(key, set()), key)
        self.assertFalse(guard.should_block('A', set()))
        self.assertFalse(guard.should_block('F4', set()))

    def test_primary_and_shift_shortcuts(self):
        for key in ('B', 'C', 'E', 'F', 'G', 'K', 'Q', 'V', 'X', 'T', 'N', 'W', 'U', 'S', 'P', 'TAB', 'ESC'):
            self.assertTrue(guard.should_block(key, {'primary'}), key)
        for key in ('I', 'J', 'C', 'K', 'M', 'S', 'ESC'):
            self.assertTrue(guard.should_block(key, {'primary', 'shift'}), key)
        self.assertFalse(guard.should_block('I', {'primary'}))
        self.assertFalse(guard.should_block('A', {'primary'}))

    def test_alt_shortcuts(self):
        for key in ('TAB', 'ESC', 'F4', 'LEFT', 'RIGHT', 'SPACE'):
            self.assertTrue(guard.should_block(key, {'alt'}), key)
        self.assertFalse(guard.should_block('F4', {'shift'}))

    def test_windows_vk_translation(self):
        self.assertEqual(guard.windows_key(0x5b), 'META')  # Win kiri
        self.assertEqual(guard.windows_key(0x5c), 'META')  # Win kanan
        self.assertTrue(guard.should_block(guard.windows_key(0x5b), set()))
        self.assertTrue(guard.should_block(guard.windows_key(0x5c), set()))
        self.assertEqual(guard.windows_key(0xa6), 'BROWSER_BACK')
        self.assertEqual(guard.windows_key(0xac), 'BROWSER_HOME')
        self.assertEqual(guard.windows_key(0xb6), 'LAUNCH_APP1')
        self.assertEqual(guard.windows_key(0x2c), 'PRINTSCREEN')
        self.assertEqual(guard.windows_key(0x43), 'C')
        self.assertEqual(guard.windows_key(0x7b), 'F12')
        self.assertEqual(guard.windows_key(0), '')

    def test_non_windows_does_not_claim_global_protection(self):
        with patch.object(guard.sys, 'platform', 'linux'):
            hook = guard.WindowsKeyboardGuard()
            self.assertFalse(hook.start())
            hook.stop()

    def test_only_exact_exit_combination(self):
        self.assertTrue(guard.is_exit_shortcut('Q', {'primary', 'shift', 'alt'}))
        self.assertFalse(guard.is_exit_shortcut('Q', {'primary', 'shift'}))
        self.assertFalse(guard.is_exit_shortcut('Q', {'primary', 'shift', 'alt', 'meta'}))
        self.assertFalse(guard.is_exit_shortcut('W', {'primary', 'shift', 'alt'}))

    def test_windows_exit_is_not_blocked_by_control_q_policy(self):
        state = guard.WindowsKeyState()
        for vk in (0xA2, 0xA0, 0xA4):  # left Ctrl, Shift, Alt
            self.assertEqual(state.handle(vk, True, False), (False, False))
        self.assertEqual(state.handle(0x51, True, False), (True, True))
        self.assertEqual(state.handle(0x51, True, False), (True, False))  # auto-repeat
        self.assertEqual(state.handle(0xA2, False, True), (False, False))
        self.assertEqual(state.handle(0x51, False, True), (True, False))

    def test_windows_other_control_q_does_not_exit(self):
        state = guard.WindowsKeyState()
        state.handle(0xA2, True, False)
        self.assertEqual(state.handle(0x51, True, False), (True, False))
        self.assertEqual(state.handle(0x51, False, True), (True, False))

    def test_windows_exit_rejects_extra_windows_modifier(self):
        state = guard.WindowsKeyState()
        self.assertEqual(state.handle(0x5b, True, False), (True, False))
        for vk in (0xA2, 0xA0, 0xA4):
            state.handle(vk, True, False)
        self.assertEqual(state.handle(0x51, True, False), (True, False))

if __name__ == '__main__':
    unittest.main()
