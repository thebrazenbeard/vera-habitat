"""Private, explicitly selected GLB preview is never canonical Habitat identity."""
import hashlib
import json
import struct
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from vera_habitat.local_room import RoomServer, preview_asset_bytes


def fixture_glb(*, uri=None):
    blob = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": 4}],
            "scenes": [{"nodes": []}], "scene": 0}
    if uri is not None:
        blob["buffers"][0]["uri"] = uri
    head = json.dumps(blob, separators=(",", ":")).encode("utf-8")
    head += b" " * (-len(head) % 4)
    bin_chunk = b"test"
    length = 12 + 8 + len(head) + 8 + len(bin_chunk)
    return (struct.pack("<4sII", b"glTF", 2, length)
            + struct.pack("<I4s", len(head), b"JSON") + head
            + struct.pack("<I4s", len(bin_chunk), b"BIN\x00") + bin_chunk)


def request(url):
    try:
        with urlopen(Request(url), timeout=5) as r:
            return r.status, r.headers, r.read()
    except HTTPError as e:
        return e.code, e.headers, e.read()

def test_preview_requires_exact_digest_and_self_contained_glb(tmp_path):
    path = tmp_path / "sample.glb"
    good = fixture_glb()
    path.write_bytes(good)
    digest = hashlib.sha256(good).hexdigest()
    assert preview_asset_bytes(path, digest) == good
    with pytest.raises(ValueError):
        preview_asset_bytes(path, "0" * 64)
    with pytest.raises(ValueError):
        preview_asset_bytes(path, "bad")
    path.write_bytes(fixture_glb(uri="https://example.org/remote.bin"))
    with pytest.raises(ValueError):
        preview_asset_bytes(path, hashlib.sha256(path.read_bytes()).hexdigest())
    path.write_bytes(b"not a GLB")
    with pytest.raises(ValueError):
        preview_asset_bytes(path, hashlib.sha256(path.read_bytes()).hexdigest())


def test_private_preview_is_opt_in_and_hash_fenced_on_every_get(tmp_path):
    data = fixture_glb()
    path = tmp_path / "vera-experimental.glb"
    path.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    calls = []
    server = RoomServer({"vera": "fake-vera:dev", "jack": "fake-jack:dev"},
                        responder=lambda m, h: calls.append(m) or "fake",
                        port=0, preview_assets={"vera": (str(path), digest)})
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        base = "http://127.0.0.1:" + str(server.server_port)
        code, _, meta = request(base + "/api/preview-assets")
        assert code == 200
        desc = json.loads(meta)["previews"]
        assert len(desc) == 1
        assert desc[0]["slot"] == "vera"
        assert desc[0]["approval"] == "UNVERIFIED_EXPERIMENTAL_PREVIEW"
        assert "C:\\" not in meta.decode() and str(tmp_path) not in meta.decode()
        assert desc[0]["url"] == "/sandbox/previews/vera.glb"
        code, headers, body = request(base + desc[0]["url"])
        assert code == 200 and body == data
        assert headers["Content-Type"] == "model/gltf-binary"
        assert headers["Cache-Control"] == "no-store"
        assert request(base + "/sandbox/previews/jack.glb")[0] == 404
        path.write_bytes(fixture_glb(uri="evil.bin"))
        assert request(base + "/sandbox/previews/vera.glb")[0] == 503
        assert not calls
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=4)
