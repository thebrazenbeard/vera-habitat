"""Restricted-observation navigation policy regression tests."""
from vera_habitat.navigation import (
    NavigationEpisode, AgentObservation, HOLDOUT_SEEDS,
    GreedyPolicy, evaluate_baselines, run_episode,
)
from vera_habitat.mapping_policy import MemoryMapPolicy
from vera_habitat.training_ground import TrainingAction


def test_memory_policy_uses_only_observations_and_replans_after_rejection():
    episode = NavigationEpisode(1000)
    policy = MemoryMapPolicy()
    before = episode.observe()
    action = policy.choose_action(before)
    assert isinstance(action, TrainingAction) and action.dry_run
    assert not hasattr(policy, "scenario") and not hasattr(policy, "_world")
    seen = policy.observed_obstacle_fragments
    assert seen >= 0
    feedback = episode.step(action)
    assert isinstance(feedback.observation, AgentObservation)
    next_action = policy.choose_action(feedback.observation)
    assert isinstance(next_action, TrainingAction)
    assert policy.observed_obstacle_fragments >= seen


def test_memory_policy_beats_greedy_on_heldout_barriers():
    results = evaluate_baselines(
        seeds=HOLDOUT_SEEDS, policies=("greedy", "memory")
    )
    assert results[1].success_rate > results[0].success_rate
    assert results[1].success_rate >= 0.5
    assert results[1].privileged_map is False
    assert results[1].mean_invalid_actions == 0


def test_memory_policy_reproducible_and_resettable():
    env = NavigationEpisode(1002)
    a, b = MemoryMapPolicy(), MemoryMapPolicy()
    for _ in range(15):
        observation = env.observe()
        ax = a.choose_action(observation)
        bx = b.choose_action(observation)
        assert ax == bx
        feedback = env.step(ax)
        if feedback.terminated or feedback.truncated:
            break
    assert a.observed_obstacle_fragments == b.observed_obstacle_fragments
    a.reset()
    assert a.observed_obstacle_fragments == 0
    assert a.blocked_edge_count == 0


def test_memory_baseline_is_explicit_cli_option(capsys):
    import json
    from vera_habitat.navigation_eval import main
    assert main(["--split", "holdout", "--episodes", "4",
                 "--policies", "memory"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["baselines"]) == 1
    assert data["baselines"][0]["policy"] == "memory"
    assert not data["baselines"][0]["privileged_map"]
