"""Observation-limited persistent obstacle-map baseline for neutral Habitat.

No full Scenario, world snapshot, or simulator runtime is passed to this policy.
Geometry knowledge is built only from clipped local obstacle observations plus
rejected action dispositions. This is deterministic planning, not learning.
"""
from __future__ import annotations

from heapq import heappop, heappush
from math import isfinite
from typing import TypeAlias

from .navigation import AgentObservation
from .training_ground import TrainingAction

Point: TypeAlias = tuple[int, int]
Edge: TypeAlias = tuple[Point, Point]
Bounds: TypeAlias = tuple[float, float, float, float]


def _edge(a: Point, b: Point) -> Edge:
    return (a, b) if a <= b else (b, a)


def _segment_hits_bounds(a: Point, b: Point, rect: Bounds, radius: float) -> bool:
    """Conservative segment against measured, locally clipped rectangle."""
    enter, exit = 0.0, 1.0
    for i, low, high in ((0, rect[0] - radius, rect[2] + radius),
                         (1, rect[1] - radius, rect[3] + radius)):
        velocity = b[i] - a[i]
        if not velocity:
            if not low <= a[i] <= high:
                return False
            continue
        t0, t1 = (low - a[i])/velocity, (high - a[i])/velocity
        enter = max(enter, min(t0, t1))
        exit = min(exit, max(t0, t1))
        if enter > exit:
            return False
    return True


class MemoryMapPolicy:
    """Grid planner that remembers visible obstacle fragments between steps.

    Envelope 10x10, integer waypoints 1..9, and radius 0.2 are documented
    *task rules*, not extracted from the hidden map. Assumes exact synthetic
    pose/goal observations; this is not camera-based localization.
    """

    privileged_map = False

    def __init__(self, *, extent: int = 10, radius: float = 0.2) -> None:
        if type(extent) is not int or not 3 <= extent <= 100:
            raise ValueError("extent must be an integer in [3,100]")
        if type(radius) not in (int, float) or not isfinite(radius) or not 0 < radius < 0.5:
            raise ValueError("radius must be positive and under half a cell")
        self.extent = extent
        self.radius = float(radius)
        self.reset()

    def reset(self) -> None:
        self._blocked: set[Edge] = set()
        self._fragments: set[Bounds] = set()
        self._previous_edge: Edge | None = None
        self._previous_steps: int | None = None

    @property
    def blocked_edge_count(self) -> int:
        return len(self._blocked)

    @property
    def observed_obstacle_fragments(self) -> int:
        return len(self._fragments)

    def _neighbors(self, point: Point):
        x, y = point
        for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)):
            nxt = (x + dx, y + dy)
            if (1 <= nxt[0] <= self.extent - 1 and
                    1 <= nxt[1] <= self.extent - 1 and
                    _edge(point, nxt) not in self._blocked):
                yield nxt

    def _integrate_sensor(self, observation: AgentObservation) -> None:
        x, y = observation.position_xy
        for seen in observation.visible_obstacles:
            left, bottom, right, top = seen.bounds_relative
            box = (x + left, y + bottom, x + right, y + top)
            # Round reconstructed floating coordinates for stable identities.
            key = tuple(round(v, 8) for v in box)
            if key in self._fragments:
                continue
            self._fragments.add(key)
            for px in range(1, self.extent):
                for py in range(1, self.extent):
                    a = (px, py)
                    for nx, ny in ((px + 1, py), (px, py + 1)):
                        b = (nx, ny)
                        if nx >= self.extent or ny >= self.extent:
                            continue
                        if _segment_hits_bounds(a, b, box, self.radius):
                            self._blocked.add(_edge(a, b))

    def _plan(self, start: Point, goal: Point) -> tuple[Point, ...]:
        frontier: list[tuple[int, int, Point]] = []
        heuristic = lambda p: abs(p[0] - goal[0]) + abs(p[1] - goal[1])
        heappush(frontier, (heuristic(start), 0, start))
        dist = {start: 0}
        parents: dict[Point, Point] = {}
        while frontier:
            _, g, current = heappop(frontier)
            if g != dist.get(current):
                continue
            if current == goal:
                nodes = [current]
                while nodes[-1] != start:
                    nodes.append(parents[nodes[-1]])
                return tuple(reversed(nodes))
            for nxt in self._neighbors(current):
                alternative = g + 1
                if alternative < dist.get(nxt, 10**9):
                    dist[nxt] = alternative
                    parents[nxt] = current
                    heappush(frontier, (alternative + heuristic(nxt), alternative, nxt))
        return ()

    def choose_action(self, observation: AgentObservation) -> TrainingAction:
        if type(observation) is not AgentObservation:
            raise TypeError("only AgentObservation is allowed")
        steps = observation.remaining_steps
        if (self._previous_steps is not None and steps > self._previous_steps
                or observation.last_disposition == "RESET"):
            self.reset()
        self._previous_steps = steps
        if (observation.last_disposition.endswith("_REJECTED")
                and self._previous_edge is not None):
            self._blocked.add(self._previous_edge)
        self._integrate_sensor(observation)
        x, y = observation.position_xy
        gx = x + observation.goal_offset_xy[0]
        gy = y + observation.goal_offset_xy[1]
        start = (round(x), round(y))
        goal = (round(gx), round(gy))
        if (abs(x - start[0]) > 1e-6 or abs(y - start[1]) > 1e-6
                or not 1 <= goal[0] < self.extent or not 1 <= goal[1] < self.extent):
            return TrainingAction("NOOP")
        if start == goal:
            return TrainingAction("NOOP")
        path = self._plan(start, goal)
        if len(path) < 2:
            return TrainingAction("NOOP")
        nxt = path[1]
        self._previous_edge = _edge(start, nxt)
        return TrainingAction("MOVE", float(nxt[0] - start[0]),
                              float(nxt[1] - start[1]), duration_ms=1000)
