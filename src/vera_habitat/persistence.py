"""Opt-in, offline, authenticated checkpoint file for Vera Habitat.

Only explicit save()/load() methods perform filesystem I/O. This local store
does not install a service, create network authority, activate Vera, or record
Vera's identity/memory. HMAC verifies a holder of a shared local secret wrote
the bytes; it does NOT prove source-control currentness, defend against key
compromise, or prevent rollback to an older correctly authenticated file.

Uses an advisory per-file OS lock around explicit saves by cooperating
local processes. The trusted directory and OS are required; this is NOT a
distributed lock, hostile-process sandbox, or anti-rollback mechanism.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import tempfile

from .anchor import AnchorHead, TrustedAnchor
from ._file_lock import exclusive_checkpoint_lock as _exclusive_checkpoint_lock
from .checkpoint import _object_pairs_no_duplicates
from .model import _finite_real
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

    def __init__(self, path: str | Path, key: bytes, *, writer_id: str,
                 lock_timeout_seconds: float = 2.0,
                 anchor: TrustedAnchor | None = None,
                 anchor_id: str | None = None):
        if not isinstance(path, (str, Path)) or not str(path):
            raise ValueError("checkpoint path required")
        if type(key) is not bytes or len(key) < 32:
            raise ValueError("HMAC key must be at least 32 bytes")
        if (not _finite_real(lock_timeout_seconds)
                or not 0 <= lock_timeout_seconds <= 30):
            raise ValueError("lock_timeout_seconds must be finite in [0, 30]")
        if anchor is not None:
            if (type(anchor_id) is not str or not anchor_id.strip()
                    or len(anchor_id) > 128):
                raise ValueError("anchor_id is required for an external anchor")
            if (not callable(getattr(anchor, "read_head", None))
                    or not callable(getattr(anchor, "compare_and_advance", None))):
                raise ValueError("anchor must implement the trusted CAS contract")
        elif anchor_id is not None:
            raise ValueError("anchor_id requires an external anchor")
        self._anchor = anchor
        self._anchor_id = anchor_id
        self._lock_timeout_seconds = float(lock_timeout_seconds)
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

    def _current_anchor(self) -> AnchorHead | None:
        """Read through the caller-supplied authority without local fallback."""
        assert self._anchor is not None
        head = self._anchor.read_head()
        if (head is not None and
                (type(head) is not AnchorHead or head.anchor_id != self._anchor_id)):
            raise ValueError("invalid trusted anchor head")
        return head

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
        if self._anchor is not None:
            required = AnchorHead(self._anchor_id, sequence, mac)
            if self._current_anchor() != required:
                raise ValueError("trusted anchor disagrees with checkpoint; possible rollback")
        return StoredCheckpoint(runtime, mac, sequence, parent, writer_id)

    def save(self, world: HabitatRuntime, *, expected_seal: str | None = None) -> StoredCheckpoint:
        """Serialize cooperating local writers around the full check-and-save.

        Creates a permanent sidecar `.lock` on first explicit save. Advisory
        locks protect cooperating local processes only, not hostile writers or
        network filesystems. A timed-out lock raises TimeoutError.
        """
        with _exclusive_checkpoint_lock(self._path, self._lock_timeout_seconds):
            return self._save_unlocked(world, expected_seal=expected_seal)

    def _save_unlocked(self, world: HabitatRuntime, *, expected_seal: str | None = None) -> StoredCheckpoint:
        """Save atomically (single file) after lock acquisition.

        This is a local file operation and must be explicitly invoked.
        The caller is responsible for securing the key and trusted directory,
        coordinating noncooperating/distributed writers, backups and any
        independently trusted anti-rollback anchoring.
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
        if existing is None and self._anchor is not None and self._current_anchor() is not None:
            raise ValueError("trusted anchor has a head but checkpoint is absent")
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
            # Commit the independently trusted high-water mark BEFORE exposing
            # new local data: a crash may leave the file stale, but never
            # makes a stale generation pass an anchored load.
            if self._anchor is not None:
                previous_head = (AnchorHead(self._anchor_id, existing.sequence, existing.seal)
                                 if existing else None)
                next_head = AnchorHead(self._anchor_id, unsigned["sequence"], mac)
                if self._anchor.compare_and_advance(previous_head, next_head) is not True:
                    raise ValueError("trusted anchor CAS conflict; checkpoint unchanged")
            # Replace the target only after staging and (when enabled) anchor CAS.
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
