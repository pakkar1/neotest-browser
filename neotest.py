#!/usr/bin/env python3
"""Neotest Kiosk: tampilkan situs tanpa membaca atau mengubah isi halaman."""
import hashlib
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time

from keyboard_guard import WindowsKeyboardGuard, should_block, is_exit_shortcut
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

APP_NAME = "Neotest"
APP_VERSION = "3.4.0"
# Sesuaikan jika repository GitHub berbeda; harus sama dengan repo untuk build.
GITHUB_REPO = "pakkar1/cakbro-updates"
GITHUB_BRANCH = "main"
DEFAULT_URL = "https://ujikom.pakkar.my.id/2026/09/uji-kompetensi.html"
CONFIG_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/config.json"
RELEASE_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def data_dir():
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    path = base / APP_NAME
    # Versi sebelumnya menggunakan CakBro; tetap pakai data lama apabila ada
    # agar cache URL dan sesi WebEngine tidak hilang saat auto-update.
    legacy = base / "CakBro"
    if not path.exists() and legacy.is_dir():
        path = legacy
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_bytes(url, limit, timeout=12):
    if urlparse(url).scheme != "https":
        raise ValueError("Hanya URL HTTPS yang diterima")
    request = Request(url, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}", "Accept": "application/vnd.github+json"})
    with urlopen(request, timeout=timeout) as response:
        if urlparse(response.geturl()).scheme != "https":
            raise ValueError("Redirect non-HTTPS ditolak")
        result = response.read(limit + 1)
        if len(result) > limit:
            raise ValueError("Respons terlalu besar")
        return result


def validate_home_url(value):
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 32 for c in value):
        raise ValueError("URL tidak valid")
    parts = urlparse(value)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("home_url harus berupa URL HTTPS tanpa kredensial")
    return value


def load_home_url():
    """Ambil konfigurasi GitHub. Jika offline, pakai cache terakhir atau URL bawaan."""
    cache = data_dir() / "config.json"
    try:
        config = json.loads(get_bytes(CONFIG_URL, 65536).decode("utf-8"))
        url = validate_home_url(config["home_url"])
        try:
            temp = cache.with_suffix(".tmp")
            temp.write_text(json.dumps({"home_url": url}), encoding="utf-8")
            os.replace(temp, cache)
        except OSError:
            logging.exception("Cache konfigurasi tidak dapat disimpan")
        return url
    except Exception:
        logging.exception("Konfigurasi GitHub tidak dapat diambil; gunakan cache")
    try:
        return validate_home_url(json.loads(cache.read_text(encoding="utf-8"))["home_url"])
    except Exception:
        return DEFAULT_URL


def version_tuple(value):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value or "")
    return tuple(map(int, match.groups())) if match else None


def asset_name():
    machine = platform.machine().lower()
    if sys.platform == "win32" and machine in ("amd64", "x86_64"):
        return "Neotest-windows-x86_64.exe"
    if sys.platform.startswith("linux") and machine in ("amd64", "x86_64"):
        return "Neotest-linux-x86_64"
    if sys.platform == "darwin":
        if machine in ("arm64", "aarch64"):
            return "Neotest-macos-arm64"
        if machine in ("x86_64", "amd64"):
            return "Neotest-macos-x86_64"
    return None


def checksum_for(text, name):
    for line in text.splitlines():
        match = re.fullmatch(r"([a-fA-F0-9]{64})\s+\*?([^\r\n]+)", line.strip())
        if match and match.group(2) == name:
            return match.group(1).lower()
    raise ValueError("SHA-256 aset tidak ditemukan")


