"""Behavior-level tests for seeded navigation and honest evaluation."""
from dataclasses import fields
import math

import pytest

from vera_habitat.navigation import (
    AgentObservation, NavigationEpisode, GreedyPolicy, RandomPolicy,
    OracleAStarPolicy, make_scenario, run_episode, evaluate_baselines,
    TRAIN_SEEDS, HOLDOUT_SEEDS,
)
from vera_habitat.training_ground import TrainingAction


def test_seeded_reproducible_world_and_independent_reset():
    assert set(TRAIN_SEEDS).isdisjoint(HOLDOUT_SEEDS)
    a, b = make_scenario(1017), make_scenario(1017)
    assert a == b
    assert len({make_scenario(s).obstacles for s in HOLDOUT_SEEDS}) >= 4
    env = NavigationEpisode(1017)
    initial = env.observe()
    env.step(TrainingAction("MOVE", x=0, y=1, duration_ms=1000))
    assert env.reset(1017) == initial
    assert env.observe() == initial


def test_policy_observation_is_restricted_and_sensor_clipped():
    env = NavigationEpisode(1005, sensor_range_m=1.2)
    obs = env.observe()
    assert isinstance(obs, AgentObservation)
    assert "scene" not in {f.name for f in fields(obs)}
    assert "goal" not in {f.name for f in fields(obs)}
    assert "obstacles" not in {f.name for f in fields(obs)}
    assert not hasattr(obs, "revision")
    assert not hasattr(obs, "distance_to_goal_m")
    for obstacle in obs.visible_obstacles:
        assert all(abs(v) <= 1.2 + 1e-9 for v in obstacle.bounds_relative)
    assert obs.remaining_steps == 40


def test_episode_boundary_preserves_feedback_and_truncation():
    env = NavigationEpisode(1010, max_steps=2)
    initial = env.observe()
    result = env.step(TrainingAction("NOOP"))
    assert result.accepted and not result.terminated and not result.truncated
    assert result.observation.remaining_steps == 1
    assert result.observation.last_disposition == "SIMULATION_NOOP"
    result = env.step(TrainingAction("NOOP"))
    assert result.truncated and not result.terminated
    with pytest.raises(RuntimeError, match="complete"):
        env.step(TrainingAction("NOOP"))
    assert initial.remaining_steps == 2


def test_oracle_full_map_reference_succeeds_on_unseen_maps():
    for seed in HOLDOUT_SEEDS:
        episode = NavigationEpisode(seed, max_steps=50)
        result = run_episode(episode, OracleAStarPolicy(episode.scenario))
        assert result.success, (seed, result)
        assert result.blocked_actions == 0
        assert result.steps <= 50
        assert result.privileged_map


def test_baselines_are_reproducible_and_distinguish_privilege():
    a = evaluate_baselines(seeds=HOLDOUT_SEEDS[:8])
    b = evaluate_baselines(seeds=HOLDOUT_SEEDS[:8])
    assert a == b
    assert [r.policy for r in a] == ["random", "greedy", "oracle"]
    assert all(r.episodes == 8 for r in a)
    assert all(0 <= r.success_rate <= 1 for r in a)
    assert a[-1].success_rate == 1
    assert a[-1].privileged_map and not a[0].privileged_map
    assert a[-1].success_rate >= a[1].success_rate


def test_unknown_policy_and_duplicate_seeds_fail_closed():
    with pytest.raises(ValueError):
        evaluate_baselines(seeds=(1, 1))
    with pytest.raises(ValueError):
        evaluate_baselines(seeds=(1,), policies=("unknown",))
    with pytest.raises(ValueError):
        make_scenario(True)
    with pytest.raises(ValueError):
        NavigationEpisode(1, sensor_range_m=0)


def test_policy_receives_only_observation_and_invalid_action_is_counted():
    class InvalidPolicy:
        def choose_action(self, observation):
            assert type(observation) is AgentObservation
            return {"move": "unsafe"}
    result = run_episode(NavigationEpisode(3, max_steps=3), InvalidPolicy())
    assert result.invalid_actions == 3
    assert not result.success
    assert result.steps == 3
    assert not result.privileged_map


def test_greedy_policy_direction_follows_goal_not_privileged_map():
    env = NavigationEpisode(3)
    observation = env.observe()
    action = GreedyPolicy().choose_action(observation)
    assert action.kind == "MOVE"
    assert action.dry_run
    assert action.duration_ms <= 1000
    assert action.x >= 0 and action.y >= 0


def test_random_policy_is_seeded():
    env = NavigationEpisode(3)
    a, b = RandomPolicy(11), RandomPolicy(11)
    for _ in range(30):
        assert a.choose_action(env.observe()) == b.choose_action(env.observe())
