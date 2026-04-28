from __future__ import annotations

from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import cgi
import json
import socket
import subprocess
import threading
import time


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_ROCKET_LEAGUE_HOST = "127.0.0.1"
DEFAULT_ROCKET_LEAGUE_PORT = 49123
DEFAULT_CONFIG = {
    "x": 0,
    "y": 0,
    "size": 270,
    "ringCenterX": 135,
    "ringCenterY": 135,
    "ringRadius": 120,
    "ringStart": 104,
    "ringLength": 535,
    "ringTotal": 760,
    "ringWidth": 17,
    "glowWidth": 24,
    "color": "#64d8ff",
    "numberColor": "#f5fbff",
    "labelColor": "#f5fbff",
    "numberOffsetX": 0,
    "numberOffsetY": 0,
    "labelOffsetX": 0,
    "labelOffsetY": 0,
    "labelText": "BOOST",
    "numberGlowColor": "#ffffff",
    "numberGlowAlpha": 0.88,
    "numberGlowBlur": 12,
    "labelGlowColor": "#ffffff",
    "labelGlowAlpha": 0.2,
    "labelGlowBlur": 4,
    "glowAlpha": 0.28,
    "image": "textures/builtin/style-1/BlueBoost.png",
}
DEFAULT_APP_SETTINGS = {
    "launchWithWindows": False,
    "startInTray": True,
    "pollRocketLeagueOnlyWhenRunning": True,
    "firstLaunchCompleted": False,
}


def is_rocket_league_running() -> bool:
    try:
        startupinfo = None
        creationflags = 0
        if hasattr(subprocess, "STARTUPINFO"):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq RocketLeague.exe"],
            capture_output=True,
            text=True,
            check=False,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
    except OSError:
        return False

    return "RocketLeague.exe" in result.stdout


@dataclass
class BridgeState:
    lock: threading.Lock = field(default_factory=threading.Lock)
    status: str = "starting"
    error: str = ""
    message: dict | None = None
    sequence: int = 0
    rl_running: bool = False
    last_message_at: float = 0.0

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "status": self.status,
                "error": self.error,
                "message": self.message,
                "sequence": self.sequence,
                "rlRunning": self.rl_running,
                "lastMessageAt": self.last_message_at,
            }

    def set_status(self, status: str, error: str = "") -> None:
        with self.lock:
            self.status = status
            self.error = error

    def set_rl_running(self, running: bool) -> None:
        with self.lock:
            self.rl_running = running

    def publish(self, message: dict) -> None:
        with self.lock:
            self.message = message
            self.sequence += 1
            self.status = "connected"
            self.error = ""
            self.last_message_at = time.time()


