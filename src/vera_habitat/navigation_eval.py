"""CLI comparison of restricted baselines against a privileged grid oracle.

Reports reproducible synthetic evaluation only. No learning or device calls.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from typing import Sequence

from .navigation import TRAIN_SEEDS, HOLDOUT_SEEDS, evaluate_baselines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate synthetic Vera Habitat navigation baselines"
    )
    parser.add_argument("--split", choices=("train", "holdout"),
                        default="holdout")
    parser.add_argument("--episodes", type=int, default=20,
                        help="Number of deterministic seed layouts (1..20)")
    parser.add_argument("--policies", nargs="+",
                        choices=("random", "greedy", "oracle"),
                        default=["random", "greedy", "oracle"])
    args = parser.parse_args(argv)
    pool = TRAIN_SEEDS if args.split == "train" else HOLDOUT_SEEDS
    if not 1 <= args.episodes <= len(pool):
        parser.error(f"--episodes must be between 1 and {len(pool)}")
    seeds = pool[:args.episodes]
    results = evaluate_baselines(seeds=seeds, policies=args.policies)
    print(json.dumps({
        "schema_version": "VERA_HABITAT_NAV_EVALUATION_V1",
        "split": args.split,
        "seeds": list(seeds),
        "baselines": [asdict(result) for result in results],
        "limitations": [
            "simulated_world_not_ARK",
            "goal_offset_and_avatar_pose_are_synthetic_observations",
            "oracle_has_privileged_full_map",
            "grid_reference_efficiency_is_not_Habitat_SPL",
            "reward_is_not_learning_proof",
            "seeded_procedural_layouts_share_one_barrier_family",
            "no_native_Vera_runtime_or_hardware_actuation",
        ],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
