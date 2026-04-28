from pathlib import Path
import time
from boost_meter_core import OverlayBridgeServer


def main():
    root = Path(__file__).resolve().parent
    server = OverlayBridgeServer(static_root=root, data_root=root)
    server.start()
    print(f"Rocket League overlay bridge running at http://{server.host}:{server.port}/boost-overlay.html")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()