class ConfigStore:
    def __init__(self, static_root: Path, data_root: Path, config_path: Path | None = None):
        self.static_root = static_root
        self.data_root = data_root
        self.config_path = config_path or data_root / "overlay-config.json"
        self.builtin_texture_dir = static_root / "textures" / "builtin"
        self.custom_texture_dir = data_root / "textures" / "custom"

    def load_config(self) -> dict:
        if not self.config_path.exists():
            self.config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
            return dict(DEFAULT_CONFIG)

        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}

        return self.sanitize_config(data)

    def save_config(self, data: dict) -> dict:
        config = self.sanitize_config(data)
        self.config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        return config

    def sanitize_config(self, data: dict) -> dict:
        config = dict(DEFAULT_CONFIG)
        if isinstance(data, dict):
            config.update({key: data[key] for key in config if key in data})

        numeric_bounds = {
            "x": (-960, 960),
            "y": (-540, 540),
            "size": (100, 700),
            "ringCenterX": (0, 700),
            "ringCenterY": (0, 700),
            "ringRadius": (10, 350),
            "ringStart": (0, 360),
            "ringLength": (0, 1400),
            "ringTotal": (1, 2000),
            "ringWidth": (1, 80),
            "glowWidth": (1, 100),
            "glowAlpha": (0, 1),
            "numberOffsetX": (-180, 180),
            "numberOffsetY": (-180, 180),
            "labelOffsetX": (-180, 180),
            "labelOffsetY": (-180, 180),
            "numberGlowAlpha": (0, 1),
            "numberGlowBlur": (0, 60),
            "labelGlowAlpha": (0, 1),
            "labelGlowBlur": (0, 60),
        }

        for key, (minimum, maximum) in numeric_bounds.items():
            try:
                value = float(config[key])
            except (TypeError, ValueError):
                value = DEFAULT_CONFIG[key]
            value = max(minimum, min(maximum, value))
            config[key] = int(value) if key not in ("glowAlpha", "numberGlowAlpha", "labelGlowAlpha") else value

        for key in ("color", "numberColor", "labelColor", "numberGlowColor", "labelGlowColor"):
            color = str(config.get(key, DEFAULT_CONFIG[key]))
            if not (len(color) == 7 and color.startswith("#")):
                color = DEFAULT_CONFIG[key]
            config[key] = color

        config["labelText"] = str(config.get("labelText", DEFAULT_CONFIG["labelText"]))[:24] or DEFAULT_CONFIG["labelText"]

        image = str(config.get("image", DEFAULT_CONFIG["image"])).replace("\\", "/")
        valid_images = {texture["path"] for texture in self.list_textures()}
        if image not in valid_images:
            image = DEFAULT_CONFIG["image"]
        config["image"] = image
        return config

    def list_textures(self) -> list[dict]:
        textures: list[dict] = []
        directories = (self.builtin_texture_dir, self.custom_texture_dir)
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            for path in sorted(directory.rglob("*.png")):
                if directory == self.builtin_texture_dir:
                    relative_path = path.relative_to(self.static_root).as_posix()
                else:
                    relative_path = path.relative_to(self.data_root).as_posix()
                relative_parts = path.relative_to(directory).parts
                if directory == self.builtin_texture_dir and len(relative_parts) > 1:
                    group = f"builtin/{relative_parts[0]}"
                    label = f"Built-in: {relative_parts[0].replace('-', ' ').title()}"
                elif directory == self.builtin_texture_dir:
                    group = "builtin"
                    label = "Built-in"
                else:
                    group = "custom"
                    label = "Custom"

                textures.append(
                    {
                        "path": relative_path,
                        "name": path.stem,
                        "group": group,
                        "label": label,
                    }
                )
        return textures

    def save_uploaded_texture(self, filename: str, file_data: bytes) -> dict:
        cleaned_name = Path(filename).name
        if not cleaned_name.lower().endswith(".png"):
            raise ValueError("Only .png files are supported.")
        if not cleaned_name:
            raise ValueError("Missing file name.")

        target_dir = self.data_root / "textures" / "custom"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / cleaned_name
        target_path.write_bytes(file_data)

        return {
            "ok": True,
            "path": target_path.relative_to(self.data_root).as_posix(),
            "name": target_path.stem,
        }


class AppSettingsStore:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()

    def load(self) -> dict:
        with self.lock:
            if not self.path.exists():
                self.path.write_text(json.dumps(DEFAULT_APP_SETTINGS, indent=2), encoding="utf-8")
                return dict(DEFAULT_APP_SETTINGS)

            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}

            return self.sanitize(data)

    def save(self, data: dict) -> dict:
        with self.lock:
            settings = self.sanitize(data)
            self.path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
            return settings

    def sanitize(self, data: dict) -> dict:
        settings = dict(DEFAULT_APP_SETTINGS)
        if isinstance(data, dict):
            for key in settings:
                if key in data:
                    settings[key] = bool(data[key])
        return settings


def normalize_message(message):
    if isinstance(message, dict) and isinstance(message.get("Data"), str):
        try:
            message = dict(message)
            message["Data"] = json.loads(message["Data"])
        except json.JSONDecodeError:
            pass
    return message


