"""Tests the public, explicit local checkpoint persistence seam."""
import json

import pytest

from vera_habitat import (
    ActionProposal, Entity, EffectClass, HabitatRuntime, Position3,
)
from vera_habitat import AuthenticatedFileStore


KEY = bytes(range(32))
WRONG_KEY = b"w" * 32


def world():
    habitat = HabitatRuntime()
    habitat.spawn(Entity("vera", "AVATAR", "home", Position3(0, 0, 0)))
    habitat.propose(ActionProposal(
        "move-1", EffectClass.SIMULATION_ONLY, "MOVE_ENTITY",
        "vera", Position3(2, 1, 0),
    ))
    return habitat


def store(tmp_path, key=KEY):
    return AuthenticatedFileStore(tmp_path / "checkpoint.sealed.json", key,
                                  writer_id="offline-local-test")


def test_no_file_creation_or_autobind_before_save(tmp_path):
    location = tmp_path / "checkpoint.sealed.json"
    s = store(tmp_path)
    assert not location.exists()
    with pytest.raises(FileNotFoundError):
        s.load()
    assert not location.exists()


def test_authenticated_save_load_restore_and_replay_guard(tmp_path):
    s = store(tmp_path)
    w = world()
    entry = s.save(w)
    assert entry.sequence == 1
    assert entry.parent_seal is None
    assert entry.writer_id == "offline-local-test"
    assert len(entry.seal) == 64
    assert (tmp_path / "checkpoint.sealed.json").is_file()
    restored = s.load()
    assert restored.sequence == 1
    assert restored.seal == entry.seal
    assert restored.runtime.export_checkpoint() == w.export_checkpoint()
    repeat = ActionProposal("move-1", EffectClass.SIMULATION_ONLY,
                            "MOVE_ENTITY", "vera", Position3(400, 0, 0))
    assert restored.runtime.propose(repeat).disposition == "DUPLICATE_ACTION_ID"


def test_authenticated_roll_forward_requires_previous_seal(tmp_path):
    s = store(tmp_path)
    first = s.save(world())
    saved = s.load()
    saved.runtime.propose(ActionProposal(
        "move-2", EffectClass.SIMULATION_ONLY, "MOVE_ENTITY",
        "vera", Position3(3, 1, 0),
    ))
    with pytest.raises(ValueError, match="expected_seal"):
        s.save(saved.runtime)
    with pytest.raises(ValueError, match="expected_seal"):
        s.save(saved.runtime, expected_seal="f" * 64)
    second = s.save(saved.runtime, expected_seal=first.seal)
    assert second.sequence == 2
    assert second.parent_seal == first.seal
    assert second.seal != first.seal
    assert s.load().runtime.snapshot().entities[0].position == Position3(3, 1, 0)
    assert s.load().sequence == 2


def test_wrong_key_or_modified_payload_fails_closed(tmp_path):
    s = store(tmp_path)
    before = s.save(world())
    with pytest.raises(ValueError, match="authentication"):
        store(tmp_path, WRONG_KEY).load()
    path = tmp_path / "checkpoint.sealed.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["writer_id"] = "an-attacker"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="authentication"):
        s.load()
    with pytest.raises(ValueError):
        s.save(world(), expected_seal=before.seal)


def test_recomputing_public_checkpoint_digest_does_not_forge_hmac(tmp_path):
    from vera_habitat.checkpoint import canonical_digest
    s = store(tmp_path)
    s.save(world())
    path = tmp_path / "checkpoint.sealed.json"
    envelope = json.loads(path.read_text(encoding="utf-8"))
    checkpoint = json.loads(envelope["checkpoint"])
    checkpoint["scene"]["entities"][0]["position"]["x"] = 999.0
    checkpoint["sha256"] = canonical_digest(checkpoint)
    envelope["checkpoint"] = json.dumps(checkpoint)
    path.write_text(json.dumps(envelope), encoding="utf-8")
    with pytest.raises(ValueError, match="authentication"):
        s.load()


def test_invalid_existing_file_never_clobbered(tmp_path):
    path = tmp_path / "checkpoint.sealed.json"
    path.write_text("invalid checkpoint", encoding="utf-8")
    s = store(tmp_path)
    with pytest.raises(ValueError):
        s.save(world())
    assert path.read_text(encoding="utf-8") == "invalid checkpoint"


def test_missing_expected_predecessor_rejected_without_writing(tmp_path):
    s = store(tmp_path)
    with pytest.raises(ValueError, match="expected_seal"):
        s.save(world(), expected_seal="0" * 64)
    assert not (tmp_path / "checkpoint.sealed.json").exists()


@pytest.mark.parametrize("key,writer", [
    (b"short", "writer"),
    (KEY, ""),
    (KEY, 123),
])
def test_invalid_configuration_has_no_filesystem_side_effects(tmp_path, key, writer):
    with pytest.raises(ValueError):
        AuthenticatedFileStore(tmp_path / "checkpoint.sealed.json", key, writer_id=writer)
    assert not list(tmp_path.iterdir())


def test_reject_symlink_target_if_supported(tmp_path):
    outside = tmp_path / "external-file"
    outside.write_text("untrusted", encoding="utf-8")
    path = tmp_path / "checkpoint.sealed.json"
    try:
        path.symlink_to(outside)
    except (NotImplementedError, OSError):
        pytest.skip("filesystem symlinks unavailable")
    s = store(tmp_path)
    with pytest.raises(ValueError):
        s.save(world())
    with pytest.raises(ValueError):
        s.load()
    assert outside.read_text(encoding="utf-8") == "untrusted"


