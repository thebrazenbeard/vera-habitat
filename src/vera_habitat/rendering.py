"""Renderer-safe JSON projection; contains no action authority or transport."""
from __future__ import annotations

import json

from .model import SceneSnapshot
from .checkpoint import _entity_record, _nonnegative_int


def render_scene_json(snapshot: SceneSnapshot) -> str:
    """Project typed world state into disposable, detached JSON.

    All consumption is read-only. A renderer cannot mutate Habitat by
    changing this JSON, and the projection does not encode control routes.
    """
    if not isinstance(snapshot, SceneSnapshot):
        raise ValueError("expected typed SceneSnapshot")
    if snapshot.schema_version != "VERA_HABITAT_SCENE_V1":
        raise ValueError("unsupported scene version")
    revision = _nonnegative_int(snapshot.revision, "scene revision")
    items = sorted(snapshot.entities, key=lambda e: e.entity_id)
    if len({e.entity_id for e in items}) != len(items):
        raise ValueError("renderer requires unique entity identities")
    value = {
        "schema_version": "VERA_HABITAT_RENDER_V1",
        "world_revision": revision,
        "authority": "READ_ONLY_PROJECTION",
        "entities": [_entity_record(e) for e in items],
    }
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)