class RocketLeagueReader(threading.Thread):
    def __init__(
        self,
        state: BridgeState,
        host: str,
        port: int,
        poll_only_when_running: callable | None = None,
    ):
        super().__init__(daemon=True)
        self.state = state
        self.host = host
        self.port = port
        self.poll_only_when_running = poll_only_when_running
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        decoder = json.JSONDecoder()

        while not self._stop_event.is_set():
            should_poll_gate = self.poll_only_when_running() if self.poll_only_when_running else False
            rl_running = is_rocket_league_running()
            self.state.set_rl_running(rl_running)

            if should_poll_gate and not rl_running:
                self.state.set_status("waiting", "Rocket League is not running.")
                self._stop_event.wait(1.0)
                continue

            try:
                self.state.set_status("connecting")
                with socket.create_connection((self.host, self.port), timeout=3) as rl_socket:
                    rl_socket.settimeout(3)
                    self.state.set_status("connected")
                    buffer = ""

                    while not self._stop_event.is_set():
                        chunk = rl_socket.recv(65536)
                        if not chunk:
                            break

                        buffer += chunk.decode("utf-8", errors="replace")
                        while buffer.strip():
                            buffer = buffer.lstrip()
                            try:
                                message, end_index = decoder.raw_decode(buffer)
                            except json.JSONDecodeError:
                                break

                            buffer = buffer[end_index:]
                            self.state.publish(normalize_message(message))

                self._stop_event.wait(0.02)
            except Exception as error:
                rl_running = is_rocket_league_running()
                self.state.set_rl_running(rl_running)
                self.state.set_status("disconnected", str(error))
                self._stop_event.wait(1.0)


