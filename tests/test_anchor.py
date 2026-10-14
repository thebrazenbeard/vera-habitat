"""Adversarial behavior for an explicitly supplied trusted rollback anchor."""
import pytest

from vera_habitat import (
    ActionProposal, AuthenticatedFileStore, EffectClass, Entity,
    HabitatRuntime, Position3,
)
from vera_habitat.anchor import AnchorHead


KEY = bytes(range(32))


class FakeAnchor:
    """Test double only: neither persistent nor independently trusted."""

    def __init__(self):
        self.head = None
        self.fail_read = False
        self.fail_advance = False
        self.force_conflict = False
        self.advances = 0

    def read_head(self):
        if self.fail_read:
            raise ConnectionError("anchor unavailable")
        return self.head

    def compare_and_advance(self, expected, successor):
        if self.fail_advance:
            raise ConnectionError("anchor unavailable")
        if self.force_conflict or self.head != expected:
            return False
        self.head = successor
        self.advances += 1
        return True


def setup(tmp_path, anchor):
    path = tmp_path / "checkpoint.json"
    store = AuthenticatedFileStore(
        path, KEY, writer_id="test", anchor=anchor,
        anchor_id="habitat-test-world",
    )
    world = HabitatRuntime()
    world.spawn(Entity("entity", "AVATAR", "home", Position3(0, 0, 0)))
    return path, store, world


def advance_world(world):
    world.propose(ActionProposal(
        "new-move", EffectClass.SIMULATION_ONLY, "MOVE_ENTITY",
        "entity", Position3(2, 0, 0),
    ))


def test_explicit_anchor_advances_by_cas_and_verifies_load(tmp_path):
    anchor = FakeAnchor()
    path, store, world = setup(tmp_path, anchor)
    assert anchor.advances == 0 and not path.exists()
    first = store.save(world)
    assert anchor.head == AnchorHead("habitat-test-world", 1, first.seal)
    restored = store.load()
    advance_world(restored.runtime)
    second = store.save(restored.runtime, expected_seal=first.seal)
    assert anchor.head == AnchorHead("habitat-test-world", 2, second.seal)
    assert anchor.advances == 2
    assert store.load().sequence == 2


def test_previous_valid_authenticated_file_is_detected_as_rollback(tmp_path):
    anchor = FakeAnchor()
    path, store, world = setup(tmp_path, anchor)
    first = store.save(world)
    old_bytes = path.read_bytes()
    advance_world(world)
    store.save(world, expected_seal=first.seal)
    path.write_bytes(old_bytes)
    with pytest.raises(ValueError, match="anchor"):
        store.load()
    with pytest.raises(ValueError, match="anchor"):
        store.save(world, expected_seal=first.seal)
    assert anchor.head.sequence == 2


def test_missing_or_reset_anchor_cannot_adopt_existing_file(tmp_path):
    anchor = FakeAnchor()
    path, store, world = setup(tmp_path, anchor)
    first = store.save(world)
    anchor.head = None
    with pytest.raises(ValueError, match="anchor"):
        store.load()
    with pytest.raises(ValueError, match="anchor"):
        store.save(world, expected_seal=first.seal)
    assert path.exists()


def test_external_conflict_prevents_checkpoint_replace(tmp_path):
    anchor = FakeAnchor()
    path, store, world = setup(tmp_path, anchor)
    first = store.save(world)
    original = path.read_bytes()
    advance_world(world)
    anchor.force_conflict = True
    with pytest.raises(ValueError, match="anchor"):
        store.save(world, expected_seal=first.seal)
    assert path.read_bytes() == original
    assert anchor.head.sequence == 1


def test_anchor_outage_fails_closed_without_disk_change(tmp_path):
    anchor = FakeAnchor()
    path, store, world = setup(tmp_path, anchor)
    first = store.save(world)
    original = path.read_bytes()
    advance_world(world)
    anchor.fail_read = True
    with pytest.raises(ConnectionError, match="unavailable"):
        store.load()
    with pytest.raises(ConnectionError, match="unavailable"):
        store.save(world, expected_seal=first.seal)
    anchor.fail_read = False
    anchor.fail_advance = True
    with pytest.raises(ConnectionError, match="unavailable"):
        store.save(world, expected_seal=first.seal)
    assert path.read_bytes() == original


def test_post_anchor_file_replace_failure_remains_fail_closed(tmp_path, monkeypatch):
    anchor = FakeAnchor()
    _, store, world = setup(tmp_path, anchor)
    first = store.save(world)
    advance_world(world)

    def fail_replace(*args):
        raise OSError("simulated disk failure")

    monkeypatch.setattr("vera_habitat.persistence.os.replace", fail_replace)
    with pytest.raises(OSError, match="disk failure"):
        store.save(world, expected_seal=first.seal)
    assert anchor.head.sequence == 2
    with pytest.raises(ValueError, match="anchor"):
        store.load()


def test_untrusted_anchor_values_fail_closed(tmp_path):
    anchor = FakeAnchor()
    _, store, world = setup(tmp_path, anchor)
    first = store.save(world)
    anchor.head = "invalid"
    with pytest.raises(ValueError, match="anchor"):
        store.load()
    with pytest.raises(ValueError, match="anchor"):
        store.save(world, expected_seal=first.seal)


def test_anchor_requires_explicit_stable_identity(tmp_path):
    anchor = FakeAnchor()
    with pytest.raises(ValueError, match="anchor_id"):
        AuthenticatedFileStore(tmp_path / "test.json", KEY,
                               writer_id="test", anchor=anchor)


def test_ambiguous_cas_response_must_not_install_unverified_local_file(tmp_path):
    class AmbiguousCommit(FakeAnchor):
        def compare_and_advance(self, expected, successor):
            assert super().compare_and_advance(expected, successor)
            raise ConnectionError("unknown commit outcome")

    anchor = AmbiguousCommit()
    path, store, world = setup(tmp_path, anchor)
    with pytest.raises(ConnectionError, match="unknown commit outcome"):
        store.save(world)
    assert not path.exists()
    assert anchor.head.sequence == 1
    with pytest.raises(ValueError, match="anchor"):
        store.save(world)


def test_deleting_latest_checkpoint_does_not_reset_anchored_stream(tmp_path):
    anchor = FakeAnchor()
    path, store, world = setup(tmp_path, anchor)
    store.save(world)
    path.unlink()
    with pytest.raises(ValueError, match="anchor"):
        store.save(world)
    with pytest.raises(FileNotFoundError):
        store.load()


def test_anchor_scope_mismatch_is_not_accepted(tmp_path):
    anchor = FakeAnchor()
    _, store, world = setup(tmp_path, anchor)
    first = store.save(world)
    anchor.head = AnchorHead("wrong-world", 1, first.seal)
    with pytest.raises(ValueError, match="anchor"):
        store.load()
