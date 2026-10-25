from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from types import MappingProxyType
from typing import Mapping
from uuid import uuid4


def _nonempty(value: str, field_name: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{field_name} must be text")
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} must not be empty")
    _require_utf8(value, field_name)
    return value


def _require_utf8(value: str, field_name: str) -> None:
    """Keep accepted runtime text representable by checkpoint UTF-8 JSON."""
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{field_name} must be valid UTF-8 text") from exc


def _finite_real(value: object) -> bool:
    """Reject nonnumeric, Boolean and unrepresentably large coordinates."""
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


@dataclass(frozen=True, slots=True)
class Position3:
    x: float
    y: float
    z: float

    def __post_init__(self) -> None:
        if not all(_finite_real(v) for v in (self.x, self.y, self.z)):
            raise ValueError("coordinates must be finite")


@dataclass(frozen=True, slots=True)
class Entity:
    entity_id: str
    kind: str
    zone: str
    position: Position3
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "entity_id", _nonempty(self.entity_id, "entity_id"))
        object.__setattr__(self, "kind", _nonempty(self.kind, "kind"))
        object.__setattr__(self, "zone", _nonempty(self.zone, "zone"))
        metadata = dict(self.metadata)
        for key, value in metadata.items():
            if type(key) is str:
                _require_utf8(key, "metadata key")
            if type(value) is str:
                _require_utf8(value, "metadata value")
        object.__setattr__(self, "metadata", MappingProxyType(metadata))


class EffectClass(str, Enum):
    SIMULATION_ONLY = "SIMULATION_ONLY"
    EXTERNAL_REQUEST = "EXTERNAL_REQUEST"


@dataclass(frozen=True, slots=True)
class ActionProposal:
    action_id: str
    effect_class: EffectClass
    action: str
    entity_id: str
    target_position: Position3 | None = None

    @classmethod
    def move(cls, entity_id: str, target: Position3) -> "ActionProposal":
        return cls(
            action_id=str(uuid4()),
            effect_class=EffectClass.SIMULATION_ONLY,
            action="MOVE_ENTITY",
            entity_id=entity_id,
            target_position=target,
        )


@dataclass(frozen=True, slots=True)
class ActionReceipt:
    action_id: str
    accepted: bool
    disposition: str
    revision_before: int
    revision_after: int


@dataclass(frozen=True, slots=True)
class SceneSnapshot:
    schema_version: str
    revision: int
    entities: tuple[Entity, ...]
