import math

import pytest

from vera_habitat.training_ground import (
    NeutralTrainingGround, Obstacle2, TrainingAction, render_ascii,
)


def move(x=0.0, y=0.0, ms=1000):
    return TrainingAction("MOVE", x=x, y=y, duration_ms=ms)


def test_deterministic_world_and_snapshot_projection():
    a, b = NeutralTrainingGround(), NeutralTrainingGround()
    assert a.observe() == b.observe()
    assert "V" in render_ascii(a.observe())
    assert "G" in render_ascii(a.observe())
    assert "#" in render_ascii(a.observe())
    assert len(render_ascii(a.observe()).splitlines()) == 10
    before = a.observe().scene.revision
    render_ascii(a.observe())
    assert a.observe().scene.revision == before
    for action in (move(1), move(1), move(y=1), TrainingAction("NOOP")):
        assert a.step(action) == b.step(action)
    assert a.steps == b.steps


def test_swept_obstacle_prevents_tunneling_without_revision_mutation():
    g = NeutralTrainingGround(speed_mps=8.0)
    before = g.observe()
    blocked = g.step(move(1))
    assert not blocked.accepted
    assert blocked.disposition == "OBSTACLE_CANDIDATE_REJECTED"
    assert blocked.revision_before == blocked.revision_after == before.scene.revision
    assert blocked.observation.avatar == before.avatar
    assert blocked.reward < 0
    assert len(g.steps) == 1


def test_boundary_rejects_without_mutation():
    g = NeutralTrainingGround()
    before = g.observe().scene.revision
    # One metre to the left from x=1 is outside the avatar-radius margin.
    step = g.step(move(-1))
    assert not step.accepted
    assert step.disposition == "BOUNDARY_CANDIDATE_REJECTED"
    assert step.revision_before == step.revision_after == before


def test_detour_reaches_goal_after_blocked_trial():
    g = NeutralTrainingGround()
    assert g.step(move(1)).accepted  # x=2
    assert g.step(move(1)).accepted  # x=3
    assert not g.step(move(1)).accepted  # x=4 would touch inflated wall
    for _ in range(7):
        assert g.step(move(y=1)).accepted  # y=8
    for _ in range(6):
        assert g.step(move(1)).accepted  # x=9
    goal_step = g.step(move(y=1))
    assert goal_step.accepted
    assert goal_step.observation.reached_goal
    assert goal_step.observation.finished
    assert goal_step.reward > 4
    assert goal_step.observation.avatar.x == 9
    assert goal_step.observation.avatar.y == 9
    with pytest.raises(RuntimeError, match="complete"):
        g.step(move(1))


def test_terminal_step_budget_on_rejections_and_noops():
    g = NeutralTrainingGround(max_steps=2)
    first = g.step(TrainingAction("NOOP"))
    assert first.accepted
    assert first.revision_before == first.revision_after
    last = g.step(move(-1))
    assert not last.accepted
    assert last.observation.finished
    assert not last.observation.reached_goal
    with pytest.raises(RuntimeError):
        g.step(TrainingAction("NOOP"))


@pytest.mark.parametrize("kwargs", [
    {"kind": "INTERACT"},
    {"kind": "LOOK"},
    {"kind": "MOVE", "duration_ms": 1001},
    {"kind": "MOVE", "duration_ms": 1.5},
    {"kind": "MOVE", "duration_ms": True},
    {"kind": "MOVE", "duration_ms": 0},
    {"kind": "MOVE", "duration_ms": 20, "x": float("nan")},
    {"kind": "MOVE", "duration_ms": 20, "x": float("inf")},
    {"kind": "MOVE", "duration_ms": 20, "x": 1.2},
    {"kind": "MOVE", "duration_ms": 20, "x": True},
    {"kind": "MOVE", "duration_ms": 20, "dry_run": False},
    {"kind": "NOOP", "x": 0.2},
    {"kind": "NOOP", "duration_ms": 2},
])
def test_invalid_action_fails_closed(kwargs):
    with pytest.raises(ValueError):
        TrainingAction(**kwargs)


def test_diagonal_input_has_no_speed_bonus():
    g = NeutralTrainingGround(obstacles=())
    before = g.observe().avatar
    step = g.step(move(1, 1))
    distance = math.hypot(step.observation.avatar.x - before.x,
                          step.observation.avatar.y - before.y)
    assert distance == pytest.approx(1.0)
    assert step.accepted


@pytest.mark.parametrize("kwargs", [
    {"start": (-1.0, 1.0)},
    {"goal": (11.0, 5.0)},
    {"max_steps": 0},
    {"speed_mps": 0.0},
    {"radius_m": float("inf")},
    {"goal": (1.0, 1.0)},
    {"obstacles": (Obstacle2("wall", 0.0, 0.0, 2.0, 2.0),)},
    {"obstacles": (Obstacle2("goal", 4.0, 0.0, 6.0, 7.0),)},
    {"obstacles": (Obstacle2("wall", 4.0, 0.0, 6.0, 7.0),) * 2},
])
def test_invalid_world_rejected(kwargs):
    with pytest.raises(ValueError):
        NeutralTrainingGround(**kwargs)


def test_rejected_action_type_has_no_world_effect():
    g = NeutralTrainingGround()
    before = g.observe()
    with pytest.raises(TypeError):
        g.step({"kind": "MOVE", "x": 1})
    assert g.observe() == before


def test_corner_touch_conservatively_blocked():
    g = NeutralTrainingGround(
        start=(1, 1), goal=(7, 7), width_m=8, height_m=8,
        speed_mps=4, obstacles=(Obstacle2("square", 3.0, 3.0, 4.0, 4.0),),
    )
    assert not g.step(move(1, 1)).accepted
