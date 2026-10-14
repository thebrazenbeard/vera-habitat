"""Seeded, offline navigation evaluation over the Vera Habitat neutral ground.

Only the observation DTO reaches ordinary policies. The full-map A* oracle is
explicitly privileged, not comparable to restricted-observation policies as a
fair agent benchmark. No runtime route, network client, or actuator exists here.
"""
from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from math import hypot, isfinite
from random import Random
from typing import Protocol, Sequence

from .training_ground import (
    NeutralTrainingGround, Obstacle2, TrainingAction, _swept_aabb_hit,
)

TRAIN_SEEDS = tuple(range(20))
HOLDOUT_SEEDS = tuple(range(1000, 1020))


def _integer(value: object, name: str) -> int:
    if type(value) is not int or not 0 <= value < 2**32:
        raise ValueError(f"{name} must be an integer seed in [0, 2**32)")
    return value


@dataclass(frozen=True, slots=True)
class Scenario:
    seed: int
    obstacles: tuple[Obstacle2, ...]
    start: tuple[float, float] = (1.0, 2.0)
    goal: tuple[float, float] = (8.0, 8.0)
    width_m: float = 10.0
    height_m: float = 10.0
    avatar_radius_m: float = 0.2
    speed_mps: float = 1.0


def make_scenario(seed: int) -> Scenario:
    """Create repeatable barrier-and-gap layouts with nonoverlapping splits."""
    _integer(seed, "seed")
    rng = Random(seed)
    left = rng.choice((3.4, 3.8, 4.2, 4.6))
    right = left + rng.choice((0.8, 1.0))
    # Half the cases demand a detour *away* from the direct goal heading.
    # Crossing at y=1 or y=9 remains possible for a radius-0.2 avatar.
    if rng.randrange(2):
        edge = rng.choice((6.5, 8.5))
        wall = Obstacle2("barrier", left, 0.0, right, edge)
    else:
        edge = rng.choice((1.5, 3.5))
        wall = Obstacle2("barrier", left, edge, right, 10.0)
    return Scenario(seed=seed, obstacles=(wall,))


@dataclass(frozen=True, slots=True)
class VisibleObstacle:
    """Bounds relative to avatar and cropped to square sensor range."""
    bounds_relative: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class AgentObservation:
    """Synthetic pose/waypoint observations; NO scene, map or world revision."""
    position_xy: tuple[float, float]
    goal_offset_xy: tuple[float, float]
    visible_obstacles: tuple[VisibleObstacle, ...]
    remaining_steps: int
    last_disposition: str


@dataclass(frozen=True, slots=True)
class StepFeedback:
    observation: AgentObservation
    accepted: bool
    disposition: str
    reward: float
    terminated: bool
    truncated: bool


class NavigationEpisode:
    """Explicit reset/step interface; world truth never passed to policy."""
    def __init__(self, seed: int, *, sensor_range_m: float = 2.0,
                 max_steps: int = 40, family: str = "barrier"):
        if type(sensor_range_m) not in (int, float) or (
                not isfinite(sensor_range_m) or sensor_range_m <= 0):
            raise ValueError("sensor_range_m must be positive and finite")
        if type(max_steps) is not int or not 1 <= max_steps <= 10000:
            raise ValueError("max_steps must be an integer in [1,10000]")
        if family not in ("barrier", "zigzag"):
            raise ValueError("unknown scenario family")
        self.family = family
        self.sensor_range_m = float(sensor_range_m)
        self.max_steps = max_steps
        self.scenario: Scenario
        self._world: NeutralTrainingGround
        self._last_disposition: str
        self.reset(seed)

    def reset(self, seed: int) -> AgentObservation:
        self.scenario = (make_scenario(seed) if self.family == "barrier"
                         else make_zigzag_scenario(seed))
        s = self.scenario
        self._world = NeutralTrainingGround(
            width_m=s.width_m, height_m=s.height_m,
            speed_mps=s.speed_mps, radius_m=s.avatar_radius_m,
            max_steps=self.max_steps, start=s.start, goal=s.goal,
            obstacles=s.obstacles,
        )
        self._last_disposition = "RESET"
        return self.observe()

    def observe(self) -> AgentObservation:
        internal = self._world.observe()
        x, y = internal.avatar.x, internal.avatar.y
        range_m = self.sensor_range_m
        visible: list[VisibleObstacle] = []
        # Crop obstacles to sensor footprint. IDs and uncropped box bounds
        # never appear in the observation (even if part is visible).
        for box in self.scenario.obstacles:
            left, right = max(box.left, x - range_m), min(box.right, x + range_m)
            bottom, top = max(box.bottom, y - range_m), min(box.top, y + range_m)
            if left <= right and bottom <= top:
                visible.append(VisibleObstacle((
                    left - x, bottom - y, right - x, top - y,
                )))
        return AgentObservation(
            (x, y), (internal.goal.x - x, internal.goal.y - y),
            tuple(visible), self.max_steps - internal.steps_taken,
            self._last_disposition,
        )

    def step(self, action: TrainingAction) -> StepFeedback:
        receipt = self._world.step(action)
        self._last_disposition = receipt.disposition
        observation = self.observe()
        return StepFeedback(
            observation=observation,
            accepted=receipt.accepted,
            disposition=receipt.disposition,
            reward=receipt.reward,
            terminated=receipt.observation.reached_goal,
            truncated=(receipt.observation.finished and
                       not receipt.observation.reached_goal),
        )