class OverlayBridgeServer:
    def __init__(
        self,
        static_root: Path,
        data_root: Path,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        rocket_league_host: str = DEFAULT_ROCKET_LEAGUE_HOST,
        rocket_league_port: int = DEFAULT_ROCKET_LEAGUE_PORT,
        config_path: Path | None = None,
        app_settings_store: AppSettingsStore | None = None,
    ):
        self.static_root = static_root
        self.data_root = data_root
        self.host = host
        self.port = port
        self.rocket_league_host = rocket_league_host
        self.rocket_league_port = rocket_league_port
        self.config_store = ConfigStore(static_root, data_root, config_path)
        self.app_settings_store = app_settings_store
        self.state = BridgeState()
        self.reader = RocketLeagueReader(
            self.state,
            self.rocket_league_host,
            self.rocket_league_port,
            self.should_poll_only_when_running,
        )
        self.server: ThreadingHTTPServer | None = None
        self.server_thread: threading.Thread | None = None

    def should_poll_only_when_running(self) -> bool:
        if not self.app_settings_store:
            return False
        return bool(self.app_settings_store.load()["pollRocketLeagueOnlyWhenRunning"])

    def start(self) -> None:
        if self.server:
            return
        if not self.reader.is_alive():
            self.reader.start()
        handler = self._build_handler()
        self.server = ThreadingHTTPServer((self.host, self.port), handler)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

    def stop(self) -> None:
        if self.reader:
            self.reader.stop()
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.server_thread:
            self.server_thread.join(timeout=2)

    def _build_handler(self):
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return

            def do_GET(self):
                parsed = urlparse(self.path)
                path = parsed.path

                if path == "/events":
                    self.stream_events()
                    return

                if path == "/version":
                    overlay = bridge.static_root / "boost-overlay.html"
                    config_mtime = bridge.config_store.config_path.stat().st_mtime_ns if bridge.config_store.config_path.exists() else 0
                    app_page = bridge.static_root / "desktop-ui.html"
                    app_mtime = app_page.stat().st_mtime_ns if app_page.exists() else 0
                    payload = {"version": overlay.stat().st_mtime_ns + config_mtime + app_mtime}
                    self.send_json(payload)
                    return

                if path == "/config":
                    self.send_json(bridge.config_store.load_config())
                    return

                if path == "/textures":
                    self.send_json(bridge.config_store.list_textures())
                    return

                if path == "/app/settings":
                    settings = bridge.app_settings_store.load() if bridge.app_settings_store else dict(DEFAULT_APP_SETTINGS)
                    self.send_json(settings)
                    return

                if path == "/app/status":
                    self.send_json(
                        {
                            "obsUrl": f"http://{bridge.host}:{bridge.port}/boost-overlay.html",
                            "editorUrl": f"http://{bridge.host}:{bridge.port}/boost-overlay.html?edit=1",
                            "setupUrl": "",
                            "bridge": bridge.state.snapshot(),
                        }
                    )
                    return

                if path in ("", "/"):
                    path = "/boost-overlay.html"

                self.serve_static(path)

            def do_POST(self):
                parsed = urlparse(self.path)
                path = parsed.path

                if path == "/config":
                    incoming = self.read_json_body()
                    if incoming is None:
                        return
                    self.send_json(bridge.config_store.save_config(incoming))
                    return

                if path == "/app/settings":
                    incoming = self.read_json_body()
                    if incoming is None:
                        return
                    if not bridge.app_settings_store:
                        self.send_error(404)
                        return
                    self.send_json(bridge.app_settings_store.save(incoming))
                    return

                if path == "/upload-texture":
                    self.handle_upload_texture()
                    return

                self.send_error(404)

            def read_json_body(self):
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                try:
                    return json.loads(body.decode("utf-8"))
                except json.JSONDecodeError:
                    self.send_error(400)
                    return None

            def handle_upload_texture(self):
                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={"REQUEST_METHOD": "POST"},
                )
                uploaded = form["file"] if "file" in form else None
                if uploaded is None or not getattr(uploaded, "filename", ""):
                    self.send_error(400)
                    return

                try:
                    result = bridge.config_store.save_uploaded_texture(uploaded.filename, uploaded.file.read())
                except ValueError as error:
                    self.send_json({"ok": False, "error": str(error)}, status=400)
                    return

                self.send_json(result)

            def serve_static(self, path: str):
                relative = Path(path.lstrip("/"))
                if relative.parts and relative.parts[0] == "textures" and len(relative.parts) > 1 and relative.parts[1] == "custom":
                    base_root = bridge.data_root
                else:
                    base_root = bridge.static_root

                requested = (base_root / relative).resolve()
                if base_root not in requested.parents and requested != base_root:
                    self.send_error(403)
                    return

                if not requested.exists() or not requested.is_file():
                    self.send_error(404)
                    return

                content_type = "text/html; charset=utf-8"
                if requested.suffix == ".js":
                    content_type = "application/javascript; charset=utf-8"
                elif requested.suffix == ".css":
                    content_type = "text/css; charset=utf-8"
                elif requested.suffix == ".png":
                    content_type = "image/png"
                elif requested.suffix == ".json":
                    content_type = "application/json; charset=utf-8"

                data = requested.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def send_json(self, payload: dict | list, status: int = 200):
                data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def stream_events(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "keep-alive")
                self.end_headers()

                last_sequence = -1
                last_status = None
                last_rl_running = None
                last_heartbeat = 0.0

                while True:
                    snapshot = bridge.state.snapshot()
                    try:
                        if snapshot["status"] != last_status or snapshot["rlRunning"] != last_rl_running:
                            self.write_event(
                                "bridge",
                                {
                                    "status": snapshot["status"],
                                    "error": snapshot["error"],
                                    "rlRunning": snapshot["rlRunning"],
                                },
                            )
                            last_status = snapshot["status"]
                            last_rl_running = snapshot["rlRunning"]

                        if snapshot["message"] is not None and snapshot["sequence"] != last_sequence:
                            self.write_event("message", snapshot["message"])
                            last_sequence = snapshot["sequence"]

                        now = time.time()
                        if now - last_heartbeat > 1:
                            self.write_event("heartbeat", {"time": now})
                            last_heartbeat = now

                        time.sleep(0.02)
                    except (BrokenPipeError, ConnectionResetError):
                        return

            def write_event(self, event_name: str, payload: dict):
                self.wfile.write(f"event: {event_name}\n".encode("utf-8"))
                self.wfile.write(f"data: {json.dumps(payload, separators=(',', ':'))}\n\n".encode("utf-8"))
                self.wfile.flush()

        return Handler
