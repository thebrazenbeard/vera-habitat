"""Optional Physica broad-phase adapter: candidate pairs, never contacts.

Uses the installed Physica distribution at explicit request only.
Habitat's own swept-AABB collision result remains the fail-closed reference.
No code, model, network connection or actuator is copied or installed here.
"""
from __future__ import annotations

from fractions import Fraction
from importlib import import_module
from math import inf, isfinite, nextafter, ulp
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
        self._swept_pairs = getattr(spatial, "swept_broad_phase_pairs", None)
        if not callable(self._swept_pairs):
            raise ImportError("Physica swept backend requires swept_broad_phase_pairs")
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
        # Physica now retains exact rational input geometry while Habitat's
        # independent slab test performs rounded subtract/divide operations.
        # Near inclusive edge/corner contacts those two representations can
        # disagree even at ordinary scales. Pad the *candidate* query by a
        # small scale-relative binary64 error budget; Habitat still makes the
        # actual rejection decision and detects truly missing candidates.
        bounds = []
        for s, e in zip(start, end):
            guard = 8 * ulp(max(abs(s), abs(e), radius))
            low, high = s - radius - guard, s + radius + guard
            # A finite Habitat world can approach the edge of binary64. If
            # outward padding overflows, return every known obstacle as an
            # unpruned candidate superset. This preserves Habitat's own slab
            # decision without passing an invalid AABB to Physica.
            if not isfinite(guard) or not isfinite(low) or not isfinite(high):
                return self._obstacle_ids
            padded = (nextafter(low, -inf), nextafter(high, inf))
            if not all(isfinite(value) for value in padded):
                return self._obstacle_ids
            bounds.append(padded)

        # The rounded displacement can stop short of a supplied endpoint
        # after severe cancellation. Round it outward in the actual travel
        # direction, using exact comparisons of the finite input floats.
        motion_delta = []
        for s, e in zip(start, end):
            delta = e - s
            if not isfinite(delta):
                return self._obstacle_ids
            exact_delta = Fraction(e) - Fraction(s)
            if e > s and Fraction(delta) < exact_delta:
                delta = nextafter(delta, inf)
            elif e < s and Fraction(delta) > exact_delta:
                delta = nextafter(delta, -inf)
            if not isfinite(delta):
                return self._obstacle_ids
            motion_delta.append(delta)

        motion = self._AABB(
            self._motion_id,
            (bounds[0][0], bounds[1][0]),
            (bounds[0][1], bounds[1][1]),
        )
        deltas = {box.id: (0.0, 0.0) for box in self._boxes}
        deltas[self._motion_id] = tuple(motion_delta)
        pairs = self._swept_pairs((*self._boxes, motion), deltas)
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