class Policy(Protocol):
    def choose_action(self, observation: AgentObservation) -> TrainingAction: ...


def _move(x: int, y: int) -> TrainingAction:
    return TrainingAction("MOVE", float(x), float(y), duration_ms=1000)


class GreedyPolicy:
    """Local goal-heading baseline; may become stuck at obstacles."""
    def choose_action(self, observation: AgentObservation) -> TrainingAction:
        dx, dy = observation.goal_offset_xy
        if hypot(dx, dy) <= .3:
            return TrainingAction("NOOP")
        if abs(dx) >= abs(dy):
            return _move(1 if dx > 0 else -1, 0)
        return _move(0, 1 if dy > 0 else -1)


class RandomPolicy:
    """Seeded random cardinal movement; never sees the world map."""
    def __init__(self, seed: int):
        self._rng = Random(_integer(seed, "seed"))

    def choose_action(self, observation: AgentObservation) -> TrainingAction:
        del observation
        dx, dy = self._rng.choice(((1, 0), (-1, 0), (0, 1), (0, -1)))
        return _move(dx, dy)


def _grid_path(scenario: Scenario, start: tuple[int, int]) -> tuple[tuple[int, int], ...]:
    """Reference shortest 4-neighbor path in *this* integer-grid abstraction."""
    goal = (round(scenario.goal[0]), round(scenario.goal[1]))
    radius = scenario.avatar_radius_m
    def clear(a: tuple[int, int], b: tuple[int, int]) -> bool:
        if not (radius <= b[0] <= scenario.width_m - radius
                and radius <= b[1] <= scenario.height_m - radius):
            return False
        return not any(_swept_aabb_hit(a, b, box, radius)
                       for box in scenario.obstacles)

    frontier: list[tuple[int, int, tuple[int, int]]] = []
    heappush(frontier, (abs(start[0]-goal[0]) + abs(start[1]-goal[1]), 0, start))
    costs: dict[tuple[int, int], int] = {start: 0}
    parents: dict[tuple[int, int], tuple[int, int]] = {}
    while frontier:
        _, cost, point = heappop(frontier)
        if cost != costs.get(point):
            continue
        if point == goal:
            path = [point]
            while path[-1] != start:
                path.append(parents[path[-1]])
            return tuple(reversed(path))
        for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)):
            neighbor = (point[0] + dx, point[1] + dy)
            if not clear(point, neighbor):
                continue
            alt = cost + 1
            if alt < costs.get(neighbor, 1_000_000):
                costs[neighbor] = alt
                parents[neighbor] = point
                heuristic = abs(neighbor[0]-goal[0]) + abs(neighbor[1]-goal[1])
                heappush(frontier, (alt + heuristic, alt, neighbor))
    return ()


class OracleAStarPolicy:
    """PRIVILEGED: given whole Scenario, not just policy observation."""
    privileged_map = True

    def __init__(self, scenario: Scenario):
        if not isinstance(scenario, Scenario):
            raise TypeError("oracle requires explicit full-map Scenario")
        self.scenario = scenario

    def choose_action(self, observation: AgentObservation) -> TrainingAction:
        x, y = observation.position_xy
        start = (round(x), round(y))
        if abs(x - start[0]) > 1e-6 or abs(y - start[1]) > 1e-6:
            return TrainingAction("NOOP")
        path = _grid_path(self.scenario, start)
        if len(path) < 2:
            return TrainingAction("NOOP")
        return _move(path[1][0] - start[0], path[1][1] - start[1])


@dataclass(frozen=True, slots=True)
class EpisodeResult:
    seed: int
    success: bool
    steps: int
    blocked_actions: int
    invalid_actions: int
    cumulative_reward: float
    path_length_m: float
    grid_reference_steps: int
    grid_reference_efficiency: float
    privileged_map: bool


@dataclass(frozen=True, slots=True)
class BaselineReport:
    policy: str
    episodes: int
    success_rate: float
    mean_steps: float
    mean_blocked_actions: float
    mean_invalid_actions: float
    mean_reward: float
    success_weighted_grid_efficiency: float
    privileged_map: bool


