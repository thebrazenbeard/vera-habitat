"""Pure trajectory-to-proposal preview, compatible with Physica Trajectory data.

Neither imports a physics engine nor submits actions. Trajectory model adequacy
and units remain the producer's responsibility; these are only candidate,
simulation-scoped position proposals requiring separate Habitat acceptance.
"""
from __future__ import annotations

from itertools import islice
from math import isfinite

from .model import ActionProposal, EffectClass, Position3


# The public trajectory protocol may be backed by streaming iterables. A
# preview must bound *consumption* before trying to materialize them.
MAX_STATE_DIM = 1024
MAX_STATE_VALUES = 1_000_000


def preview_trajectory_moves(
    trajectory: object, *, entity_id: str, action_prefix: str,
    y: float = 0., z: float = 0., max_moves: int = 512,
) -> tuple[ActionProposal, ...]:
    """Translate states' first coordinate into explicitly bounded candidate moves.

    Accepts the public `times`/`states` protocol of `physica.Trajectory`,
    without installing/binding Physica to the Habitat control plane.
    The first state is initial and does not create a move.
    """
    if type(entity_id) is not str or not entity_id.strip():
        raise ValueError("entity_id must be a nonblank string")
    if type(action_prefix) is not str or not action_prefix.strip():
        raise ValueError("action_prefix must be a nonblank string")
    if type(max_moves) is not int or not 1 <= max_moves <= 10_000:
        raise ValueError("max_moves must be in [1, 10000]")
    if any(type(v) not in (float, int) or not isfinite(v) for v in (y, z)):
        raise ValueError("projection y,z must be finite real coordinates")
    try:
        times = tuple(islice(trajectory.times, max_moves + 2))
    except (AttributeError, TypeError) as exc:
        raise ValueError("trajectory needs finite times and state vectors") from exc
    if not 2 <= len(times) <= max_moves + 1:
        raise ValueError("trajectory exceeds configured candidate budget")
    try:
        state_source = trajectory.states
        states = []
        total_values = 0
        for row in islice(state_source, max_moves + 2):
            state = tuple(islice(row, MAX_STATE_DIM + 1))
            if len(state) > MAX_STATE_DIM:
                raise ValueError("trajectory state dimension exceeds budget")
            total_values += len(state)
            if total_values > MAX_STATE_VALUES:
                raise ValueError("trajectory state value budget exceeded")
            states.append(state)
    except (AttributeError, TypeError) as exc:
        raise ValueError("trajectory needs finite times and state vectors") from exc
    if len(states) != len(times) or len(states) > max_moves + 1:
        raise ValueError("trajectory exceeds configured candidate budget")
    if any(type(t) not in (float, int) or not isfinite(t) for t in times):
        raise ValueError("trajectory times must be finite numeric values")
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("trajectory times must strictly increase")
    dim = len(states[0])
    if dim < 1 or any(len(s) != dim for s in states):
        raise ValueError("trajectory states must have fixed positive dimension")
    if any(type(v) not in (float, int) or not isfinite(v)
           for state in states for v in state):
        raise ValueError("trajectory states must be finite numeric values")
    return tuple(
        ActionProposal(
            action_id=f"{action_prefix}:{index}",
            effect_class=EffectClass.SIMULATION_ONLY,
            action="MOVE_ENTITY",
            entity_id=entity_id,
            target_position=Position3(float(state[0]), float(y), float(z)),
        )
        for index, state in enumerate(states[1:], 1)
    )
