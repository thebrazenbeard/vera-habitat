"""Restricted-observation memory navigation baseline (implementation pending)."""
from __future__ import annotations

from .training_ground import TrainingAction


class MemoryMapPolicy:
    privileged_map = False

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.observed_obstacle_fragments = 0
        self.blocked_edge_count = 0

    def choose_action(self, observation) -> TrainingAction:
        raise NotImplementedError("observation-only memory planning not implemented")
