"""Out-of-family, non-monotonic geometry stress tests.

A different held-out geometry family is a stronger challenge than merely
changing seeds inside the original single-barrier generator.
"""
import json

from vera_habitat.navigation import (
    HOLDOUT_SEEDS, NavigationEpisode, OracleAStarPolicy,
    evaluate_baselines, make_zigzag_scenario, run_episode,
)
from vera_habitat.navigation_eval import main


def test_zigzag_seeded_two_barriers_differ_from_original_family():
    a, b = make_zigzag_scenario(1003), make_zigzag_scenario(1003)
    assert a == b
    assert len(a.obstacles) == 2
    assert len({make_zigzag_scenario(s).obstacles for s in HOLDOUT_SEEDS}) >= 4
    assert {box.entity_id for box in a.obstacles} == {"lower_barrier", "upper_barrier"}


def test_zigzag_has_reference_routes_and_measures_memory_without_map_privilege():
    seeds = HOLDOUT_SEEDS[:10]
    reports = evaluate_baselines(
        seeds=seeds, policies=("greedy", "memory", "oracle"),
        family="zigzag", max_steps=60,
    )
    assert reports[-1].success_rate == 1.0
    assert reports[1].success_rate > reports[0].success_rate
    assert reports[1].privileged_map is False
    assert reports[-1].privileged_map is True


def test_zigzag_cli_reports_family_budget_and_is_reproducible(capsys):
    args = ["--family", "zigzag", "--max-steps", "60",
            "--split", "holdout", "--episodes", "4",
            "--policies", "greedy", "memory", "oracle"]
    assert main(args) == 0
    a = json.loads(capsys.readouterr().out)
    assert a["family"] == "zigzag"
    assert a["max_steps"] == 60
    assert a["baselines"][-1]["success_rate"] == 1.0
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out) == a
