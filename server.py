from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import socket
import threading
import time


HOST = "127.0.0.1"
PORT = 8765
ROCKET_LEAGUE_HOST = "127.0.0.1"
ROCKET_LEAGUE_PORT = 49123
ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "overlay-config.json"
TEXTURE_DIRS = (ROOT / "textures" / "builtin", ROOT / "textures" / "custom")
STATE_LOCK = threading.Lock()
STATE = {
    "status": "starting",
    "error": "",
    "message": None,
    "sequence": 0
}
DEFAULT_CONFIG = {
    "x": 32,
    "y": 32,
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
    "glowAlpha": 0.28,
    "image": "textures/builtin/style-1/BlueBoost.png"
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        path = self.path.split("?", 1)[0]

        if path == "/events":
            self.stream_events()
            return

        if path == "/version":
            overlay = ROOT / "boost-overlay.html"
            config_mtime = CONFIG_PATH.stat().st_mtime_ns if CONFIG_PATH.exists() else 0
            payload = json.dumps({"version": overlay.stat().st_mtime_ns + config_mtime}, separators=(",", ":")).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if path == "/config":
            payload = json.dumps(load_config(), separators=(",", ":")).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if path == "/textures":
            payload = json.dumps(list_textures(), separators=(",", ":")).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if path in ("", "/"):
            path = "/boost-overlay.html"

        requested = (ROOT / path.lstrip("/")).resolve()
        if ROOT not in requested.parents and requested != ROOT:
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

        data = requested.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path != "/config":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        try:
            incoming = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(400)
            return

        config = sanitize_config(incoming)
        CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
        payload = json.dumps(config, separators=(",", ":")).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def stream_events(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        last_sequence = -1
        last_status = None
        last_heartbeat = 0.0

        while True:
            with STATE_LOCK:
                snapshot = dict(STATE)

            try:
                if snapshot["status"] != last_status:
                    self.write_event("bridge", {
                        "status": snapshot["status"],
                        "error": snapshot["error"]
                    })
                    last_status = snapshot["status"]

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

    def write_event(self, event_name, payload):
        self.wfile.write(f"event: {event_name}\n".encode("utf-8"))
        self.wfile.write(f"data: {json.dumps(payload, separators=(',', ':'))}\n\n".encode("utf-8"))
        self.wfile.flush()


def normalize_message(message):
    if isinstance(message, dict) and isinstance(message.get("Data"), str):
        try:
            message = dict(message)
            message["Data"] = json.loads(message["Data"])
        except json.JSONDecodeError:
            pass

    return message


def set_bridge_state(status, error=""):
    with STATE_LOCK:
        STATE["status"] = status
        STATE["error"] = error


def publish_message(message):
    with STATE_LOCK:
        STATE["message"] = message
        STATE["sequence"] += 1
        STATE["status"] = "connected"
        STATE["error"] = ""


def rocket_league_reader():
    decoder = json.JSONDecoder()

    while True:
        try:
            set_bridge_state("connecting")
            with socket.create_connection((ROCKET_LEAGUE_HOST, ROCKET_LEAGUE_PORT), timeout=3) as rl_socket:
                rl_socket.settimeout(3)
                set_bridge_state("connected")
                buffer = ""

                while True:
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
                        publish_message(normalize_message(message))

            time.sleep(0.02)
        except Exception as error:
            set_bridge_state("disconnected", str(error))
            time.sleep(1.0)


def load_config():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
        return dict(DEFAULT_CONFIG)

    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = {}

    return sanitize_config(data)


def sanitize_config(data):
    config = dict(DEFAULT_CONFIG)
    if isinstance(data, dict):
        config.update({key: data[key] for key in config if key in data})

    numeric_bounds = {
        "x": (0, 1800),
        "y": (0, 1000),
        "size": (100, 700),
        "ringCenterX": (0, 700),
        "ringCenterY": (0, 700),
        "ringRadius": (10, 350),
        "ringStart": (0, 360),
        "ringLength": (0, 1400),
        "ringTotal": (1, 2000),
        "ringWidth": (1, 80),
        "glowWidth": (1, 100),
        "glowAlpha": (0, 1)
    }

    for key, (minimum, maximum) in numeric_bounds.items():
        try:
            value = float(config[key])
        except (TypeError, ValueError):
            value = DEFAULT_CONFIG[key]
        value = max(minimum, min(maximum, value))
        config[key] = int(value) if key != "glowAlpha" else value

    for key in ("color", "numberColor", "labelColor"):
        color = str(config.get(key, DEFAULT_CONFIG[key]))
        if not (len(color) == 7 and color.startswith("#")):
            color = DEFAULT_CONFIG[key]
        config[key] = color

    image = str(config.get("image", DEFAULT_CONFIG["image"])).replace("\\", "/")
    valid_images = {texture["path"] for texture in list_textures()}
    if image not in valid_images:
        image = DEFAULT_CONFIG["image"]
    config["image"] = image

    return config


def list_textures():
    textures = []
    for directory in TEXTURE_DIRS:
        directory.mkdir(parents=True, exist_ok=True)
        for path in sorted(directory.rglob("*.png")):
            relative_path = path.relative_to(ROOT).as_posix()
            relative_parts = path.relative_to(directory).parts
            if directory.name == "builtin" and len(relative_parts) > 1:
                group = f"builtin/{relative_parts[0]}"
                label = f"Built-in: {relative_parts[0].replace('-', ' ').title()}"
            elif directory.name == "builtin":
                group = "builtin"
                label = "Built-in"
            else:
                group = "custom"
                label = "Custom"

            textures.append({
                "path": relative_path,
                "name": path.stem,
                "group": group,
                "label": label
            })
    return textures


def main():
    threading.Thread(target=rocket_league_reader, daemon=True).start()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Rocket League overlay bridge running at http://{HOST}:{PORT}/boost-overlay.html")
    server.serve_forever()


if __name__ == "__main__":
    main()
