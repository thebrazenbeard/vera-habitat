"""Optional Physica broad-phase adapter: candidate pairs, never contacts.

Uses the installed Physica distribution at explicit request only.
Habitat's own swept-AABB collision result remains the fail-closed reference.
No code, model, network connection or actuator is copied or installed here.
"""
from __future__ import annotations

from importlib import import_module
from math import isfinite
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .training_ground import Obstacle2


class PhysicaCandidates:
    """Translate bounded swept motion into Physica AABB candidate queries."""

    def __init__(self, obstacles: tuple[Obstacle2, ...]) -> None:
        try:
            spatial = import_module("physica.spatial")
        except ImportError as exc:
            raise ImportError(
                "Physica backend requires a separately installed physica.spatial"
            ) from exc
        self._AABB = spatial.AABB
        self._pairs = spatial.broad_phase_pairs
        ids = {b.entity_id for b in obstacles}
        motion_id = "__habitat_motion__"
        while motion_id in ids:
            motion_id += "_"
        self._motion_id = motion_id
        self._obstacle_ids = frozenset(ids)
        self._boxes = tuple(
            self._AABB(b.entity_id, (b.left, b.bottom), (b.right, b.top))
            for b in obstacles
        )

    def candidates(
        self, start: tuple[float, float], end: tuple[float, float], radius: float
    ) -> frozenset[str]:
        if (type(radius) not in (float, int) or not isfinite(radius)
                or radius < 0 or len(start) != 2 or len(end) != 2
                or any(type(v) not in (float, int) or not isfinite(v)
                       for v in (*start, *end))):
            raise ValueError("invalid swept motion envelope")
        motion = self._AABB(
            self._motion_id,
            (min(start[0], end[0]) - radius,
             min(start[1], end[1]) - radius),
            (max(start[0], end[0]) + radius,
             max(start[1], end[1]) + radius),
        )
        pairs = self._pairs((*self._boxes, motion))
        candidates = set()
        for pair in pairs:
            if type(pair) is not tuple or len(pair) != 2:
                raise RuntimeError("malformed Physica candidate pair")
            left, right = pair
            if self._motion_id in pair:
                other = right if left == self._motion_id else left
                if other not in self._obstacle_ids:
                    raise RuntimeError("unknown Physica candidate ID")
                candidates.add(other)
        return frozenset(candidates)
