"""A seed split is not necessarily an obstacle-geometry split."""

from __future__ import annotations

import json

import pytest

from vera_habitat.navigation import (
    TRAIN_SEEDS,
    make_scenario,
    make_zigzag_scenario,
)
from vera_habitat.navigation_eval import (
    build_evaluation_report,
    build_geometry_disjoint_evaluation_report,
    geometry_disjoint_holdout_seeds,
    _translation_normalized_signature,
    main,
)


def _signature(scenario) -> tuple:
    return tuple((box.left, box.bottom, box.right, box.top)
                 for box in scenario.obstacles)


@pytest.mark.parametrize("family,generator,expected", [
    ("barrier", make_scenario, ()),
    ("zigzag", make_zigzag_scenario,
     (1000, 1001, 1002, 1004, 1006, 1008, 1014, 1015, 1019)),
])
def test_selects_only_unique_unseen_obstacle_layouts(family, generator, expected):
    selected = geometry_disjoint_holdout_seeds(family)
    assert selected == expected
    training = {_translation_normalized_signature(generator(seed).obstacles)
                for seed in TRAIN_SEEDS}
    holdout = [_translation_normalized_signature(generator(seed).obstacles)
               for seed in selected]
    assert set(holdout).isdisjoint(training)
    assert len(holdout) == len(set(holdout))


def test_translation_normalization_eliminates_position_only_novelty():
    assert _translation_normalized_signature(make_scenario(1000).obstacles) in {
        _translation_normalized_signature(make_scenario(s).obstacles)
        for s in TRAIN_SEEDS
    }
    # The raw bounds can appear different even when shape is just shifted.
    assert _signature(make_scenario(1000)) not in {
        _signature(make_scenario(s)) for s in TRAIN_SEEDS
    }


def test_new_report_is_separate_reproducible_and_old_v1_is_unchanged():
    kwargs = dict(family="zigzag", episodes=2, max_steps=8,
                  sensor_range_m=2.0, policies=("greedy", "oracle"))
    before = build_evaluation_report(split="holdout", **kwargs)
    first = build_geometry_disjoint_evaluation_report(**kwargs)
    second = build_geometry_disjoint_evaluation_report(**kwargs)
    after = build_evaluation_report(split="holdout", **kwargs)

    assert before == after
    assert before["schema_version"] == "VERA_HABITAT_NAV_EVALUATION_V1"
    assert first == second
    assert first["schema_version"] == "VERA_HABITAT_NAV_GEOMETRY_DISJOINT_EVAL_V1"
    assert first["split"] == "holdout_geometry_disjoint"
    assert first["seeds"] == [1000, 1001]
    assert len(first["baselines"]) == 2
    assert first["train_layout_reuse_count"] == 0
    assert "not_a_generalization_claim" in first["limitations"]


@pytest.mark.parametrize("episodes", [False, 0, -1, 10, 1.5, "2"])
def test_capacity_and_type_fail_closed(episodes):
    with pytest.raises(ValueError):
        build_geometry_disjoint_evaluation_report(
            family="zigzag", episodes=episodes, max_steps=8,
            sensor_range_m=2.0, policies=("greedy",),
        )


def test_exhausted_barrier_family_fails_closed_not_hallucinated_novelty():
    assert geometry_disjoint_holdout_seeds("barrier") == ()
    with pytest.raises(ValueError, match="no translation-disjoint layouts"):
        build_geometry_disjoint_evaluation_report(
            family="barrier", episodes=1, max_steps=8,
            sensor_range_m=2.0, policies=("greedy",),
        )


def test_cli_requires_holdout_and_cannot_reuse_v1_bundle(capsys):
    assert main(["--geometry-disjoint", "--family", "zigzag",
                 "--max-steps", "6", "--policies", "greedy"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["schema_version"] == "VERA_HABITAT_NAV_GEOMETRY_DISJOINT_EVAL_V1"
    assert len(report["seeds"]) == 9  # default is all structurally unseen candidates

    for args in (
        ["--split", "train"],
        ["--bundle"],
        ["--layout-audit-only"],
        ["--episodes", "10"],
        ["--family", "barrier"],
    ):
        with pytest.raises(SystemExit) as failure:
            main(["--geometry-disjoint", *args])
        assert failure.value.code == 2


def test_cli_explicit_capacity_zigzag(capsys):
    assert main(["--geometry-disjoint", "--family", "zigzag",
                 "--episodes", "9", "--max-steps", "6",
                 "--policies", "greedy"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert len(report["seeds"]) == 9
    assert len(set(report["seeds"])) == 9
