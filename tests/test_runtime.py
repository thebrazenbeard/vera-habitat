from vera_habitat import ActionProposal, EffectClass, Entity, HabitatRuntime, Position3
from vera_habitat.model import ActionProposal as Proposal


def test_simulation_move_advances_revision_once():
    runtime = HabitatRuntime()
    runtime.spawn(Entity("vera", "AVATAR", "home", Position3(0, 0, 0)))
    before = runtime.revision
    receipt = runtime.propose(ActionProposal.move("vera", Position3(2, 0, 1)))
    assert receipt.accepted is True
    assert receipt.revision_before == before
    assert receipt.revision_after == before + 1
    assert runtime.snapshot().entities[0].position == Position3(2, 0, 1)


def test_external_effect_rejected_without_mutation():
    runtime = HabitatRuntime()
    runtime.spawn(Entity("vera", "AVATAR", "home", Position3(0, 0, 0)))
    before = runtime.revision
    proposal = Proposal(
        action_id="external-1",
        effect_class=EffectClass.EXTERNAL_REQUEST,
        action="MOVE_ENTITY",
        entity_id="vera",
        target_position=Position3(3, 0, 0),
    )
    receipt = runtime.propose(proposal)
    assert receipt.accepted is False
    assert receipt.disposition == "EXTERNAL_EFFECT_UNAVAILABLE"
    assert runtime.revision == before


def test_snapshot_is_sorted_and_non_authoritative_projection():
    runtime = HabitatRuntime()
    runtime.spawn(Entity("zeta", "OBJECT", "room", Position3(0, 0, 0)))
    runtime.spawn(Entity("alpha", "OBJECT", "room", Position3(1, 0, 0)))
    snapshot = runtime.snapshot()
    assert [item.entity_id for item in snapshot.entities] == ["alpha", "zeta"]
