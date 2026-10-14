"""CLI comparison of restricted baselines against a privileged grid oracle.

Reports reproducible synthetic evaluation only. No learning or device calls.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from typing import Sequence

from .navigation import TRAIN_SEEDS, HOLDOUT_SEEDS, evaluate_baselines


def build_evaluation_report(*, split: str, family: str, episodes: int,
                            max_steps: int, sensor_range_m: float,
                            policies: Sequence[str]) -> dict:
    """Recompute one bounded report without I/O or external authority."""
    from math import isfinite

    if split not in ("train", "holdout") or family not in ("barrier", "zigzag"):
        raise ValueError("unsupported evaluation family or split")
    pool = TRAIN_SEEDS if split == "train" else HOLDOUT_SEEDS
    if type(episodes) is not int or not 1 <= episodes <= len(pool):
        raise ValueError("invalid evaluation episode count")
    if type(max_steps) is not int or not 1 <= max_steps <= 10000:
        raise ValueError("invalid evaluation step budget")
    if (type(sensor_range_m) not in (int, float)
            or not isfinite(sensor_range_m) or sensor_range_m <= 0):
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
    parser.add_argument("--episodes", type=int, default=20,
                        help="Number of deterministic seed layouts (1..20)")
    parser.add_argument("--policies", nargs="+",
                        choices=("random", "greedy", "memory", "oracle"),
                        default=["random", "greedy", "oracle"])
    parser.add_argument("--bundle", action="store_true",
                        help="Include a public digest and replay-verifiable payload")
    args = parser.parse_args(argv)
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