def download_verified(url, destination, expected):
    if urlparse(url).scheme != "https":
        raise ValueError("URL unduhan harus HTTPS")
    request = Request(url, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
    h = hashlib.sha256()
    # File di direktori tujuan agar os.replace tetap dalam filesystem yang sama.
    try:
        with urlopen(request, timeout=60) as response, open(destination, "wb") as out:
            if urlparse(response.geturl()).scheme != "https":
                raise ValueError("Redirect non-HTTPS ditolak")
            total = 0
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                total += len(block)
                if total > 1024 * 1024 * 1024:
                    raise ValueError("Aset terlalu besar")
                h.update(block)
                out.write(block)
        if h.hexdigest() != expected:
            raise ValueError("SHA-256 tidak cocok")
    except Exception:
        Path(destination).unlink(missing_ok=True)
        raise


def stage_update():
    """Cek stable release saat startup. Hanya binary PyInstaller yang diperbarui."""
    if not getattr(sys, "frozen", False):
        return None
    name = asset_name()
    if not name:
        logging.warning("Platform tidak didukung oleh auto-update")
        return None
    target = Path(sys.executable).resolve()
    staged = None
    try:
        release = json.loads(get_bytes(RELEASE_URL, 1024 * 1024).decode("utf-8"))
        remote = version_tuple(release.get("tag_name"))
        current = version_tuple(APP_VERSION)
        if release.get("draft") or release.get("prerelease") or not remote or remote <= current:
            return None
        assets = {x["name"]: x["browser_download_url"] for x in release["assets"]}
        # Hanya tautan aset release di repository sendiri, bukan URL bebas dari manifest.
        prefix = f"https://github.com/{GITHUB_REPO}/releases/download/"
        checksum_url, binary_url = assets["SHA256SUMS.txt"], assets[name]
        if not checksum_url.startswith(prefix) or not binary_url.startswith(prefix):
            raise ValueError("URL aset release bukan dari repository yang dikonfigurasi")
        expected = checksum_for(get_bytes(checksum_url, 65536).decode("utf-8"), name)
        fd, staged = tempfile.mkstemp(prefix=".neotest-update-", dir=str(target.parent))
        os.close(fd)
        download_verified(binary_url, staged, expected)
        if sys.platform != "win32":
            os.chmod(staged, 0o755)
        return staged
    except Exception:
        if staged:
            Path(staged).unlink(missing_ok=True)
        logging.exception("Pemeriksaan/pengunduhan update gagal; gunakan versi saat ini")
        return None


def start_update_helper(staged):
    target = Path(sys.executable).resolve()
    helper = None
    try:
        # Salinan mandiri diperlukan karena executable Windows sedang digunakan.
        directory = tempfile.mkdtemp(prefix="neotest-helper-")
        helper = Path(directory) / target.name
        shutil.copy2(target, helper)
        subprocess.Popen([str(helper), "--apply-update", str(os.getpid()), staged, str(target)],
                         close_fds=True, start_new_session=True)
        return True
    except Exception:
        logging.exception("Helper pembaruan gagal dijalankan")
        Path(staged).unlink(missing_ok=True)
        if helper:
            shutil.rmtree(helper.parent, ignore_errors=True)
        return False


def apply_update(parent, staged, target):
    # Wait for parent process exit. Windows open process handle avoids PID reuse.
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x00100000, False, parent)
        if handle:
            result = kernel.WaitForSingleObject(handle, 120000)
            kernel.CloseHandle(handle)
            if result != 0:
                return 1
    else:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            try:
                os.kill(parent, 0)
            except ProcessLookupError:
                break
            except PermissionError:
                return 1
            time.sleep(0.25)
        else:
            return 1
    installed = False
    for _ in range(15):
        try:
            os.replace(staged, target)
            installed = True
            break
        except OSError:
            time.sleep(1)
    if not installed:
        logging.error("Gagal mengganti binary; jalankan versi lama. Periksa izin folder.")
        Path(staged).unlink(missing_ok=True)
    try:
        subprocess.Popen([target] + ([] if installed else ["--skip-update"]),
                         close_fds=True, start_new_session=True)
    except OSError:
        logging.exception("Gagal memulai ulang aplikasi")
        return 1
    return 0 if installed else 1


