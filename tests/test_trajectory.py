"""Read-only trajectory adapter; candidate moves are never submitted automatically."""
from dataclasses import dataclass

import pytest

from vera_habitat import Entity, HabitatRuntime, Position3
from vera_habitat.trajectory import preview_trajectory_moves


@dataclass(frozen=True)
class NumericalTrace:
    times: tuple[float, ...]
    states: tuple[tuple[float, ...], ...]


def trace():
    return NumericalTrace((0., .1, .2), ((1., 0.), (.99, -.2), (.95, -.4)))


def test_trajectory_preview_never_mutates_any_runtime():
    world = HabitatRuntime()
    world.spawn(Entity("avatar", "AVATAR", "room", Position3(1., 0., 0.)))
    rev = world.revision
    pending = preview_trajectory_moves(trace(), entity_id="avatar",
                                       action_prefix="example-001")
    assert len(pending) == 2  # skips initial state
    assert pending[0].action_id == "example-001:1"
    assert pending[0].target_position == Position3(.99, 0., 0.)
    assert all(p.effect_class.value == "SIMULATION_ONLY" for p in pending)
    assert world.revision == rev
    assert world.propose(pending[0]).accepted
    assert world.propose(pending[0]).disposition == "DUPLICATE_ACTION_ID"
    assert world.snapshot().entities[0].position == Position3(.99, 0., 0.)


def test_trajectory_length_and_monotonic_time_validation():
    invalid = [
        NumericalTrace((0., 0.), ((1., 0.), (2., 0.))),
        NumericalTrace((0., 1.), ((1., 0.),)),
        NumericalTrace((0., .1), ((1., 0.), (float("nan"), 0.))),
        NumericalTrace((0., .1), ((1., 0.), (2.,))),
    ]
    for value in invalid:
        with pytest.raises(ValueError):
            preview_trajectory_moves(value, entity_id="avatar",
                                     action_prefix="scenario")


def test_trajectory_explicit_budget_prevents_unbounded_proposals():
    with pytest.raises(ValueError):
        preview_trajectory_moves(trace(), entity_id="avatar",
                                 action_prefix="scenario", max_moves=1)
    with pytest.raises(ValueError):
        preview_trajectory_moves(trace(), entity_id="avatar",
                                 action_prefix="")
