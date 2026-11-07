"""Pemblokiran shortcut best-effort; kebijakan bersama Qt dan hook Windows."""
import logging
import sys
import threading

# Nama tombol berupa nama kanonis (huruf kapital, ESC, PRINTSCREEN, dll.).
_BLOCK_ALONE = {
    "F1", "F3", "F5", "F6", "F10", "F11", "F12", "PRINTSCREEN", "MENU", "META",
    "BROWSER_BACK", "BROWSER_FORWARD", "BROWSER_REFRESH", "BROWSER_STOP",
    "BROWSER_SEARCH", "BROWSER_FAVORITES", "BROWSER_HOME", "LAUNCH_MAIL", "LAUNCH_APP1", "LAUNCH_APP2",
}
_PRIMARY_KEYS = {"B", "C", "D", "E", "F", "G", "H", "J", "K", "L", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "TAB", "PAGEUP", "PAGEDOWN", "ESC"}
_SHIFT_PRIMARY = {"I", "J", "C", "K", "M", "N", "T", "P", "S", "ESC"}
_ALT_KEYS = {"TAB", "ESC", "F4", "LEFT", "RIGHT", "SPACE", "HOME"}


def should_block(key, modifiers):
    """Aturan umum. 'primary' berarti Ctrl atau Command, tergantung platform."""
    mods = set(modifiers)
    if key in _BLOCK_ALONE:
        return True
    if "primary" in mods and (key in _PRIMARY_KEYS or ("shift" in mods and key in _SHIFT_PRIMARY)):
        return True
    if "alt" in mods and key in _ALT_KEYS:
        return True
    return False


def is_exit_shortcut(key, modifiers):
    """Hanya Ctrl+Shift+Alt+Q; modifier lain membuatnya tidak cocok."""
    return key == "Q" and set(modifiers) == {"primary", "shift", "alt"}


# Windows virtual-key codes. Low-level hook ini memerlukan message loop sendiri.
_VK_SPECIAL = {0x5B: "META", 0x5C: "META", 0x5D: "MENU", 0x2C: "PRINTSCREEN",
               0x1B: "ESC", 0x09: "TAB", 0x21: "PAGEUP", 0x22: "PAGEDOWN",
               0x25: "LEFT", 0x27: "RIGHT", 0x20: "SPACE", 0x24: "HOME",
               0x70: "F1", 0x72: "F3", 0x73: "F4", 0x74: "F5", 0x75: "F6",
               0x79: "F10", 0x7A: "F11", 0x7B: "F12",
               0xA6: "BROWSER_BACK", 0xA7: "BROWSER_FORWARD", 0xA8: "BROWSER_REFRESH",
               0xA9: "BROWSER_STOP", 0xAA: "BROWSER_SEARCH", 0xAB: "BROWSER_FAVORITES",
               0xAC: "BROWSER_HOME", 0xB4: "LAUNCH_MAIL", 0xB6: "LAUNCH_APP1", 0xB7: "LAUNCH_APP2"}
_VK_MODS = {0x11: "primary", 0xA2: "primary", 0xA3: "primary",
            0x10: "shift", 0xA0: "shift", 0xA1: "shift",
            0x12: "alt", 0xA4: "alt", 0xA5: "alt",
            0x5B: "meta", 0x5C: "meta"}


def windows_key(vk):
    if 0x41 <= vk <= 0x5A:
        return chr(vk)
    return _VK_SPECIAL.get(vk, "")


class WindowsKeyState:
    """Logika event terpisah agar perilaku hook dapat diuji tanpa Windows."""
    def __init__(self):
        self.down = set()
        self.swallowed = set()

    def handle(self, vk, is_down, is_up, alt_down=False):
        if is_down:
            repeated = vk in self.down
            self.down.add(vk)
            mods = {_VK_MODS[k] for k in self.down if k in _VK_MODS}
            if alt_down:
                mods.add("alt")
            name = windows_key(vk)
            if is_exit_shortcut(name, mods):
                self.swallowed.add(vk)
                return True, not repeated
            if should_block(name, mods):
                self.swallowed.add(vk)
                return True, False
        elif is_up:
            self.down.discard(vk)
            if vk in self.swallowed:
                self.swallowed.discard(vk)
                return True, False
        return False, False


class WindowsKeyboardGuard:
    """Hook keyboard Windows global selama aplikasi aktif (bukan keamanan absolut)."""
    def __init__(self, on_exit=None):
        self.on_exit = on_exit or (lambda: None)
        self.thread = None
        self.thread_id = 0
        self.ready = threading.Event()
        self.installed = False

    def start(self):
        if sys.platform != "win32":
            return False
        self.thread = threading.Thread(target=self._run, name="NeotestKeyboardHook", daemon=True)
        self.thread.start()
        if not self.ready.wait(5):
            logging.error("Hook keyboard Windows tidak merespons")
            return False
        return self.installed

    def _run(self):
        import ctypes
        from ctypes import wintypes
        user = ctypes.WinDLL("user32", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD),
                        ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                        ("dwExtraInfo", ctypes.c_size_t)]
        LRESULT = ctypes.c_ssize_t
        callback_type = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        user.SetWindowsHookExW.argtypes = [ctypes.c_int, callback_type, wintypes.HINSTANCE, wintypes.DWORD]
        user.SetWindowsHookExW.restype = wintypes.HANDLE
        user.CallNextHookEx.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        user.CallNextHookEx.restype = LRESULT
        user.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
        user.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        user.GetMessageW.restype = wintypes.BOOL
        kernel.GetCurrentThreadId.restype = wintypes.DWORD
        key_state = WindowsKeyState()
        @callback_type
        def callback(code, message, pointer):
            if code < 0:
                return user.CallNextHookEx(None, code, message, pointer)
            try:
                data = ctypes.cast(pointer, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                vk = int(data.vkCode)
                is_down = message in (0x0100, 0x0104)
                is_up = message in (0x0101, 0x0105)
                blocked, exit_requested = key_state.handle(
                    vk, is_down, is_up, alt_down=bool(data.flags & 0x20))
                if exit_requested:
                    self.on_exit()  # hanya mengirim sinyal ke UI thread
                if blocked:
                    return 1
            except Exception:
                logging.exception("Kesalahan callback hook keyboard")
            return user.CallNextHookEx(None, code, message, pointer)
        self.callback = callback  # callback harus tetap hidup selama hook aktif
        self.thread_id = kernel.GetCurrentThreadId()
        hook = user.SetWindowsHookExW(13, callback, None, 0)  # WH_KEYBOARD_LL
        self.installed = bool(hook)
        # Pastikan message queue thread tersedia sebelum stop mengirim WM_QUIT.
        msg = wintypes.MSG()
        user.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
        self.ready.set()
        if not hook:
            logging.error("SetWindowsHookExW gagal: %s", ctypes.get_last_error())
            return
        try:
            while user.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                pass
        finally:
            user.UnhookWindowsHookEx(hook)
            self.installed = False

    def stop(self):
        if sys.platform != "win32" or not self.thread_id:
            return
        import ctypes
        from ctypes import wintypes
        user = ctypes.WinDLL("user32", use_last_error=True)
        user.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user.PostThreadMessageW.restype = wintypes.BOOL
        user.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)  # WM_QUIT
        if self.thread:
            self.thread.join(timeout=3)
