from __future__ import annotations

from pathlib import Path
import ctypes
import sys
import winreg

import webview

from boost_meter_core import AppSettingsStore, OverlayBridgeServer


APP_NAME = "RL Custom UI"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def app_data_dir() -> Path:
    root = Path.home() / "AppData" / "Local" / "RLCustomUI"
    root.mkdir(parents=True, exist_ok=True)
    return root


class Api:
    def __init__(self, settings_store: AppSettingsStore):
        self.settings_store = settings_store

    def sync_startup(self) -> None:
        settings = self.settings_store.load()
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
            if settings.get("launchWithWindows"):
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{sys.executable}"')
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except OSError:
            pass


def main() -> None:
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("RLCustomUI.Desktop")
    except Exception:
        pass

    static_root = app_base_dir()
    data_root = app_data_dir()
    settings_store = AppSettingsStore(data_root / "app-settings.json")
    settings = settings_store.load()
    settings["pollRocketLeagueOnlyWhenRunning"] = True
    settings_store.save(settings)

    server = OverlayBridgeServer(static_root, data_root, app_settings_store=settings_store)
    server.start()

    api = Api(settings_store)
    window = webview.create_window(
        APP_NAME,
        "http://127.0.0.1:8765/desktop-ui.html",
        width=1180,
        height=760,
        min_size=(760, 520),
        background_color="#0d1015",
        js_api=api,
    )

    def on_loaded():
        api.sync_startup()

    def on_closing():
        api.sync_startup()
        server.stop()

    window.events.loaded += on_loaded
    window.events.closed += on_closing
    webview.start(private_mode=False)


if __name__ == "__main__":
    main()
