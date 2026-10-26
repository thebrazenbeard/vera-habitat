"""CLI comparison of restricted baselines against a privileged grid oracle.

Reports reproducible synthetic evaluation only. No learning or device calls.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from typing import Sequence

from .model import _finite_real
from .navigation import (
    TRAIN_SEEDS,
    HOLDOUT_SEEDS,
    evaluate_baselines,
    make_scenario,
    make_zigzag_scenario,
)


def _layout_audit(*, family: str, seeds: Sequence[int]) -> dict:
    """Count exact synthetic obstacle-layout reuse, not model generalization.

    Training and holdout use distinct seed IDs but finite geometry choices.
    Compare obstacle bounds rather than seeds so identical worlds are visible.
    """
    generate = make_scenario if family == "barrier" else make_zigzag_scenario

    def signature(seed: int) -> tuple:
        return tuple(
            (box.left, box.bottom, box.right, box.top)
            for box in generate(seed).obstacles
        )

    training = {signature(seed) for seed in TRAIN_SEEDS}
    evaluated = [signature(seed) for seed in seeds]
    unique_evaluated = set(evaluated)
    return {
        "signature": "obstacle_bounds_v1",
        "evaluated_unique_layouts": len(unique_evaluated),
        "train_unique_layouts": len(training),
        "episodes_reusing_train_layout": sum(
            layout in training for layout in evaluated
        ),
        "unique_layouts_reused_from_train": len(unique_evaluated & training),
    }


def build_layout_audit(*, split: str, family: str, episodes: int) -> dict:
    """Opt-in geometry audit, separate from replay-stable V1 evaluations.

    Historical evaluation reports and sealed bundles must not silently gain
    fields under the same V1 schema identifier.
    """
    if split not in ("train", "holdout") or family not in ("barrier", "zigzag"):
        raise ValueError("unsupported audit family or split")
    pool = TRAIN_SEEDS if split == "train" else HOLDOUT_SEEDS
    if type(episodes) is not int or not 1 <= episodes <= len(pool):
        raise ValueError("invalid audit episode count")
    return {
        "schema_version": "VERA_HABITAT_NAV_LAYOUT_AUDIT_V1",
        "split": split,
        "family": family,
        "seeds": list(pool[:episodes]),
        **_layout_audit(family=family, seeds=pool[:episodes]),
    }


def _translation_normalized_signature(obstacles: Sequence) -> tuple:
    """Canonicalize shape under global horizontal translation, not rotation.

    The seeded generator's horizontal coordinates use decimal tenths; round
    translated float differences to nine places to avoid phantom novelty from
    binary representation artifacts. Vertical bounds and inter-box spacing
    stay significant. This does not normalize start/goal or dynamics.
    """
    if not obstacles:
        return ()
    origin_x = min(box.left for box in obstacles)
    return tuple(sorted(
        (round(box.left - origin_x, 9), box.bottom,
         round(box.right - origin_x, 9), box.top)
        for box in obstacles
    ))


def geometry_disjoint_holdout_seeds(family: str) -> tuple[int, ...]:
    """Select public holdout seeds with unseen translation-normalized shape.

    Fail closed when the generator provides no novel shape; this particularly
    matters for barrier, whose coordinate-distinct layouts are all global
    horizontal translations of training shapes. Not a secret test set.
    """
    if family not in ("barrier", "zigzag"):
        raise ValueError("unsupported evaluation family")
    generator = make_scenario if family == "barrier" else make_zigzag_scenario

    def signature(seed: int) -> tuple:
        return _translation_normalized_signature(generator(seed).obstacles)

    seen = {signature(seed) for seed in TRAIN_SEEDS}
    selected: list[int] = []
    for seed in HOLDOUT_SEEDS:
        layout = signature(seed)
        if layout not in seen:
            selected.append(seed)
            seen.add(layout)
    return tuple(selected)


def build_geometry_disjoint_evaluation_report(
    *, family: str, episodes: int, max_steps: int,
    sensor_range_m: float, policies: Sequence[str],
) -> dict:
    """Evaluate a public synthetic holdout with no translated-shape collisions.

    This opt-in report uses a separate schema: V1 reports and sealed replay
    bundle identities are deliberately untouched.
    """
    seeds = geometry_disjoint_holdout_seeds(family)
    if not seeds:
        raise ValueError(f"no translation-disjoint layouts available for {family}")
    if type(episodes) is not int or not 1 <= episodes <= len(seeds):
        raise ValueError("invalid geometry-disjoint episode count")
    if type(max_steps) is not int or not 1 <= max_steps <= 10000:
        raise ValueError("invalid evaluation step budget")
    if not _finite_real(sensor_range_m) or sensor_range_m <= 0:
        raise ValueError("invalid evaluation sensor range")
    selected = seeds[:episodes]
    results = evaluate_baselines(
        seeds=selected, policies=policies, family=family,
        max_steps=max_steps, sensor_range_m=sensor_range_m,
    )
    return {
        "schema_version": "VERA_HABITAT_NAV_GEOMETRY_DISJOINT_EVAL_V1",
        "split": "holdout_geometry_disjoint",
        "family": family,
        "max_steps": max_steps,
        "sensor_range_m": sensor_range_m,
        "seeds": list(selected),
        "train_layout_reuse_count": 0,
        "geometry_signature": "obstacle_bounds_translation_normalized_x_v1",
        "selection_rule": "first_public_holdout_shape_absent_from_train_v1_up_to_horizontal_translation",
        "baselines": [asdict(result) for result in results],
        "limitations": [
            "not_a_generalization_claim",
            "public_generator_and_seed_selection_can_be_gamed",
            "same_synthetic_scenario_families_as_training",
            "translation_normalized_horizontal_shape_not_semantic_or_dynamics_disjointness",
            "start_goal_relation_to_obstacles_is_not_normalized",
            "oracle_has_privileged_full_map",
            "no_live_Vera_runtime_or_hardware_actuation",
            "NO_AUTO_BIND",
        ],
    }


def build_evaluation_report(*, split: str, family: str, episodes: int,
                            max_steps: int, sensor_range_m: float,
                            policies: Sequence[str]) -> dict:
    """Recompute one bounded report without I/O or external authority."""
    if split not in ("train", "holdout") or family not in ("barrier", "zigzag"):
        raise ValueError("unsupported evaluation family or split")
    pool = TRAIN_SEEDS if split == "train" else HOLDOUT_SEEDS
    if type(episodes) is not int or not 1 <= episodes <= len(pool):
        raise ValueError("invalid evaluation episode count")
    if type(max_steps) is not int or not 1 <= max_steps <= 10000:
        raise ValueError("invalid evaluation step budget")
    if not _finite_real(sensor_range_m) or sensor_range_m <= 0:
        raise ValueError("invalid evaluation sensor range")
    results = evaluate_baselines(
        seeds=pool[:episodes], policies=policies,
        family=family, max_steps=max_steps,
        sensor_range_m=sensor_range_m,
    )
    return {
        "schema_version": "VERA_HABITAT_NAV_EVALUATION_V1",
        "split": split,
        "family": family,
        "max_steps": max_steps,
        "sensor_range_m": sensor_range_m,
        "seeds": list(pool[:episodes]),
        "baselines": [asdict(result) for result in results],
        "limitations": [
            "simulated_world_not_ARK",
            "goal_offset_and_avatar_pose_are_synthetic_observations",
            "oracle_has_privileged_full_map",
            "grid_reference_efficiency_is_not_Habitat_SPL",
            "reward_is_not_learning_proof",
            "holdout_seeds_share_generator_family_with_training",
            "sensor_range_is_local_square_visibility_not_occlusion",
            "no_native_Vera_runtime_or_hardware_actuation",
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate synthetic Vera Habitat navigation baselines"
    )
    parser.add_argument("--split", choices=("train", "holdout"),
                        default="holdout")
    parser.add_argument("--family", choices=("barrier", "zigzag"), default="barrier")
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument("--sensor-range", type=float, default=2.0)
    parser.add_argument("--episodes", type=int, default=None,
                        help="Number of deterministic seed layouts (default: 20 for V1, all unseen geometries for opt-in mode)")
    parser.add_argument("--policies", nargs="+",
                        choices=("random", "greedy", "memory", "oracle"),
                        default=["random", "greedy", "oracle"])
    parser.add_argument("--bundle", action="store_true",
                        help="Include a public digest and replay-verifiable payload")
    parser.add_argument("--layout-audit-only", action="store_true",
                        help="Print a separate geometry overlap audit without altering V1 reports")
    parser.add_argument("--geometry-disjoint", action="store_true",
                        help="Opt into a separate public unseen-geometry holdout; not a generalization claim")
    args = parser.parse_args(argv)
    if args.geometry_disjoint:
        if args.split != "holdout":
            parser.error("--geometry-disjoint is holdout-only")
        if args.bundle or args.layout_audit_only:
            parser.error("--geometry-disjoint cannot use V1 bundles or layout-audit-only")
        available = len(geometry_disjoint_holdout_seeds(args.family))
        if not available:
            parser.error(f"no translation-disjoint layouts available for {args.family}")
        count = available if args.episodes is None else args.episodes
        if not 1 <= count <= available:
            parser.error(f"--episodes must be between 1 and {available} in geometry-disjoint mode")
        if not 1 <= args.max_steps <= 10000:
            parser.error("--max-steps must be between 1 and 10000")
        from math import isfinite
        if not isfinite(args.sensor_range) or args.sensor_range <= 0:
            parser.error("--sensor-range must be finite and positive")
        report = build_geometry_disjoint_evaluation_report(
            family=args.family, episodes=count, max_steps=args.max_steps,
            sensor_range_m=args.sensor_range, policies=args.policies,
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    if args.episodes is None:
        args.episodes = 20
    pool = TRAIN_SEEDS if args.split == "train" else HOLDOUT_SEEDS
    if not 1 <= args.episodes <= len(pool):
        parser.error(f"--episodes must be between 1 and {len(pool)}")
    if not 1 <= args.max_steps <= 10000:
        parser.error("--max-steps must be between 1 and 10000")
    from math import isfinite
    if not isfinite(args.sensor_range) or args.sensor_range <= 0:
        parser.error("--sensor-range must be finite and positive")
    if args.bundle:
        from .eval_bundle import MAX_REPLAY_STEPS
        if args.episodes * args.max_steps * len(args.policies) > MAX_REPLAY_STEPS:
            parser.error("--bundle replay work budget exceeded")
    if args.layout_audit_only:
        if args.bundle:
            parser.error("--layout-audit-only cannot be combined with --bundle")
        audit = build_layout_audit(
            split=args.split, family=args.family, episodes=args.episodes,
        )
        print(json.dumps(audit, indent=2, sort_keys=True))
        return 0
    report = build_evaluation_report(
        split=args.split, family=args.family, episodes=args.episodes,
        max_steps=args.max_steps, sensor_range_m=args.sensor_range,
        policies=args.policies,
    )
    if args.bundle:
        from .eval_bundle import seal_evaluation_report
        report = seal_evaluation_report(report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