def test_maximum_input_bytes_reject_large_file_before_json_load(tmp_path):
    path = tmp_path / "checkpoint.sealed.json"
    path.write_bytes(b"0" * 2_100_000)
    with pytest.raises(ValueError):
        store(tmp_path).load()


def test_failing_export_keeps_previous_signed_file_unchanged(tmp_path, monkeypatch):
    s = store(tmp_path)
    signed = s.save(world())
    original = (tmp_path / "checkpoint.sealed.json").read_bytes()
    candidate = world()
    def fail_export():
        raise ValueError("cannot serialize world")
    monkeypatch.setattr(candidate, "export_checkpoint", fail_export)
    with pytest.raises(ValueError):
        s.save(candidate, expected_seal=signed.seal)
    assert (tmp_path / "checkpoint.sealed.json").read_bytes() == original


def test_save_receipt_world_is_detached_from_live_input(tmp_path):
    s = store(tmp_path)
    live = world()
    stored = s.save(live)
    live.propose(ActionProposal("later", EffectClass.SIMULATION_ONLY,
                                "MOVE_ENTITY", "vera", Position3(100, 1, 0)))
    assert stored.runtime.snapshot().entities[0].position == Position3(2, 1, 0)


def test_failed_atomic_replace_preserves_previous_signed_bytes_and_cleans_temp(
    tmp_path, monkeypatch,
):
    from vera_habitat import persistence
    s = store(tmp_path)
    first = s.save(world())
    before = (tmp_path / "checkpoint.sealed.json").read_bytes()
    w = s.load().runtime
    w.propose(ActionProposal("another", EffectClass.SIMULATION_ONLY,
                             "MOVE_ENTITY", "vera", Position3(4, 1, 0)))
    def replace_failure(source, destination):
        raise OSError("forced filesystem replace failure")
    monkeypatch.setattr(persistence.os, "replace", replace_failure)
    with pytest.raises(OSError, match="forced filesystem replace failure"):
        s.save(w, expected_seal=first.seal)
    assert (tmp_path / "checkpoint.sealed.json").read_bytes() == before
    assert not list(tmp_path.glob(".habitat-save-*.tmp"))


def test_store_never_writes_secret_into_sealed_file(tmp_path):
    secret = b"visible-sentinel-KEEP-SECRET-LOCAL-123456"
    s = store(tmp_path, secret)
    s.save(world())
    data = (tmp_path / "checkpoint.sealed.json").read_bytes()
    assert secret not in data
    assert secret.hex().encode() not in data


def test_writer_change_cannot_replace_a_valid_prior_envelope(tmp_path):
    first = store(tmp_path)
    signed = first.save(world())
    another = AuthenticatedFileStore(tmp_path / "checkpoint.sealed.json",
                                     KEY, writer_id="different-writer")
    with pytest.raises(ValueError, match="writer"):
        another.save(world(), expected_seal=signed.seal)
    assert first.load().writer_id == "offline-local-test"


def test_predecessor_seal_alone_cannot_authorize_divergent_local_history(tmp_path):
    s = store(tmp_path)
    first = s.save(world())
    unrelated = HabitatRuntime()
    unrelated.spawn(Entity("stranger", "AVATAR", "home", Position3(0, 0, 0)))
    unrelated.propose(ActionProposal("different-action", EffectClass.SIMULATION_ONLY,
                                     "MOVE_ENTITY", "stranger", Position3(8, 0, 0)))
    with pytest.raises(ValueError, match="history"):
        s.save(unrelated, expected_seal=first.seal)
    assert s.load().seal == first.seal


def test_reject_duplicate_generation_with_no_new_receipt(tmp_path):
    s = store(tmp_path)
    first = s.save(world())
    with pytest.raises(ValueError, match="new receipt"):
        s.save(s.load().runtime, expected_seal=first.seal)
    assert s.load().sequence == 1


def test_rejected_action_is_valid_new_receipt_without_revision_increment(tmp_path):
    s = store(tmp_path)
    first = s.save(world())
    loaded = s.load()
    assert loaded.runtime.propose(ActionProposal(
        "external-rejected", EffectClass.EXTERNAL_REQUEST,
        "MOVE_ENTITY", "vera", Position3(999, 0, 0))).disposition == "EXTERNAL_EFFECT_UNAVAILABLE"
    assert loaded.runtime.revision == first.runtime.revision
    second = s.save(loaded.runtime, expected_seal=first.seal)
    assert second.sequence == 2
    assert second.runtime.revision == first.runtime.revision
    assert s.load().sequence == 2


def test_authenticated_old_file_can_still_be_rolled_back_without_trusted_anchor(tmp_path):
    """Explicitly proves this local HMAC store is NOT anti-rollback."""
    s = store(tmp_path)
    first = s.save(world())
    path = tmp_path / "checkpoint.sealed.json"
    old_valid_data = path.read_bytes()
    loaded = s.load()
    loaded.runtime.propose(ActionProposal(
        "new", EffectClass.SIMULATION_ONLY, "MOVE_ENTITY",
        "vera", Position3(5, 0, 0)))
    assert s.save(loaded.runtime, expected_seal=first.seal).sequence == 2
    path.write_bytes(old_valid_data)  # attacker with file write access
    assert s.load().sequence == 1
    assert s.load().seal == first.seal
