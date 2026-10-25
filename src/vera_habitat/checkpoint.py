"""Portable, self-checking in-memory world checkpoint codec.

SHA-256 detects accidental/casual editing, NOT authenticity, a trusted writer,
or a match to any deployed Vera state. No file/network effects occur here.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from .model import ActionReceipt, Entity, Position3, SceneSnapshot, _finite_real

SCHEMA = "VERA_HABITAT_CHECKPOINT_V1"
MAX_CHECKPOINT_BYTES = 1_048_576


def canonical_digest(value: dict[str, Any]) -> str:
    """Public SHA-256 content fingerprint, excluding sha256 itself."""
    if not isinstance(value, dict):
        raise ValueError("checkpoint must be a mapping")
    material = {k: v for k, v in value.items() if k != "sha256"}
    try:
        encoded = json.dumps(material, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("checkpoint contains unsupported or nonfinite values") from exc
    return sha256(encoded).hexdigest()


def _entity_record(entity: Entity) -> dict[str, Any]:
    return {
        "entity_id": entity.entity_id, "kind": entity.kind, "zone": entity.zone,
        "position": {"x": float(entity.position.x), "y": float(entity.position.y),
                     "z": float(entity.position.z)},
        "metadata": dict(sorted(entity.metadata.items())),
    }


def _receipt_record(item: ActionReceipt) -> dict[str, Any]:
    return {
        "action_id": item.action_id, "accepted": item.accepted,
        "disposition": item.disposition,
        "revision_before": item.revision_before,
        "revision_after": item.revision_after,
    }


def dump_checkpoint(snapshot: SceneSnapshot, receipts: tuple[ActionReceipt, ...],
                    seen_action_ids: frozenset[str]) -> str:
    """Serialize current scene, receipts, and idempotency guard in canonical JSON."""
    data: dict[str, Any] = {
        "schema_version": SCHEMA,
        "scene": {
            "schema_version": snapshot.schema_version,
            "revision": snapshot.revision,
            "entities": [_entity_record(e) for e in snapshot.entities],
        },
        "receipts": [_receipt_record(r) for r in receipts],
        "seen_action_ids": sorted(seen_action_ids),
    }
    data["sha256"] = canonical_digest(data)
    text = json.dumps(data, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)
    if len(text.encode("utf-8")) > MAX_CHECKPOINT_BYTES:
        raise ValueError("checkpoint exceeds size budget")
    return text


def _exact_mapping(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise ValueError(f"{label} has unexpected or missing fields")
    return value


def _clean_text(value: Any, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{label} must be nonblank text")
    return value


def _canonical_entity_text(value: Any, label: str) -> str:
    """Entity construction trims text; reject ambiguous serialized aliases."""
    text = _clean_text(value, label)
    if text != text.strip():
        raise ValueError(f"{label} must use canonical entity text")
    return text


def _nonnegative_int(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a nonnegative integer")
    return value


def _object_pairs_no_duplicates(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def load_checkpoint(source: str) -> tuple[int, dict[str, Entity], list[ActionReceipt], set[str]]:
    """Verify a snapshot/receipt consistency and reconstruct isolated objects.

    Checks integrity and structural constraints, NOT a signature or real-world
    event-chain authenticity.
    """
    if type(source) is not str:
        raise ValueError("checkpoint must be JSON text")
    if len(source.encode("utf-8")) > MAX_CHECKPOINT_BYTES:
        raise ValueError("checkpoint exceeds size budget")
    try:
        data = json.loads(source, object_pairs_hook=_object_pairs_no_duplicates)
    except (json.JSONDecodeError, UnicodeError, RecursionError) as exc:
        raise ValueError("invalid checkpoint JSON") from exc
    root = _exact_mapping(data, {
        "schema_version", "scene", "receipts", "seen_action_ids", "sha256"
    }, "checkpoint")
    if root["schema_version"] != SCHEMA:
        raise ValueError("unsupported checkpoint schema")
    digest = root["sha256"]
    if type(digest) is not str or len(digest) != 64 or digest != canonical_digest(root):
        raise ValueError("checkpoint content fingerprint mismatch")
    scene = _exact_mapping(root["scene"], {
        "schema_version", "revision", "entities"
    }, "scene")
    if scene["schema_version"] != "VERA_HABITAT_SCENE_V1":
        raise ValueError("unsupported scene schema")
    revision = _nonnegative_int(scene["revision"], "scene revision")
    if type(scene["entities"]) is not list or len(scene["entities"]) > 10000:
        raise ValueError("invalid scene entity collection")
    entities: dict[str, Entity] = {}
    for raw in scene["entities"]:
        item = _exact_mapping(raw, {
            "entity_id", "kind", "zone", "position", "metadata"
        }, "entity")
        eid = _canonical_entity_text(item["entity_id"], "entity_id")
        kind = _canonical_entity_text(item["kind"], "kind")
        zone = _canonical_entity_text(item["zone"], "zone")
        if eid in entities:
            raise ValueError("duplicate scene entity")
        coords = _exact_mapping(item["position"], {"x", "y", "z"}, "position")
        if any(not _finite_real(coords[k]) for k in ("x", "y", "z")):
            raise ValueError("invalid scene coordinates")
        pos = Position3(float(coords["x"]), float(coords["y"]), float(coords["z"]))
        metadata = item["metadata"]
        if type(metadata) is not dict or any(
            type(k) is not str or type(v) is not str for k, v in metadata.items()
        ):
            raise ValueError("entity metadata must have text keys and values")
        entities[eid] = Entity(eid, kind, zone, pos, metadata)
    if list(entities) != sorted(entities):
        raise ValueError("scene entities must be in sorted order")

    raw_receipts = root["receipts"]
    if type(raw_receipts) is not list or len(raw_receipts) > 100000:
        raise ValueError("invalid receipt collection")
    receipts: list[ActionReceipt] = []
    cursor = 0
    proposal_ids: set[str] = set()
    spawn_dispositions = {"SIMULATION_ENTITY_SPAWNED", "DUPLICATE_ENTITY_REJECTED"}
    spawned_ids: set[str] = set()
    for raw in raw_receipts:
        rec = _exact_mapping(raw, {
            "action_id", "accepted", "disposition", "revision_before", "revision_after"
        }, "receipt")
        aid = _clean_text(rec["action_id"], "action_id")
        disposition = _clean_text(rec["disposition"], "disposition")
        before = _nonnegative_int(rec["revision_before"], "revision_before")
        after = _nonnegative_int(rec["revision_after"], "revision_after")
        if type(rec["accepted"]) is not bool:
            raise ValueError("receipt acceptance must be Boolean")
        if before != cursor or after != cursor + (1 if rec["accepted"] else 0):
            raise ValueError("receipt revision chain is inconsistent")
        if disposition in spawn_dispositions:
            if not aid.startswith("spawn:") or not aid.removeprefix("spawn:"):
                raise ValueError("spawn receipt id invalid")
            if rec["accepted"] != (disposition == "SIMULATION_ENTITY_SPAWNED"):
                raise ValueError("spawn disposition contradicts acceptance")
            eid = aid.removeprefix("spawn:")
            if rec["accepted"]:
                if eid in spawned_ids:
                    raise ValueError("entity cannot be spawned twice")
                spawned_ids.add(eid)
            elif eid not in spawned_ids:
                raise ValueError("duplicate spawn rejection lacks an earlier spawn")
        else:
            if aid in proposal_ids:
                if rec["accepted"] or disposition != "DUPLICATE_ACTION_ID":
                    raise ValueError("replayed proposal must be rejected as duplicate")
            elif disposition == "DUPLICATE_ACTION_ID":
                raise ValueError("duplicate proposal rejection lacks an earlier proposal")
            if rec["accepted"] != (disposition == "SIMULATION_MOVE_APPLIED"):
                raise ValueError("proposal disposition contradicts acceptance")
            proposal_ids.add(aid)
        receipts.append(ActionReceipt(aid, rec["accepted"], disposition, before, after))
        cursor = after
    if cursor != revision:
        raise ValueError("scene revision differs from receipt chain")
    if spawned_ids != set(entities):
        raise ValueError("scene entities differ from accepted spawn receipts")
    seen = root["seen_action_ids"]
    if (type(seen) is not list or any(type(x) is not str or not x for x in seen)
            or seen != sorted(set(seen)) or set(seen) != proposal_ids):
        raise ValueError("seen action ids must match all proposal receipts")
    return revision, entities, receipts, set(seen)
