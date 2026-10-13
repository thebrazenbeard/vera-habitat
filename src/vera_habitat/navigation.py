"""Seeded neutral Habitat navigation evaluation (simulation only)."""
from dataclasses import dataclass
from typing import Protocol

TRAIN_SEEDS = tuple(range(20))
HOLDOUT_SEEDS = tuple(range(1000, 1020))

@dataclass(frozen=True)
class VisibleObstacle:
    bounds_relative: tuple[float, float, float, float]

@dataclass(frozen=True)
class AgentObservation:
    position_xy: tuple[float, float]
    goal_offset_xy: tuple[float, float]
    visible_obstacles: tuple[VisibleObstacle, ...]
    remaining_steps: int
    last_disposition: str

@dataclass(frozen=True)
class StepFeedback:
    observation: AgentObservation
    accepted: bool
    disposition: str
    reward: float
    terminated: bool
    truncated: bool

def make_scenario(seed: int):
    raise NotImplementedError("seeded scenario generation missing")

class NavigationEpisode:
    def __init__(self, seed: int, *, sensor_range_m: float = 2.0, max_steps: int = 40):
        raise NotImplementedError("episode observation boundary missing")

class GreedyPolicy:
    def choose_action(self, observation: AgentObservation):
        raise NotImplementedError("greedy baseline missing")

class RandomPolicy:
    def __init__(self, seed: int): self.seed = seed
    def choose_action(self, observation: AgentObservation):
        raise NotImplementedError("random baseline missing")

class OracleAStarPolicy:
    def __init__(self, scenario): self.scenario = scenario
    def choose_action(self, observation: AgentObservation):
        raise NotImplementedError("full-map A* reference missing")

def run_episode(episode, policy):
    raise NotImplementedError("episode evaluation missing")

def evaluate_baselines(*, seeds=HOLDOUT_SEEDS, policies=("random", "greedy", "oracle")):
    raise NotImplementedError("evaluation missing")
