"""Opt-in, offline, authenticated checkpoint file for Vera Habitat.

Only explicit save()/load() methods perform filesystem I/O. This local store
does not install a service, create network authority, activate Vera, or record
Vera's identity/memory. HMAC verifies a holder of a shared local secret wrote
the bytes; it does NOT prove source-control currentness, defend against key
compromise, or prevent rollback to an older correctly authenticated file.

Assumes one trusted writer at a time and a trusted existing directory.
Expected-seal checks are optimistic, NOT cross-process atomic transactions.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import tempfile

from .checkpoint import _object_pairs_no_duplicates
from .runtime import HabitatRuntime


SCHEMA = "VERA_HABITAT_LOCAL_AUTHENTICATED_FILE_V1"
MAX_FILE_BYTES = 2_097_152


def _canonical(data: dict) -> bytes:
    try:
        return json.dumps(data, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid authenticated envelope") from exc


def _nonblank(value: object, label: str) -> str:
    if type(value) is not str or not value.strip() or len(value) > 128:
        raise ValueError(f"{label} must be text of length 1..128")
    return value


@dataclass(frozen=True, slots=True)
class StoredCheckpoint:
    runtime: HabitatRuntime
    seal: str
    sequence: int
    parent_seal: str | None
    writer_id: str


class AuthenticatedFileStore:
    """Single-writer, opt-in local JSON store for the *simulation* world only."""

    def __init__(self, path: str | Path, key: bytes, *, writer_id: str):
        if not isinstance(path, (str, Path)) or not str(path):
            raise ValueError("checkpoint path required")
        if type(key) is not bytes or len(key) < 32:
            raise ValueError("HMAC key must be at least 32 bytes")
        self._path = Path(path)
        self._key = key
        self._writer_id = _nonblank(writer_id, "writer_id")

    def _file_bytes(self) -> bytes:
        # Reject the symlink rather than silently accepting another file.
        if self._path.is_symlink():
            raise ValueError("checkpoint symlinks are unavailable")
        with self._path.open("rb") as source:
            data = source.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise ValueError("authenticated checkpoint exceeds file budget")
        return data

    def load(self) -> StoredCheckpoint:
        """Authenticate and load only; never create or bind a runtime service."""
        data = self._file_bytes()
        try:
            object_value = json.loads(data.decode("utf-8"),
                                      object_pairs_hook=_object_pairs_no_duplicates)
        except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
            raise ValueError("invalid authenticated checkpoint JSON") from exc
        if type(object_value) is not dict or set(object_value) != {
            "schema", "writer_id", "sequence", "parent_seal", "checkpoint", "mac"
        }:
            raise ValueError("unexpected authenticated checkpoint fields")
        if object_value["schema"] != SCHEMA:
            raise ValueError("unknown authenticated checkpoint schema")
        writer_id = _nonblank(object_value["writer_id"], "writer_id")
        sequence = object_value["sequence"]
        if type(sequence) is not int or sequence < 1:
            raise ValueError("invalid checkpoint sequence")
        parent = object_value["parent_seal"]
        if (parent is not None and
                (type(parent) is not str or len(parent) != 64
                 or any(c not in "0123456789abcdef" for c in parent))):
            raise ValueError("invalid parent seal")
        if (sequence == 1) != (parent is None):
            raise ValueError("checkpoint sequence and parent inconsistent")
        if type(object_value["checkpoint"]) is not str:
            raise ValueError("checkpoint payload must be JSON text")
        mac = object_value["mac"]
        if type(mac) is not str or len(mac) != 64:
            raise ValueError("invalid checkpoint authentication")
        unsigned = {key: value for key, value in object_value.items() if key != "mac"}
        expected_mac = hmac.new(self._key, _canonical(unsigned),
                                hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, expected_mac):
            raise ValueError("checkpoint authentication failed")
        # Only deserialize/reconstruct AFTER verifying the keyed MAC.
        runtime = HabitatRuntime.from_checkpoint(object_value["checkpoint"])
        return StoredCheckpoint(runtime, mac, sequence, parent, writer_id)

    def save(self, world: HabitatRuntime, *, expected_seal: str | None = None) -> StoredCheckpoint:
        """Save atomically (single file) with optimistic predecessor checking.

        This is a local file operation and must be explicitly invoked.
        The caller is responsible for securing the key, trusted directory,
        cross-process write exclusion, backups, and anti-rollback anchoring.
        """
        if not isinstance(world, HabitatRuntime):
            raise ValueError("save requires a HabitatRuntime")
        if expected_seal is not None and (
            type(expected_seal) is not str or len(expected_seal) != 64
        ):
            raise ValueError("expected_seal must be a 64-digit hexadecimal seal")
        if self._path.is_symlink():
            raise ValueError("checkpoint symlinks are unavailable")
        try:
            existing = self.load()
        except FileNotFoundError:
            existing = None
        predecessor = existing.seal if existing else None
        if expected_seal != predecessor:
            raise ValueError("expected_seal does not match current authenticated file")
        if existing and existing.writer_id != self._writer_id:
            raise ValueError("checkpoint writer differs from this store's writer")
        snapshot = world.export_checkpoint()
        # Validate and detach the return value *before* touching the file.
        saved_copy = HabitatRuntime.from_checkpoint(snapshot)
        if existing is not None:
            previous = existing.runtime.receipts
            current = saved_copy.receipts
            if current[:len(previous)] != previous:
                raise ValueError("checkpoint receipt history must extend predecessor")
            if len(current) == len(previous):
                raise ValueError("checkpoint requires at least one new receipt")
        unsigned = {
            "schema": SCHEMA,
            "writer_id": self._writer_id,
            "sequence": existing.sequence + 1 if existing else 1,
            "parent_seal": predecessor,
            "checkpoint": snapshot,
        }
        mac = hmac.new(self._key, _canonical(unsigned), hashlib.sha256).hexdigest()
        envelope = {**unsigned, "mac": mac}
        payload = _canonical(envelope)
        if len(payload) > MAX_FILE_BYTES:
            raise ValueError("authenticated checkpoint exceeds file budget")
        directory = self._path.parent
        # Require an existing trusted directory; never create a path or service.
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError("trusted existing checkpoint directory required")
        tmp: str | None = None
        try:
            fd, tmp = tempfile.mkstemp(prefix=".habitat-save-", suffix=".tmp",
                                       dir=directory)
            with os.fdopen(fd, "wb") as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            # Replace the target only after the new file is fully written.
            os.replace(tmp, self._path)
            tmp = None
        finally:
            if tmp is not None:
                try:
                    os.unlink(tmp)
                except FileNotFoundError:
                    pass
        return StoredCheckpoint(saved_copy, mac, unsigned["sequence"],
                                predecessor, self._writer_id)
