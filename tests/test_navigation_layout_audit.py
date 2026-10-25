"""Seed-disjoint navigation holdouts can reuse identical obstacle layouts."""

import pytest

from vera_habitat.navigation import (
    HOLDOUT_SEEDS,
    TRAIN_SEEDS,
    make_scenario,
    make_zigzag_scenario,
)
from vera_habitat.navigation_eval import build_evaluation_report


@pytest.mark.parametrize(
    ("family", "factory", "known_train_overlap"),
    [
        ("barrier", make_scenario, 6),
        ("zigzag", make_zigzag_scenario, 3),
    ],
)
def test_report_discloses_geometric_reuse_between_seed_splits(
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

    report = build_evaluation_report(
        split="holdout", family=family, episodes=len(HOLDOUT_SEEDS),
        max_steps=40, sensor_range_m=2., policies=("greedy",),
    )
    assert report["layout_audit"] == {
        "signature": "obstacle_bounds_v1",
        "evaluated_unique_layouts": len(set(held_shapes)),
        "train_unique_layouts": len(train_shapes),
        "episodes_reusing_train_layout": overlaps,
        "unique_layouts_reused_from_train": len(set(held_shapes) & train_shapes),
    }
    assert "holdout_seeds_may_reuse_training_layouts" in report["limitations"]


def test_training_report_has_consistent_layout_audit():
    report = build_evaluation_report(
        split="train", family="barrier", episodes=2,
        max_steps=40, sensor_range_m=2., policies=("greedy",),
    )
    assert report["layout_audit"]["evaluated_unique_layouts"] == 2
    assert report["layout_audit"]["episodes_reusing_train_layout"] == 2
