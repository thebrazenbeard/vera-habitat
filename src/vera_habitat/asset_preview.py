"""Opt-in, hash-bound, self-contained GLB preview. Not asset rights/identity approval."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import struct

MAX_PREVIEW_BYTES = 16 * 1024 * 1024
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _contains_uri(value: object) -> bool:
    if type(value) is dict:
        return any(
            key == "uri" or _contains_uri(item)
            for key, item in value.items()
        )
    if type(value) is list:
        return any(_contains_uri(item) for item in value)
    return False


def _object_array(document: dict, name: str) -> list:
    objects = document.get(name, [])
    if type(objects) is not list or any(type(item) is not dict for item in objects):
        raise ValueError(f"GLB {name} must be an array of objects")
    return objects


def _index(value: object, count: int, name: str) -> int:
    # bool is a subclass of int; JSON booleans are not glTF indices.
    if type(value) is not int or not 0 <= value < count:
        raise ValueError(f"GLB {name} index out of bounds or invalid")
    return value


def _references(value: object, count: int, name: str) -> list[int]:
    if type(value) is not list:
        raise ValueError(f"GLB {name} must be an array")
    indices = [_index(item, count, name) for item in value]
    if len(set(indices)) != len(indices):
        raise ValueError(f"GLB {name} contains duplicate references")
    return indices


def _validate_scene_graph(document: dict) -> None:
    """Bound core scene/node references; not a complete glTF validator."""
    nodes = _object_array(document, "nodes")
    scenes = _object_array(document, "scenes")
    if "scene" in document:
        _index(document["scene"], len(scenes), "default scene")
    for scene in scenes:
        _references(scene.get("nodes", []), len(nodes), "scene node")
    edges = [_references(node.get("children", []), len(nodes), "child node")
             for node in nodes]
    # Kahn's algorithm detects cycles, including unreachable cycles, without
    # recursively following untrusted graph depth.
    indegree = [0] * len(nodes)
    for children in edges:
        for child in children:
            indegree[child] += 1
    pending = [i for i, degree in enumerate(indegree) if degree == 0]
    visited = 0
    while pending:
        visited += 1
        for child in edges[pending.pop()]:
            indegree[child] -= 1
            if indegree[child] == 0:
                pending.append(child)
    if visited != len(nodes):
        raise ValueError("GLB node graph contains a cycle")


def preview_asset_bytes(path: Path, expected_sha256: str) -> bytes:
    """Verify exact private bytes on *each* read; no external URI dependencies."""
    if type(expected_sha256) is not str or not _SHA256.fullmatch(expected_sha256):
        raise ValueError("preview requires lower-case SHA-256")
    candidate = Path(path).resolve(strict=True)
    if candidate.suffix.lower() != ".glb" or not candidate.is_file():
        raise ValueError("preview must be a local GLB file")
    size = candidate.stat().st_size
    if size < 32 or size > MAX_PREVIEW_BYTES:
        raise ValueError("preview GLB file size out of bounds")
    raw = candidate.read_bytes()
    if len(raw) != size or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("private GLB bytes changed or digest mismatch")
    magic, version, declared = struct.unpack_from("<4sII", raw)
    if magic != b"glTF" or version != 2 or declared != len(raw):
        raise ValueError("not a complete glTF 2.0 binary")
    chunk_len, chunk_type = struct.unpack_from("<I4s", raw, 12)
    if chunk_type != b"JSON" or chunk_len < 2 or chunk_len % 4:
        raise ValueError("GLB first chunk must contain aligned JSON")
    if 20 + chunk_len > len(raw):
        raise ValueError("truncated GLB JSON")
    try:
        document = json.loads(raw[20:20 + chunk_len].decode("utf-8").rstrip(" \x00"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError("malformed GLB JSON") from exc
    if (type(document) is not dict
            or type(document.get("asset")) is not dict
            or document["asset"].get("version") != "2.0"
            or _contains_uri(document)):
        raise ValueError("unsupported GLB or external resource reference")
    _validate_scene_graph(document)
    # Only one embedded BIN chunk (or no BIN for pure scene geometry) is admitted.
    position = 20 + chunk_len
    if position < len(raw):
        if len(raw) - position < 8:
            raise ValueError("truncated GLB BIN header")
        bin_len, bin_type = struct.unpack_from("<I4s", raw, position)
        if bin_type != b"BIN\x00" or position + 8 + bin_len != len(raw):
            raise ValueError("GLB requires a single complete embedded BIN chunk")
    return raw
