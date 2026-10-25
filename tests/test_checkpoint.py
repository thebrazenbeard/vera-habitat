"""Adversarial replay and portable checkpoint contract for Habitat."""
import json
import pytest

from vera_habitat import ActionProposal, EffectClass, Entity, HabitatRuntime, Position3
from vera_habitat.model import ActionProposal as Proposal


def example_runtime():
    world = HabitatRuntime()
    assert world.spawn(Entity("vera", "AVATAR", "home", Position3(0, 0, 0),
                              {"role": "observer"})).accepted
    assert world.spawn(Entity("bench", "OBJECT", "home", Position3(2, 0, 0))).accepted
    return world


def test_replay_same_action_id_does_not_apply_twice():
    world = example_runtime()
    proposal = Proposal("move-0001", EffectClass.SIMULATION_ONLY,
                        "MOVE_ENTITY", "vera", Position3(1, 2, 3))
    first = world.propose(proposal)
    assert first.accepted
    previous_rev = world.revision
    second = world.propose(proposal)
    assert not second.accepted
    assert second.disposition == "DUPLICATE_ACTION_ID"
    assert second.revision_before == previous_rev == second.revision_after
    assert world.snapshot().entities[1].position == Position3(1, 2, 3)


def test_rejected_external_action_id_cannot_be_replayed_as_virtual_move():
    world = example_runtime()
    rejected = Proposal("external-9", EffectClass.EXTERNAL_REQUEST, "MOVE_ENTITY",
                        "vera", Position3(5, 0, 0))
    assert world.propose(rejected).disposition == "EXTERNAL_EFFECT_UNAVAILABLE"
    before = world.snapshot()
    second = Proposal("external-9", EffectClass.SIMULATION_ONLY, "MOVE_ENTITY",
                      "vera", Position3(5, 0, 0))
    assert world.propose(second).disposition == "DUPLICATE_ACTION_ID"
    assert world.snapshot() == before


def test_malformed_proposal_never_mutates_scene():
    world = example_runtime()
    before = world.snapshot()
    invalid = Proposal("bad", EffectClass.SIMULATION_ONLY, "MOVE_ENTITY",
                       "vera", "not-a-position")
    receipt = world.propose(invalid)
    assert not receipt.accepted
    assert receipt.disposition == "INVALID_PROPOSAL"
    assert world.snapshot() == before


def test_roundtrip_restores_state_receipts_and_duplicate_guard():
    world = example_runtime()
    proposal = Proposal("move-after-spawn", EffectClass.SIMULATION_ONLY,
                        "MOVE_ENTITY", "vera", Position3(.75, -2, 0))
    world.propose(proposal)
    world.propose(Proposal("outside", EffectClass.EXTERNAL_REQUEST,
                           "MOVE_ENTITY", "vera", Position3(900, 0, 0)))
    checkpoint = world.export_checkpoint()
    loaded = HabitatRuntime.from_checkpoint(checkpoint)
    assert loaded.export_checkpoint() == checkpoint
    assert loaded.snapshot() == world.snapshot()
    assert loaded.receipts == world.receipts
    assert loaded.propose(proposal).disposition == "DUPLICATE_ACTION_ID"
    assert loaded.revision == world.revision
    assert loaded.propose(Proposal("fresh", EffectClass.SIMULATION_ONLY,
                          "MOVE_ENTITY", "vera", Position3(1, 0, 0))).accepted


def test_checkpoint_digest_is_stable_and_does_not_claim_authenticity():
    world = example_runtime()
    value = json.loads(world.export_checkpoint())
    assert value["schema_version"] == "VERA_HABITAT_CHECKPOINT_V1"
    assert len(value["sha256"]) == 64
    assert value["scene"]["revision"] == 2
    assert value["scene"]["entities"][0]["entity_id"] == "bench"
    assert world.export_checkpoint() == world.export_checkpoint()


@pytest.mark.parametrize("mutate", [
    lambda j: j["scene"]["entities"][0]["position"].__setitem__("x", "invalid"),
    lambda j: j.__setitem__("schema_version", "VERA_HABITAT_CHECKPOINT_V999"),
    lambda j: j["scene"]["entities"].append(j["scene"]["entities"][0]),
    lambda j: j["receipts"][0].__setitem__("revision_after", 100),
    lambda j: j["seen_action_ids"].append("unreferenced"),
    lambda j: j["scene"]["entities"].pop(0),
])
def test_checkpoint_rejects_tamper_even_when_checksum_recalculated(mutate):
    from vera_habitat.checkpoint import canonical_digest
    world = example_runtime()
    world.propose(Proposal("move-1", EffectClass.SIMULATION_ONLY,
                           "MOVE_ENTITY", "vera", Position3(1, 0, 0)))
    value = json.loads(world.export_checkpoint())
    mutate(value)
    # Corrupted data cannot pass even with a recomputed public digest.
    value["sha256"] = canonical_digest(value)
    with pytest.raises(ValueError):
        HabitatRuntime.from_checkpoint(json.dumps(value))


