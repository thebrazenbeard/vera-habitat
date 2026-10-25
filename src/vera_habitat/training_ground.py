"""Bounded, deterministic, simulation-only movement practice inside Vera Habitat.

This is a *toy* 2D model on Habitat's z=0 plane. Controller axes are synthetic
world axes, not calibrated ARK inputs. Obstacle rejection uses conservative
swept AABBs; this is not a game physics engine or collision certification.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from typing import Sequence

from .model import ActionProposal, EffectClass, Entity, Position3, SceneSnapshot, _finite_real
from .runtime import HabitatRuntime


def _real(value: object, name: str) -> float:
    if not _finite_real(value):
        raise ValueError(f"{name} must be a finite real number")
    return float(value)


@dataclass(frozen=True, slots=True)
class Obstacle2:
    entity_id: str
    left: float
    bottom: float
    right: float
    top: float

    def __post_init__(self) -> None:
        if not isinstance(self.entity_id, str) or not self.entity_id.strip():
            raise ValueError("obstacle ID must be nonempty")
        for name in ("left", "bottom", "right", "top"):
            _real(getattr(self, name), name)
        if self.left >= self.right or self.bottom >= self.top:
            raise ValueError("obstacle must have positive area")


@dataclass(frozen=True, slots=True)
class TrainingAction:
    """A dry-run MOVE or NOOP, with world-aligned synthetic stick directions."""
    kind: str
    x: float = 0.0
    y: float = 0.0
    duration_ms: int = 0
    dry_run: bool = True

    def __post_init__(self) -> None:
        if self.dry_run is not True:
            raise ValueError("live-output actions are forbidden")
        if self.kind not in ("MOVE", "NOOP"):
            raise ValueError("neutral V1 supports MOVE and NOOP only")
        for name in ("x", "y"):
            v = _real(getattr(self, name), name)
            if abs(v) > 1.0:
                raise ValueError(f"{name} must be in [-1,1]")
        if type(self.duration_ms) is not int or not 0 <= self.duration_ms <= 1000:
            raise ValueError("duration must be integer milliseconds in [0,1000]")
        if self.kind == "NOOP":
            if self.x != 0 or self.y != 0 or self.duration_ms != 0:
                raise ValueError("NOOP must have zero axes and duration")
        elif self.duration_ms < 1:
            raise ValueError("MOVE must have positive duration")


@dataclass(frozen=True, slots=True)
class TrainingObservation:
    scene: SceneSnapshot
    avatar: Position3
    goal: Position3
    distance_to_goal_m: float
    steps_taken: int
    reached_goal: bool
    finished: bool


@dataclass(frozen=True, slots=True)
class TrainingStep:
    index: int
    action: TrainingAction
    accepted: bool
    disposition: str
    revision_before: int
    revision_after: int
    reward: float
    observation: TrainingObservation


def _swept_aabb_hit(
    start: tuple[float, float],
    end: tuple[float, float],
    box: Obstacle2,
    expansion: float,
) -> bool:
    """Slab test on an obstacle conservatively inflated by avatar radius.

    An inflated AABB approximates a swept disc with possible corner false
    positives. Edge touches count as blocked candidates.
    """
    near, far = 0.0, 1.0
    for s, e, low, high in (
        (start[0], end[0], box.left - expansion, box.right + expansion),
        (start[1], end[1], box.bottom - expansion, box.top + expansion),
    ):
        velocity = e - s
        if velocity == 0.0:
            if s < low or s > high:
                return False
            continue
        a, b = (low - s) / velocity, (high - s) / velocity
        near = max(near, min(a, b))
        far = min(far, max(a, b))
        if near > far:
            return False
    return True


class NeutralTrainingGround:
    """Independent episode. Uses HabitatRuntime for accepted world mutations.

    Rejected candidate motion is kept in the training-step ledger; Habitat V1
    only receives valid MOVE_ENTITY proposals, never external requests.
    """

    ZONE = "neutral_training"
    AVATAR_ID = "vera"
    GOAL_ID = "goal"

    def __init__(
        self,
        *,
        width_m: float = 10.0,
        height_m: float = 10.0,
        speed_mps: float = 1.0,
        radius_m: float = 0.2,
        goal_radius_m: float = 0.3,
        max_steps: int = 40,
        start: tuple[float, float] = (1.0, 1.0),
        goal: tuple[float, float] = (9.0, 9.0),
        obstacles: Sequence[Obstacle2] = (Obstacle2("wall", 4.0, 0.0, 6.0, 7.0),),
        collision_backend: str = "habitat",
    ) -> None:
        self.width_m = _real(width_m, "width_m")
        self.height_m = _real(height_m, "height_m")
        self.speed_mps = _real(speed_mps, "speed_mps")
        self.radius_m = _real(radius_m, "radius_m")
        self.goal_radius_m = _real(goal_radius_m, "goal_radius_m")
        if (self.width_m <= 0 or self.height_m <= 0 or
                self.speed_mps <= 0 or self.radius_m <= 0 or
                self.goal_radius_m <= 0):
            raise ValueError("world, speed and radius values must be positive")
        if type(max_steps) is not int or not 1 <= max_steps <= 10000:
            raise ValueError("max_steps must be an integer from 1 to 10000")
        self.max_steps = max_steps
        if not isinstance(start, tuple) or not isinstance(goal, tuple) or len(start) != 2 or len(goal) != 2:
            raise ValueError("start and goal must be 2D tuples")
        self._start = tuple(_real(v, "start") for v in start)
        self._goal = tuple(_real(v, "goal") for v in goal)
        self._obstacles = tuple(obstacles)
        if any(not isinstance(box, Obstacle2) for box in self._obstacles):
            raise ValueError("all obstacles must be Obstacle2")
        ids = [box.entity_id for box in self._obstacles]
        if (len(set(ids)) != len(ids) or
                any(i in (self.AVATAR_ID, self.GOAL_ID) for i in ids)):
            raise ValueError("obstacle IDs must be unique and not reserved")
        if not self._within(self._start, self.radius_m):
            raise ValueError("avatar starts outside arena bounds")
        if not self._within(self._goal, self.goal_radius_m):
            raise ValueError("goal outside arena bounds")
        if hypot(self._goal[0] - self._start[0], self._goal[1] - self._start[1]) <= self.goal_radius_m:
            raise ValueError("start must not begin at the goal")
        for box in self._obstacles:
            if not (0 <= box.left < box.right <= self.width_m and
                    0 <= box.bottom < box.top <= self.height_m):
                raise ValueError("obstacle outside arena")
            if _swept_aabb_hit(self._start, self._start, box, self.radius_m):
                raise ValueError("avatar spawns inside obstacle margin")
            if _swept_aabb_hit(self._goal, self._goal, box, self.goal_radius_m):
                raise ValueError("goal overlaps obstacle margin")
        if type(collision_backend) is not str or collision_backend not in ("habitat", "physica"):
            raise ValueError("collision_backend must be habitat or physica")
        self.collision_backend = collision_backend
        self._physica_candidates = None
        if collision_backend == "physica":
            # Explicit opt-in: never import or install Physica by default.
            from .physica_adapter import PhysicaCandidates
            self._physica_candidates = PhysicaCandidates(self._obstacles)
        self._runtime = HabitatRuntime()
        self._runtime.spawn(Entity(self.AVATAR_ID, "AVATAR", self.ZONE,
                                   Position3(*self._start, 0.0)))
        self._runtime.spawn(Entity(self.GOAL_ID, "GOAL", self.ZONE,
                                   Position3(*self._goal, 0.0),
                                   {"radius_m": str(self.goal_radius_m)}))
        for box in sorted(self._obstacles, key=lambda b: b.entity_id):
            self._runtime.spawn(Entity(
                box.entity_id, "OBSTACLE", self.ZONE,
                Position3((box.left + box.right) / 2,
                          (box.bottom + box.top) / 2, 0.0),
                {"left": str(box.left), "right": str(box.right),
                 "bottom": str(box.bottom), "top": str(box.top)},
            ))
        self._steps: list[TrainingStep] = []
        self._reached_goal = False

    def _within(self, pos: tuple[float, float], radius: float) -> bool:
        return (radius <= pos[0] <= self.width_m - radius
                and radius <= pos[1] <= self.height_m - radius)

    @property
    def steps(self) -> tuple[TrainingStep, ...]:
        return tuple(self._steps)

    def observe(self) -> TrainingObservation:
        scene = self._runtime.snapshot()
        avatar = next(e.position for e in scene.entities if e.entity_id == self.AVATAR_ID)
        goal = next(e.position for e in scene.entities if e.entity_id == self.GOAL_ID)
        count = len(self._steps)
        return TrainingObservation(
            scene, avatar, goal, hypot(goal.x - avatar.x, goal.y - avatar.y),
            count, self._reached_goal, self._reached_goal or count >= self.max_steps,
        )

    def _obstacle_collision(self, start: tuple[float, float], end: tuple[float, float]) -> bool:
        if self._physica_candidates is None:
            return any(_swept_aabb_hit(start, end, b, self.radius_m)
                       for b in self._obstacles)
        candidates = self._physica_candidates.candidates(start, end, self.radius_m)
        # Shadow-check against Habitat's independent narrow swept-AABB test.
        # This deliberately spends extra work to catch provider false negatives.
        hits = {box.entity_id for box in self._obstacles
                if _swept_aabb_hit(start, end, box, self.radius_m)}
        if not hits.issubset(candidates):
            raise RuntimeError("Physica broad-phase missed Habitat collision candidate")
        return bool(hits)

    def step(self, action: TrainingAction) -> TrainingStep:
        if not isinstance(action, TrainingAction):
            raise TypeError("expected TrainingAction")
        before_obs = self.observe()
        if before_obs.finished:
            raise RuntimeError("episode is complete; start a new ground")
        rev = before_obs.scene.revision
        idx = len(self._steps) + 1
        disposition = "SIMULATION_NOOP"
        accepted = True
        if action.kind == "MOVE":
            old = (before_obs.avatar.x, before_obs.avatar.y)
            magnitude = max(1.0, hypot(action.x, action.y))
            travel = self.speed_mps * action.duration_ms / 1000.0
            end = (old[0] + action.x / magnitude * travel,
                   old[1] + action.y / magnitude * travel)
            if not all(isfinite(v) for v in end):
                disposition, accepted = "PREDICTION_NONFINITE_REJECTED", False
            elif not self._within(end, self.radius_m):
                disposition, accepted = "BOUNDARY_CANDIDATE_REJECTED", False
            elif self._obstacle_collision(old, end):
                disposition, accepted = "OBSTACLE_CANDIDATE_REJECTED", False
            else:
                proposal = ActionProposal(
                    action_id=f"neutral:{idx:05d}",
                    effect_class=EffectClass.SIMULATION_ONLY,
                    action="MOVE_ENTITY",
                    entity_id=self.AVATAR_ID,
                    target_position=Position3(*end, 0.0),
                )
                receipt = self._runtime.propose(proposal)
                if not receipt.accepted:
                    raise RuntimeError("Habitat unexpectedly rejected internal simulation move")
                disposition = receipt.disposition
        updated = self.observe()
        if accepted and updated.distance_to_goal_m <= self.goal_radius_m:
            self._reached_goal = True
            updated = self.observe()
        progress = before_obs.distance_to_goal_m - updated.distance_to_goal_m
        reward = (progress - 0.01 + (5.0 if self._reached_goal else 0.0)) if accepted else -0.25
        step = TrainingStep(idx, action, accepted, disposition, rev,
                            updated.scene.revision, reward,
                            TrainingObservation(
                                updated.scene, updated.avatar, updated.goal,
                                updated.distance_to_goal_m, idx,
                                self._reached_goal,
                                self._reached_goal or idx >= self.max_steps,
                            ))
        self._steps.append(step)
        return step


def render_ascii(observation: TrainingObservation, *, width: int = 10, height: int = 10) -> str:
    """Disposable top-down text projection; not authoritative state."""
    if type(width) is not int or type(height) is not int or not 1 <= width <= 100 or not 1 <= height <= 100:
        raise ValueError("invalid output grid size")
    canvas = [["." for _ in range(width)] for _ in range(height)]
    for entity in observation.scene.entities:
        if entity.kind != "OBSTACLE":
            continue
        a, b, c, d = (float(entity.metadata[k]) for k in ("left", "bottom", "right", "top"))
        for y in range(height):
            for x in range(width):
                if a <= x + .5 <= c and b <= y + .5 <= d:
                    canvas[y][x] = "#"
    for point, glyph in ((observation.goal, "G"), (observation.avatar, "V")):
        x, y = int(point.x), int(point.y)
        if 0 <= x < width and 0 <= y < height:
            canvas[y][x] = glyph
    return "\n".join("".join(row) for row in reversed(canvas))
