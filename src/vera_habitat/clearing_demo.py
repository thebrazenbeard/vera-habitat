"""Print one deterministic simulation-only Clearing trial as JSON.

Usage: python -m vera_habitat.clearing_demo
No display, network, credentials, filesystem writes, or agent required.
"""
from __future__ import annotations

from hashlib import sha256
import json

from .clearing import make_clearing, run_prediction_trial
from .model import Position3
from .rendering import render_scene_json


def main() -> None:
    world = make_clearing()
    initial_projection = render_scene_json(world.snapshot())
    target = Position3(3.0, 2.0, 0.0)
    result = run_prediction_trial(
        world, action_id="clearing-first-step", entity_id="avatar",
        target=target, predicted=target,
    )
    receipt = {
        "schema": "VERA_CLEARING_HEADLESS_TRIAL_V0",
        "authority": "SIMULATION_ONLY",
        "physics_qualified": False,
        "initial_projection_sha256": sha256(
            initial_projection.encode("utf-8")
        ).hexdigest(),
        "trial": {
            "action_id": result.action_id,
            "entity_id": result.entity_id,
            "accepted": result.accepted,
            "disposition": result.disposition,
            "revision_before": result.revision_before,
            "revision_after": result.revision_after,
            "predicted": [result.predicted.x, result.predicted.y, result.predicted.z],
            "observed": [result.observed.x, result.observed.y, result.observed.z],
            "error_m": result.error_m,
            "final_projection_sha256": result.snapshot_sha256,
        },
        "scene": json.loads(render_scene_json(world.snapshot())),
    }
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