def test_checkpoint_rejects_edited_payload_without_updated_digest():
    world = example_runtime()
    record = json.loads(world.export_checkpoint())
    record["scene"]["entities"][0]["position"]["x"] = 222
    with pytest.raises(ValueError, match="fingerprint"):
        HabitatRuntime.from_checkpoint(json.dumps(record))


def test_checkpoint_rejects_unrepresentably_large_integer_coordinate_as_value_error():
    from vera_habitat.checkpoint import canonical_digest

    record = json.loads(example_runtime().export_checkpoint())
    record["scene"]["entities"][0]["position"]["x"] = 10**400
    record["sha256"] = canonical_digest(record)
    with pytest.raises(ValueError, match="invalid scene coordinates"):
        HabitatRuntime.from_checkpoint(json.dumps(record))


@pytest.mark.parametrize("field", ["entity_id", "kind", "zone"])
def test_checkpoint_rejects_noncanonical_entity_text_before_mutating_identity(field):
    from vera_habitat.checkpoint import canonical_digest

    world = HabitatRuntime()
    world.spawn(Entity("vera", "AVATAR", "home", Position3(0, 0, 0)))
    record = json.loads(world.export_checkpoint())
    record["scene"]["entities"][0][field] = f" {record['scene']['entities'][0][field]} "
    if field == "entity_id":
        record["receipts"][0]["action_id"] = "spawn: vera "
    record["sha256"] = canonical_digest(record)
    with pytest.raises(ValueError, match="canonical"):
        HabitatRuntime.from_checkpoint(json.dumps(record))


def test_checkpoint_rejects_entities_with_duplicate_canonical_identity():
    from vera_habitat.checkpoint import canonical_digest

    world = HabitatRuntime()
    world.spawn(Entity("a", "AVATAR", "home", Position3(0, 0, 0)))
    world.spawn(Entity("b", "AVATAR", "home", Position3(1, 0, 0)))
    record = json.loads(world.export_checkpoint())
    record["scene"]["entities"][0]["entity_id"] = " a"
    record["scene"]["entities"][1]["entity_id"] = "a"
    record["receipts"][0]["action_id"] = "spawn: a"
    record["receipts"][1]["action_id"] = "spawn:a"
    record["sha256"] = canonical_digest(record)
    with pytest.raises(ValueError, match="canonical"):
        HabitatRuntime.from_checkpoint(json.dumps(record))


def test_duplicate_json_keys_do_not_sneak_through_parse():
    # Duplicate object keys must not be silently 'last wins'.
    with pytest.raises(ValueError):
        HabitatRuntime.from_checkpoint('{"schema_version":"X","schema_version":"Y"}')


def test_snapshot_isolation_of_source_metadata():
    attrs = {"owner": "Vera"}
    entity = Entity("room", "OBJECT", "zone", Position3(0, 0, 0), attrs)
    world = HabitatRuntime()
    world.spawn(entity)
    attrs["owner"] = "external_mutation"
    assert world.snapshot().entities[0].metadata["owner"] == "Vera"
    with pytest.raises(TypeError):
        world.snapshot().entities[0].metadata["owner"] = "changed"


@pytest.mark.parametrize(
    "field", ["entity_id", "kind", "zone", "metadata_key", "metadata_value"]
)
def test_entity_rejects_non_utf8_text_before_spawning(field):
    bad = "bad" + chr(0xD800)
    kwargs = dict(entity_id="avatar", kind="AVATAR", zone="room",
                  position=Position3(0, 0, 0), metadata={"role": "observer"})
    if field.startswith("metadata_"):
        kwargs["metadata"] = {bad: "observer"} if field == "metadata_key" else {"role": bad}
    else:
        kwargs[field] = bad
    with pytest.raises(ValueError, match="UTF-8"):
        Entity(**kwargs)


