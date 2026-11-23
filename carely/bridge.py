"""Read an HLK-LD2410C radar plugged into this computer over USB-serial and
forward its readings to the Carely server (use this when testing without an ESP32).

    uv run python -m carely.bridge --port /dev/tty.usbserial-0001 --device bathroom
"""

import argparse
import os
import time

import httpx
import serial

from .config import load_settings
from .radar import LD2410Parser


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", required=True, help="serial port, e.g. /dev/tty.usbserial-0001 or COM3")
    ap.add_argument("--device", default="bathroom", help="radar id: bathroom | living | bedroom")
    ap.add_argument("--server", default="http://localhost:8000")
    ap.add_argument("--baud", type=int, default=256000)
    ap.add_argument("--every", type=float, default=0.5, help="seconds between readings sent")
    args = ap.parse_args()

    token = os.environ.get("RADAR_TOKEN") or load_settings().radar_token
    headers = {"X-Radar-Token": token} if token else {}
    parser = LD2410Parser()
    last_sent = 0.0
    latest = None
    with serial.Serial(args.port, args.baud, timeout=0.1) as port, httpx.Client(timeout=5.0) as http:
        print(f"reading {args.port} -> {args.server} as '{args.device}' (Ctrl+C to stop)")
        while True:
            for report in parser.feed(port.read(256)):
                latest = report
            if latest and time.time() - last_sent >= args.every:
                payload = {"device": args.device, **latest}
                try:
                    http.post(f"{args.server}/api/radar", json=payload, headers=headers)
                except httpx.HTTPError as e:
                    print("server not reachable:", e)
                print(payload)
                last_sent = time.time()


if __name__ == "__main__":
    main()