def run_gui():
    from PySide6.QtCore import QThread, Signal, QUrl, QObject, QEvent, Qt, QCoreApplication
    from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
    from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
    from PySide6.QtWebEngineWidgets import QWebEngineView

    class KeyFilter(QObject):
        # Qt menerima event saat aplikasi fokus; bukan hook sistem Linux/macOS.
        def __init__(self, exit_signal):
            super().__init__()
            self.exit_signal = exit_signal
            self.swallowed = set()

        def eventFilter(self, watched, event):
            kind = event.type()
            if kind not in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
                return False
            key = event.key()
            special = {
                Qt.Key.Key_F1: "F1", Qt.Key.Key_F3: "F3", Qt.Key.Key_F4: "F4",
                Qt.Key.Key_F5: "F5", Qt.Key.Key_F6: "F6", Qt.Key.Key_F10: "F10",
                Qt.Key.Key_F11: "F11", Qt.Key.Key_F12: "F12",
                Qt.Key.Key_Print: "PRINTSCREEN", Qt.Key.Key_Menu: "MENU",
                Qt.Key.Key_Meta: "META", Qt.Key.Key_Escape: "ESC", Qt.Key.Key_Tab: "TAB",
                Qt.Key.Key_Backtab: "TAB", Qt.Key.Key_PageUp: "PAGEUP", Qt.Key.Key_PageDown: "PAGEDOWN",
                Qt.Key.Key_Left: "LEFT", Qt.Key.Key_Right: "RIGHT", Qt.Key.Key_Space: "SPACE",
                Qt.Key.Key_Home: "HOME",
            }
            name = special.get(key, chr(key) if 65 <= key <= 90 else "")
            flags = event.modifiers()
            mods = set()
            if flags & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                mods.add("primary")
            if flags & Qt.KeyboardModifier.ShiftModifier:
                mods.add("shift")
            if flags & Qt.KeyboardModifier.AltModifier:
                mods.add("alt")
            if kind == QEvent.Type.KeyRelease and key in self.swallowed:
                self.swallowed.discard(key)
                event.accept()
                return True
            exit_mods = set()
            if flags & Qt.KeyboardModifier.ControlModifier:
                exit_mods.add("primary")
            if flags & Qt.KeyboardModifier.MetaModifier:
                exit_mods.add("meta")
            if flags & Qt.KeyboardModifier.ShiftModifier:
                exit_mods.add("shift")
            if flags & Qt.KeyboardModifier.AltModifier:
                exit_mods.add("alt")
            if is_exit_shortcut(name, exit_mods):
                if kind == QEvent.Type.KeyPress:
                    if key not in self.swallowed and not event.isAutoRepeat():
                        self.exit_signal.triggered.emit()
                    self.swallowed.add(key)
                event.accept()
                return True
            if should_block(name, mods):
                if kind == QEvent.Type.KeyPress:
                    self.swallowed.add(key)
                event.accept()
                return True
            return False

    class KioskView(QWebEngineView):
        def createWindow(self, window_type):
            # Tolak permintaan tab atau jendela baru, termasuk window.open.
            return None

    class ExitSignal(QObject):
        triggered = Signal()

    class Startup(QThread):
        def run(self):
            self.home = load_home_url()
            self.staged = None if "--skip-update" in sys.argv else stage_update()

    class Window(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle(APP_NAME)
            self.home = DEFAULT_URL
            self._allow_close = False
            self.box = QWidget()
            self.setCentralWidget(self.box)
            layout = QVBoxLayout(self.box)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            header = QHBoxLayout()
            header.setContentsMargins(8, 4, 8, 4)
            self.home_button = QPushButton("Home")
            self.home_button.setEnabled(False)
            self.home_button.clicked.connect(self.go_home)
            self.status = QLabel("Menyiapkan kiosk dan memeriksa pembaruan…")
            header.addWidget(self.home_button)
            header.addWidget(self.status, 1)
            layout.addLayout(header)
            self.view = KioskView()
            self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
            # Profil terpisah dari browser biasa, dan tetap tersimpan saat Home.
            self.profile = QWebEngineProfile("Neotest", self)
            self.profile.setPersistentStoragePath(str(data_dir() / "web-profile"))
            self.profile.setCachePath(str(data_dir() / "web-cache"))
            self.page = QWebEnginePage(self.profile, self.view)
            self.view.setPage(self.page)
            layout.addWidget(self.view, 1)
            self.worker = Startup(self)
            self.worker.finished.connect(self.start_ready)
            self.worker.start()

        def start_ready(self):
            self.home = getattr(self.worker, "home", DEFAULT_URL)
            staged = getattr(self.worker, "staged", None)
            if staged and start_update_helper(staged):
                # Restart untuk update adalah satu-satunya exit non-interaktif.
                QApplication.exit(0)
                return
            self.status.setText(guard_status)
            self.home_button.setEnabled(True)
            self.go_home()

        def go_home(self):
            self.view.load(QUrl(self.home))

        def request_exit(self):
            # Jangan hancurkan thread saat masih memeriksa jaringan.
            if self.worker.isRunning():
                self.status.setText("Tunggu pemeriksaan awal selesai, lalu tekan Ctrl+Shift+Alt+Q lagi.")
                return
            self._allow_close = True
            self.close()

        def closeEvent(self, event):
            if self._allow_close:
                event.accept()
            else:
                event.ignore()

    # Di macOS, Qt secara default menukar makna Control dan Meta. Pertahankan
    # Ctrl fisik agar kombinasi keluar sesuai permintaan pada semua platform.
    if sys.platform == "darwin":
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_MacDontSwapCtrlAndMeta, True)
    app = QApplication(sys.argv[:1])
    exit_signal = ExitSignal()
    key_filter = KeyFilter(exit_signal)
    app.installEventFilter(key_filter)
    guard = WindowsKeyboardGuard(on_exit=exit_signal.triggered.emit)
    if sys.platform == "win32":
        guard_status = "" if guard.start() else "PERINGATAN: hook keyboard Windows gagal aktif."
    else:
        guard_status = "Pembatasan sistem terbatas: aktifkan kiosk pada OS."
    window = Window()
    exit_signal.triggered.connect(window.request_exit, Qt.ConnectionType.QueuedConnection)
    window.showFullScreen()
    try:
        return app.exec()
    finally:
        guard.stop()


def main():
    if "--version" in sys.argv:
        print(f"{APP_NAME} {APP_VERSION}")
        return 0
    data = data_dir()
    logging.basicConfig(filename=str(data / "neotest.log"), level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    if len(sys.argv) == 5 and sys.argv[1] == "--apply-update":
        return apply_update(int(sys.argv[2]), sys.argv[3], sys.argv[4])
    try:
        return run_gui()
    except Exception:
        logging.exception("Aplikasi gagal dimulai")
        raise

if __name__ == "__main__":
    sys.exit(main())
