"""Seed-disjoint navigation holdouts can reuse identical obstacle layouts."""

import pytest

from vera_habitat.navigation import (
    HOLDOUT_SEEDS,
    TRAIN_SEEDS,
    make_scenario,
    make_zigzag_scenario,
)
from vera_habitat.navigation_eval import build_evaluation_report, build_layout_audit


@pytest.mark.parametrize(
    ("family", "factory", "known_train_overlap"),
    [
        ("barrier", make_scenario, 6),
        ("zigzag", make_zigzag_scenario, 3),
    ],
)
def test_separate_audit_discloses_geometric_reuse_between_seed_splits(
    family, factory, known_train_overlap
):
    def shape(seed):
        return tuple(
            (obstacle.left, obstacle.bottom, obstacle.right, obstacle.top)
            for obstacle in factory(seed).obstacles
        )

    train_shapes = {shape(seed) for seed in TRAIN_SEEDS}
    held_shapes = [shape(seed) for seed in HOLDOUT_SEEDS]
    overlaps = sum(shape in train_shapes for shape in held_shapes)
    assert set(TRAIN_SEEDS).isdisjoint(HOLDOUT_SEEDS)
    assert overlaps == known_train_overlap  # pins current generator's limitation

    audit = build_layout_audit(
        split="holdout", family=family, episodes=len(HOLDOUT_SEEDS),
    )
    assert audit == {
        "schema_version": "VERA_HABITAT_NAV_LAYOUT_AUDIT_V1",
        "split": "holdout",
        "family": family,
        "seeds": list(HOLDOUT_SEEDS),
        "signature": "obstacle_bounds_v1",
        "evaluated_unique_layouts": len(set(held_shapes)),
        "train_unique_layouts": len(train_shapes),
        "episodes_reusing_train_layout": overlaps,
        "unique_layouts_reused_from_train": len(set(held_shapes) & train_shapes),
    }


def test_training_audit_has_consistent_layout_counts():
    audit = build_layout_audit(split="train", family="barrier", episodes=2)
    assert audit["evaluated_unique_layouts"] == 2
    assert audit["episodes_reusing_train_layout"] == 2


def test_default_v1_report_keeps_legacy_replay_payload():
    """A diagnostic must not rewrite previously sealed V1 report semantics."""
    from vera_habitat.eval_bundle import seal_evaluation_report, verify_evaluation_bundle
    import json

    report = build_evaluation_report(
        split="holdout", family="barrier", episodes=2,
        max_steps=40, sensor_range_m=2., policies=("greedy",),
    )
    assert "layout_audit" not in report
    assert "holdout_seeds_may_reuse_training_layouts" not in report["limitations"]
    bundle = seal_evaluation_report(report)
    assert verify_evaluation_bundle(json.dumps(bundle)) == report


def test_audit_cli_is_opt_in_and_distinct_from_a_sealed_report(capsys):
    import json
    from vera_habitat.navigation_eval import main

    assert main(["--split", "holdout", "--family", "barrier",
                 "--episodes", "20", "--layout-audit-only"]) == 0
    audit = json.loads(capsys.readouterr().out)
    assert audit["schema_version"] == "VERA_HABITAT_NAV_LAYOUT_AUDIT_V1"
    assert audit["episodes_reusing_train_layout"] == 6
    assert "baselines" not in audit


@pytest.mark.parametrize("invalid", [0, 21, True, 1.5])
def test_audit_rejects_invalid_episode_budget(invalid):
    with pytest.raises(ValueError, match="episode count"):
        build_layout_audit(split="holdout", family="barrier", episodes=invalid)
