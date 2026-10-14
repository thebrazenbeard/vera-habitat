"""Cross-repository Physica integration qualification, not contact physics.

This module intentionally skips without Physica in the ordinary local suite.
The separately pinned CI job MUST install Physica and execute these tests.
"""
from random import Random

import pytest

spatial = pytest.importorskip("physica.spatial")
from vera_habitat.training_ground import (
    NeutralTrainingGround, Obstacle2, TrainingAction,
)


def world(*, backend: str = "habitat", obstacle_id: str = "wall"):
    return NeutralTrainingGround(
        start=(3.0, 3.0), goal=(9.0, 9.0), speed_mps=1.0,
        max_steps=45, collision_backend=backend,
        obstacles=(Obstacle2(obstacle_id, 4.0, 2.0, 6.0, 7.0),),
    )


def test_actual_physica_broadphase_rejects_swept_wall_and_preserves_receipts():
    normal = world()
    physical = world(backend="physica")
    action = TrainingAction("MOVE", 1.0, 0.0, 1000)
    a, b = normal.step(action), physical.step(action)
    assert not a.accepted and not b.accepted
    assert a.disposition == b.disposition == "OBSTACLE_CANDIDATE_REJECTED"
    assert a.revision_before == b.revision_before
    assert a.revision_after == b.revision_after
    assert physical.observe().avatar == normal.observe().avatar


def test_random_action_sequences_match_internal_shadow_oracle():
    for seed in range(12):
        rng = Random(seed + 214)
        normal = world()
        physical = world(backend="physica")
        for _ in range(40):
            if normal.observe().finished:
                assert physical.observe().finished
                break
            action = TrainingAction(
                "MOVE", rng.choice((-1, 0, 1)), rng.choice((-1, 0, 1)),
                rng.choice((200, 500, 1000)),
            )
            a, b = normal.step(action), physical.step(action)
            assert (a.accepted, a.disposition, a.reward,
                    a.revision_after, a.observation.avatar) == (
                    b.accepted, b.disposition, b.reward,
                    b.revision_after, b.observation.avatar)
        assert normal.observe() == physical.observe()


def test_physica_candidate_false_negative_fails_closed(monkeypatch):
    ground = world(backend="physica")
    before = ground.observe()
    monkeypatch.setattr(ground._physica_candidates, "_pairs", lambda items: ())
    with pytest.raises(RuntimeError, match="missed"):
        ground.step(TrainingAction("MOVE", 1.0, 0.0, 1000))
    assert ground.observe() == before
    assert not ground.steps


def test_candidate_false_positive_does_not_override_habitat_narrow_check(monkeypatch):
    ground = world(backend="physica")
    motion = ground._physica_candidates._motion_id
    monkeypatch.setattr(
        ground._physica_candidates, "_pairs",
        lambda items: ((motion, "wall"),),
    )
    step = ground.step(TrainingAction("MOVE", -1.0, 0.0, 500))
    assert step.accepted and step.disposition == "SIMULATION_MOVE_APPLIED"


def test_internal_motion_identifier_never_collides_with_obstacle_ids():
    ground = world(backend="physica", obstacle_id="__habitat_motion__")
    assert ground._physica_candidates._motion_id != "__habitat_motion__"
    step = ground.step(TrainingAction("MOVE", 1.0, 0.0, 1000))
    assert not step.accepted
    assert step.disposition == "OBSTACLE_CANDIDATE_REJECTED"


def test_invalid_backend_rejected_and_default_requires_no_optin():
    with pytest.raises(ValueError, match="collision_backend"):
        world(backend="unknown")
    assert world().collision_backend == "habitat"
    assert world(backend="physica").collision_backend == "physica"


def test_broadphase_malformed_pair_fails_before_world_mutation(monkeypatch):
    ground = world(backend="physica")
    before = ground.observe()
    monkeypatch.setattr(ground._physica_candidates, "_pairs", lambda items: ((1,),))
    with pytest.raises(RuntimeError, match="malformed"):
        ground.step(TrainingAction("MOVE", 1.0, 0.0, 1000))
    assert ground.observe() == before