def test_non_utf8_action_id_does_not_poison_checkpointable_world():
    world = example_runtime()
    prior_checkpoint = world.export_checkpoint()
    prior_revision = world.revision
    proposal = Proposal("move-" + chr(0xD800), EffectClass.SIMULATION_ONLY,
                        "MOVE_ENTITY", "vera", Position3(1, 2, 3))
    with pytest.raises(ValueError, match="UTF-8"):
        world.propose(proposal)
    assert world.revision == prior_revision
    assert world.export_checkpoint() == prior_checkpoint
    assert world.propose(Proposal("move-valid", EffectClass.SIMULATION_ONLY,
                         "MOVE_ENTITY", "vera", Position3(1, 2, 3))).accepted
    assert HabitatRuntime.from_checkpoint(world.export_checkpoint()).revision == prior_revision + 1


def test_valid_multibyte_unicode_remains_checkpointable():
    world = HabitatRuntime()
    assert world.spawn(Entity("avatar-🛰", "AVATAR", "room-🌎",
                              Position3(0, 0, 0), {"mood": "curious-✨"})).accepted
    assert world.propose(Proposal("step-🚀", EffectClass.SIMULATION_ONLY,
                                 "MOVE_ENTITY", "avatar-🛰", Position3(1, 0, 0))).accepted
    assert HabitatRuntime.from_checkpoint(world.export_checkpoint()).snapshot() == world.snapshot()


def test_checkpoint_rejects_oversized_and_nonjson_payload():
    with pytest.raises(ValueError):
        HabitatRuntime.from_checkpoint("{" * 2_000_000)
    with pytest.raises(ValueError):
        HabitatRuntime.from_checkpoint("not-json")


def test_checkpoint_rejects_duplicate_spawn_without_prior_spawn():
    from vera_habitat.checkpoint import canonical_digest
    record = json.loads(HabitatRuntime().export_checkpoint())
    record["receipts"] = [{
        "action_id": "spawn:ghost", "accepted": False,
        "disposition": "DUPLICATE_ENTITY_REJECTED",
        "revision_before": 0, "revision_after": 0,
    }]
    record["sha256"] = canonical_digest(record)
    with pytest.raises(ValueError):
        HabitatRuntime.from_checkpoint(json.dumps(record))


def test_checkpoint_rejects_duplicate_action_without_first_action():
    from vera_habitat.checkpoint import canonical_digest
    record = json.loads(HabitatRuntime().export_checkpoint())
    record["receipts"] = [{
        "action_id": "first", "accepted": False,
        "disposition": "DUPLICATE_ACTION_ID",
        "revision_before": 0, "revision_after": 0,
    }]
    record["seen_action_ids"] = ["first"]
    record["sha256"] = canonical_digest(record)
    with pytest.raises(ValueError):
        HabitatRuntime.from_checkpoint(json.dumps(record))


def test_checkpoint_rejects_repeated_accepted_action_id():
    from vera_habitat.checkpoint import canonical_digest
    world = example_runtime()
    world.propose(Proposal("move-first", EffectClass.SIMULATION_ONLY,
                           "MOVE_ENTITY", "vera", Position3(1, 0, 0)))
    world.propose(Proposal("move-second", EffectClass.SIMULATION_ONLY,
                           "MOVE_ENTITY", "vera", Position3(2, 0, 0)))
    record = json.loads(world.export_checkpoint())
    record["receipts"][-1]["action_id"] = "move-first"
    record["seen_action_ids"] = ["move-first"]
    record["sha256"] = canonical_digest(record)
    with pytest.raises(ValueError):
        HabitatRuntime.from_checkpoint(json.dumps(record))


def test_legal_duplicate_rejection_history_still_roundtrips():
    world = example_runtime()
    move = Proposal("moved-once", EffectClass.SIMULATION_ONLY,
                    "MOVE_ENTITY", "vera", Position3(3, 0, 0))
    assert world.propose(move).accepted
    assert world.propose(move).disposition == "DUPLICATE_ACTION_ID"
    assert world.spawn(Entity("vera", "AVATAR", "home",
                              Position3(9, 0, 0))).disposition == "DUPLICATE_ENTITY_REJECTED"
    assert world.propose(Proposal("no-external", EffectClass.EXTERNAL_REQUEST,
                          "MOVE_ENTITY", "vera", Position3(7, 0, 0))).disposition == "EXTERNAL_EFFECT_UNAVAILABLE"
    checkpoint = world.export_checkpoint()
    result = HabitatRuntime.from_checkpoint(checkpoint)
    assert result.export_checkpoint() == checkpoint
    assert result.snapshot() == world.snapshot()
