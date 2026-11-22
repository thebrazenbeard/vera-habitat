"""Interactive 3D sandbox HTTP contract; standalone and offline assets only."""
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from vera_habitat.local_room import RoomServer


@pytest.fixture
def sandbox_server():
    calls = []

    def responder(tag, messages):
        calls.append((tag, messages))
        return "synthetic room response"

    server = RoomServer({"vera": "fake-vera:dev", "jack": "fake-jack:dev"},
                        responder=responder, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:" + str(server.server_port), calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def request(base, path, *, method="GET", data=None, headers=None):
    payload = json.dumps(data).encode() if data is not None else None
    req = Request(base + path, data=payload, method=method,
                  headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urlopen(req, timeout=5) as response:
            return response.status, response.headers, response.read()
    except HTTPError as err:
        return err.code, err.headers, err.read()


def test_sandbox_serves_local_engine_and_actual_playable_controls(sandbox_server):
    base, calls = sandbox_server
    status, headers, html = request(base, "/sandbox")
    assert status == 200
    assert headers["Content-Type"].startswith("text/html")
    assert b"Three.js" in html
    assert b"canvas" in html
    assert b"Play in 3D" in html
    assert b"Unverified" in html
    assert b"src=\"/sandbox/sandbox.js\"" in html
    status, headers, js = request(base, "/sandbox/sandbox.js")
    assert status == 200
    assert headers["Content-Type"].startswith("text/javascript")
    assert b"WebGLRenderer" in js
    assert b"keydown" in js
    assert b"/api/turn" in js
    assert calls == []


def test_sandbox_engine_works_offline_and_is_local_only(sandbox_server):
    base, _ = sandbox_server
    for path in ("/sandbox/vendor/three.module.js",
                 "/sandbox/vendor/three.core.js"):
        code, headers, data = request(base, path)
        assert code == 200 and len(data) > 100_000
        assert headers["Content-Type"].startswith("text/javascript")
        assert headers["Cache-Control"] == "no-store"
    status, _, data = request(base, "/sandbox/vendor/LICENSE")
    assert status == 200 and b"MIT License" in data
    status, headers, _ = request(base, "/sandbox")
    assert "script-src 'self';" in headers["Content-Security-Policy"]
    assert "script-src 'self' 'unsafe-inline'" not in headers["Content-Security-Policy"]
    assert "https:" not in headers["Content-Security-Policy"]
    assert request(base, "/sandbox/vendor/../../secret")[0] == 404
    assert request(base, "/sandbox/vendor/three.core.js", headers={
        "Host": "attacker.example"})[0] == 403


def test_sandbox_does_not_change_authorized_scene_or_send_messages_automatically(sandbox_server):
    base, calls = sandbox_server
    original = json.loads(request(base, "/api/scene")[2])
    assert request(base, "/sandbox")[0] == 200
    assert request(base, "/sandbox/sandbox.js")[0] == 200
    after = json.loads(request(base, "/api/scene")[2])
    assert original == after
    assert len(calls) == 0
