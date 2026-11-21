"""Optional real-browser smoke for Habitat's local room (no production models).
Requirements, supplied by caller: Node.js, Puppeteer, local Chromium/Edge.
Environment: HABITAT_BROWSER_BINARY, optional PUPPETEER_MODULE.
No third-party Python packages are needed.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from vera_habitat.local_room import HTML, RoomHandler, RoomServer

UNTRUSTED = '<img src="missing-image.png" onerror="window.habitatInjected=true"> model text'


class UnsafeNegativeControl(RoomHandler):
    """Intentionally insecure synthetic HTML, for test sensitivity only."""

    def do_GET(self) -> None:
        if self.path != "/":
            return super().do_GET()
        if not self.allowed_request():
            return self.send(403, {"error": "loopback origin required"})
        safe = "p.append(strong,document.createTextNode(text));"
        vulnerable = 'p.append(strong);p.insertAdjacentHTML("beforeend",text);'
        if HTML.count(safe) != 1:
            raise RuntimeError("HTML source seam changed")
        return self.send(200, HTML.replace(safe, vulnerable), html=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Optional local Edge/Puppeteer smoke")
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    if not os.getenv("HABITAT_BROWSER_BINARY"):
        parser.error("HABITAT_BROWSER_BINARY must point to a local browser")
    calls: list[tuple[str, list[dict[str, str]]]] = []

    def responder(tag: str, messages: list[dict[str, str]]) -> str:
        calls.append((tag, messages))
        return UNTRUSTED if tag == "fake-vera:dev" else "Synthetic JACK reply"

    room = RoomServer(
        {"vera": "fake-vera:dev", "jack": "fake-jack:dev"},
        responder=responder,
        port=0,
    )
    if args.negative_control:
        room.RequestHandlerClass = UnsafeNegativeControl
    thread = threading.Thread(target=room.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{room.server_port}/"
        script = ROOT / "tests" / "manual_room_browser_smoke.cjs"
        completed = subprocess.run(
            ["node", str(script), url],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if args.negative_control:
            if completed.returncode == 0:
                print("NEGATIVE_CONTROL_MISSED: browser accepted unsafe HTML")
                return 1
            if "Untrusted model output was parsed as HTML" not in completed.stderr:
                print("NEGATIVE_CONTROL_FAILED_FOR_WRONG_REASON")
                print(completed.stderr[-1200:])
                return 1
            print("NEGATIVE_CONTROL_DETECTED: browser rejected intentional XSS")
            return 0
        if completed.returncode != 0:
            print("BROWSER_PROBE_FAIL", completed.stderr[-2000:])
            return 1
        if len(calls) != 2 or [tag for tag, _ in calls] != [
            "fake-vera:dev", "fake-jack:dev"
        ]:
            print("EXPECTED_EXACTLY_TWO_EXPLICIT_MODEL_REQUESTS", [t for t, _ in calls])
            return 1
        if not calls[1][1][-1]["content"].startswith(
            "Human or forwarded message: Other local model said:"
        ):
            print("MODEL_FORWARDING_INCORRECT")
            return 1
        print(completed.stdout.strip())
        print("FAKE_BACKEND_CALLS=2, AUTO_LOOP_CALLS=0")
        return 0
    finally:
        room.shutdown()
        room.server_close()
        thread.join(timeout=5)
        if thread.is_alive():
            raise RuntimeError("temporary room server failed to close")


if __name__ == "__main__":
    raise SystemExit(main())
