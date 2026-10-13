"""Read-only 3D broad-phase AABB candidates bound to a Habitat scene revision.

No rigid-body integration, narrow-phase contact, impulses, actuator control,
or automatic mutations. Inspired by broad-phase separation in Box2D/Jolt.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .model import Position3, SceneSnapshot


@dataclass(frozen=True, slots=True)
class AABB3:
    entity_id: str
    zone: str
    lower: Position3
    upper: Position3

    def __post_init__(self) -> None:
        if type(self.entity_id) is not str or not self.entity_id.strip():
            raise ValueError("entity_id must be a nonblank string")
        if type(self.zone) is not str or not self.zone.strip():
            raise ValueError("zone must be a nonblank string")
        if not isinstance(self.lower, Position3) or not isinstance(self.upper, Position3):
            raise ValueError("AABB3 requires typed Position3 bounds")
        if any(a > b for a, b in zip(
            (self.lower.x, self.lower.y, self.lower.z),
            (self.upper.x, self.upper.y, self.upper.z)
        )):
            raise ValueError("AABB3 bounds cannot be reversed")


def _validate_bounds(boxes: Sequence[AABB3]) -> tuple[AABB3, ...]:
    result = tuple(boxes)
    if any(not isinstance(box, AABB3) for box in result):
        raise ValueError("all volumes must be AABB3 instances")
    if len({box.entity_id for box in result}) != len(result):
        raise ValueError("each entity may have only one AABB3 in this projection")
    return result


def _overlap(left: AABB3, right: AABB3) -> bool:
    if left.zone != right.zone:
        return False
    return all(a <= d and c <= b for a, b, c, d in zip(
        (left.lower.x, left.lower.y, left.lower.z),
        (left.upper.x, left.upper.y, left.upper.z),
        (right.lower.x, right.lower.y, right.lower.z),
        (right.upper.x, right.upper.y, right.upper.z),
    ))


def brute_force_candidates(boxes: Sequence[AABB3]) -> tuple[tuple[str, str], ...]:
    """Independent O(n²) 3D overlap oracle; touching faces are candidates."""
    items = _validate_bounds(boxes)
    result = []
    for i, left in enumerate(items):
        for right in items[i + 1:]:
            if _overlap(left, right):
                result.append(tuple(sorted((left.entity_id, right.entity_id))))
    return tuple(sorted(result))


@dataclass(frozen=True)
class SpatialProjection:
    """Disposable spatial *view*; does not own or mutate Habitat world state."""
    revision: int
    bounds: tuple[AABB3, ...]

    @classmethod
    def from_scene(
        cls, snapshot: SceneSnapshot, boxes: Sequence[AABB3]
    ) -> "SpatialProjection":
        if not isinstance(snapshot, SceneSnapshot):
            raise ValueError("spatial projection requires a SceneSnapshot")
        volumes = _validate_bounds(boxes)
        zones = {e.entity_id: e.zone for e in snapshot.entities}
        for item in volumes:
            if item.entity_id not in zones:
                raise ValueError("unknown entity cannot be projected")
            if zones[item.entity_id] != item.zone:
                raise ValueError("AABB3 zone must match scene entity zone")
        return cls(snapshot.revision, tuple(volumes))

    def candidate_pairs(self) -> tuple[tuple[str, str], ...]:
        """Return sorted broad-phase *candidates*, not actual shape contacts."""
        ordered = sorted(self.bounds, key=lambda x: (x.lower.x, x.entity_id))
        active: list[AABB3] = []
        result: set[tuple[str, str]] = set()
        for current in ordered:
            active = [b for b in active if b.upper.x >= current.lower.x]
            for other in active:
                if (other.zone == current.zone
                        and other.lower.y <= current.upper.y
                        and current.lower.y <= other.upper.y
                        and other.lower.z <= current.upper.z
                        and current.lower.z <= other.upper.z):
                    result.add(tuple(sorted((other.entity_id, current.entity_id))))
            active.append(current)
        return tuple(sorted(result))