def run_episode(episode: NavigationEpisode, policy: Policy) -> EpisodeResult:
    if not isinstance(episode, NavigationEpisode):
        raise TypeError("episode must be NavigationEpisode")
    before = episode.observe()
    if before.remaining_steps != episode.max_steps:
        raise ValueError("run_episode requires a fresh episode")
    oracle = isinstance(policy, OracleAStarPolicy)
    if oracle and policy.scenario != episode.scenario:
        raise ValueError("oracle scenario must match episode")
    path = _grid_path(episode.scenario, tuple(map(round, episode.scenario.start)))
    if not path:
        raise ValueError("reference grid has no traversable path")
    blocked = invalid = steps = 0
    reward = distance = 0.0
    success = False
    while True:
        obs = episode.observe()
        action = policy.choose_action(obs)
        if not isinstance(action, TrainingAction):
            invalid += 1
            action = TrainingAction("NOOP")
        feedback = episode.step(action)
        steps += 1
        reward += feedback.reward
        blocked += int(not feedback.accepted)
        dx = feedback.observation.position_xy[0] - obs.position_xy[0]
        dy = feedback.observation.position_xy[1] - obs.position_xy[1]
        distance += hypot(dx, dy)
        if feedback.terminated or feedback.truncated:
            success = feedback.terminated
            break
    reference_length = len(path) - 1
    efficiency = (min(1.0, reference_length / max(distance, reference_length))
                  if success else 0.0)
    return EpisodeResult(
        episode.scenario.seed, success, steps, blocked, invalid,
        reward, distance, reference_length, efficiency, oracle,
    )


def evaluate_baselines(
    *, seeds: Sequence[int] = HOLDOUT_SEEDS,
    policies: Sequence[str] = ("random", "greedy", "oracle"),
    family: str = "barrier", max_steps: int = 40,
    sensor_range_m: float = 2.0,
) -> tuple[BaselineReport, ...]:
    if family not in ("barrier", "zigzag"):
        raise ValueError("unknown scenario family")
    if type(max_steps) is not int or not 1 <= max_steps <= 10000:
        raise ValueError("max_steps must be in [1,10000]")
    if (type(sensor_range_m) not in (int, float) or
            not isfinite(sensor_range_m) or sensor_range_m <= 0):
        raise ValueError("sensor_range_m must be positive and finite")
    seeds = tuple(seeds)
    policies = tuple(policies)
    if not seeds or len(seeds) > 10000 or len(set(seeds)) != len(seeds):
        raise ValueError("require 1..10000 unique seeds")
    for seed in seeds:
        _integer(seed, "seed")
    if not policies or len(set(policies)) != len(policies) or any(
        p not in ("random", "greedy", "memory", "oracle") for p in policies
    ):
        raise ValueError("unknown or duplicate baseline policy")
    reports: list[BaselineReport] = []
    for name in policies:
        results: list[EpisodeResult] = []
        for seed in seeds:
            ep = NavigationEpisode(seed, max_steps=max_steps, family=family,
                                   sensor_range_m=sensor_range_m)
            if name == "random":
                policy: Policy = RandomPolicy((seed + 12345) % 2**32)
            elif name == "greedy":
                policy = GreedyPolicy()
            elif name == "memory":
                from .mapping_policy import MemoryMapPolicy
                policy = MemoryMapPolicy()
            else:
                policy = OracleAStarPolicy(ep.scenario)
            results.append(run_episode(ep, policy))
        n = len(results)
        reports.append(BaselineReport(
            name, n, sum(r.success for r in results)/n,
            sum(r.steps for r in results)/n,
            sum(r.blocked_actions for r in results)/n,
            sum(r.invalid_actions for r in results)/n,
            sum(r.cumulative_reward for r in results)/n,
            sum(r.grid_reference_efficiency for r in results)/n,
            name == "oracle",
        ))
    return tuple(reports)


def make_zigzag_scenario(seed: int) -> Scenario:
    """Two staggered obstacles force navigation through opposing gaps.

    Pure synthetic geometry. Unlike the single-barrier family, the
    shortest cardinal reference path may require large non-monotonic
    detours both north and south before reaching the goal.
    """
    _integer(seed, "seed")
    rng = Random(seed)
    x1 = rng.choice((3.1, 3.4, 3.7))
    x2 = rng.choice((6.0, 6.3, 6.6))
    lower_top = rng.choice((6.8, 7.4, 8.1))
    upper_bottom = rng.choice((1.8, 2.4, 3.1))
    boxes = (
        Obstacle2("lower_barrier", x1, 0.0, x1 + .8, lower_top),
        Obstacle2("upper_barrier", x2, upper_bottom, x2 + .8, 10.0),
    )
    return Scenario(seed=seed, obstacles=boxes)

