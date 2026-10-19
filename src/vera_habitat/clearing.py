"""A tiny deterministic, simulation-only scene for The Clearing.

This is object state and prediction accounting, not physical simulation.
There is no controller, automatic agent, model, network or memory route.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import dist

from .model import ActionProposal, EffectClass, Entity, Position3
from .rendering import render_scene_json
from .runtime import HabitatRuntime

# Named positions are layout seeds, not collision geometry or physics bodies.
_SCENE = (
    ("avatar", "AVATAR", "workshop", (2.0, 2.0, 0.0)),
    ("workshop_floor", "LANDMARK", "workshop", (2.5, 2.5, 0.0)),
    ("workbench", "PROP", "workshop", (4.0, 2.0, 0.0)),
    ("lamp", "PROP", "workshop", (4.0, 2.5, 1.0)),
    ("doorway", "LANDMARK", "threshold", (5.0, 5.0, 0.0)),
    ("clearing_center", "LANDMARK", "clearing", (8.0, 8.0, 0.0)),
    ("tree_west", "LANDMARK", "clearing", (6.0, 10.0, 0.0)),
    ("tree_east", "LANDMARK", "clearing", (11.0, 8.0, 0.0)),
    ("stone", "PROP", "clearing", (8.0, 9.0, 0.0)),
)


@dataclass(frozen=True, slots=True)
class PredictionTrial:
    """Observed result of one proposed simulated repositioning action.

    The prediction is caller-provided, never privileged world truth.
    The hash is for deterministic comparison, not writer authentication.
    """
    action_id: str
    entity_id: str
    accepted: bool
    disposition: str
    revision_before: int
    revision_after: int
    predicted: Position3
    observed: Position3
    error_m: float
    snapshot_sha256: str


def make_clearing() -> HabitatRuntime:
    """Create a fresh scene. No filesystem or external effects."""
    world = HabitatRuntime()
    for identifier, kind, zone, coordinates in _SCENE:
        receipt = world.spawn(Entity(
            identifier, kind, zone, Position3(*coordinates),
            {"layout": "the-clearing-v0", "physics": "UNQUALIFIED"},
        ))
        assert receipt.accepted  # a programming invariant of the static layout
    return world


def _position(world: HabitatRuntime, identifier: str) -> Position3:
    return next(entity.position for entity in world.snapshot().entities
                if entity.entity_id == identifier)


def run_prediction_trial(
    world: HabitatRuntime,
    *,
    action_id: str,
    entity_id: str,
    target: Position3,
    predicted: Position3,
) -> PredictionTrial:
    """Compare a prediction to one ordinary Habitat simulation action.

    This V0 move is a reposition, not a force- or collision-governed motion.
    """
    if not isinstance(world, HabitatRuntime):
        raise TypeError("world must be HabitatRuntime")
    if not isinstance(target, Position3) or not isinstance(predicted, Position3):
        raise TypeError("target and prediction must be typed positions")
    _position(world, entity_id)  # unknown object fails without mutating state
    receipt = world.propose(ActionProposal(
        action_id=action_id, effect_class=EffectClass.SIMULATION_ONLY,
        action="MOVE_ENTITY", entity_id=entity_id, target_position=target,
    ))
    observed = _position(world, entity_id)
    projection = render_scene_json(world.snapshot())
    return PredictionTrial(
        action_id=action_id, entity_id=entity_id,
        accepted=receipt.accepted, disposition=receipt.disposition,
        revision_before=receipt.revision_before,
        revision_after=receipt.revision_after,
        predicted=predicted, observed=observed,
        error_m=dist(
            (predicted.x, predicted.y, predicted.z),
            (observed.x, observed.y, observed.z),
        ),
        snapshot_sha256=sha256(projection.encode("utf-8")).hexdigest(),
    )
