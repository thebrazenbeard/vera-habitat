# Neutral navigation evaluation V1

**Status:** experimental, deterministic, simulation-only. No ARK gameplay,
no trained Vera policy, no native Vera runtime binding, no external effects.
This contribution is stacked on `feat/neutral-training-ground` (Draft PR #7),
not merged into Habitat `main`.

## Run

Python 3.11+ with pytest for development:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m vera_habitat.navigation_eval --split train --episodes 20
python -m vera_habitat.navigation_eval --split holdout --episodes 20
python -m vera_habitat.navigation_eval --split holdout --episodes 4 --policies greedy oracle
```

The CLI emits deterministic JSON under
`VERA_HABITAT_NAV_EVALUATION_V1`. Random-policy choices are seeded.
The same code and seed sequence return the same data. The numeric baseline
outcomes are diagnostic of these scenarios only.

## Research-aligned interfaces

`NavigationEpisode(seed, sensor_range_m=2.0, max_steps=40)` creates an
independent Habitat ground. `reset(seed)` replaces its world and history.
`step(TrainingAction)` returns a `StepFeedback` with next observation,
acceptance, reward, and mutually exclusive `terminated` and `truncated`
statuses. `terminated` means the goal was reached; `truncated` means the
finite step budget was exhausted.

`Policy.choose_action(AgentObservation)` is an independently supplied
protocol. `AgentObservation` includes only current synthetic avatar position,
a supplied target offset, obstacle rectangles clipped to a local square
sensor window, remaining steps and last action disposition. It does **not**
include Habitat `SceneSnapshot`, entire obstacle layout, world revision,
the internal reward, or exact goal-distance field.

This is an information API, *not a sandbox*: external Python code in the same
process can still access other objects if given a reference to them. Pose and
target offset are exact synthetic measurements, **not visually inferred**
from ARK frames. No blind navigation or perception generalization is proven.

## Seeded map family and privileges

`make_scenario(seed)` generates fixed-bound 10m barrier-and-gap layouts
with randomized barrier width, x position and top/bottom coverage. Some
layouts force a temporary increase in goal distance. Fixed disjoint sets:
`TRAIN_SEEDS=0..19` and `HOLDOUT_SEEDS=1000..1019`.
Different seeds are not evidence of distributional or domain transfer:
both splits share one synthetic scenario family.

- `RandomPolicy`: seeded cardinal actions, restricted observations.
- `GreedyPolicy`: moves toward supplied goal offset; no obstacle planning.
- `OracleAStarPolicy`: **privileged reference**, instantiated with the
  full `Scenario`. It recomputes a shortest path on a 4-connected integer
  grid using Habitat's conservative segment-vs-inflated-AABB candidate test.
  It is not fairly comparable as a restricted-observation controller.
- `run_episode`: accepts any policy implementing the observation-only method;
  invalid returned action types become simulated NOOPs and are counted.
  Exceptions from policy code are not silently reinterpreted as decisions.

Reported metrics are success rate, mean steps, blocked actions, invalid
actions, reward and success-weighted **grid-reference efficiency**. The
reference shortest path uses cardinal grid moves, not an independently
validated continuous geodesic. It is **not Habitat SPL**; diagonal agents
can produce a shorter physical trajectory than the reference grid. The
reported efficiency is capped at 1.0. Reward shaping comes from the
experimental ground and may penalize correct detours, so reward must not
be treated as evidence of learned skill.

A policy's decision count is observed; wall-clock inference latency,
compute cost, calibration error and movement fidelity are not measured.

## Authority and next qualification

Habitat `NO_AUTO_BIND` persists. This code neither connects to
`vera_core.QualifiedVeraRuntime` nor invokes controller adapters.
There is no PS4, Remote Play, driver, network controller or game route.
Testing its software behavior cannot be upgraded into ARK readiness.

> **HOSTILE REVIEWER:** An A* solution on a small known grid is too easy
> and has privileged information. The restricted random/greedy policies can
> fail systematically, making the oracle's success look impressive.
> A single procedural map family also encourages overfitting.

**Accepted.** Interpret oracle success strictly as a reference-path and
environment correctness check. Future engineering should add multiple map
families and an observation-limited agent with memory, test robustness under
noisy/occluded sensor data, and evaluate separately on unseen geometry and
motion models. Do not claim trained navigation or sim-to-ARK transfer on
this result alone.

No third-party package is required for navigation or for the comparison
oracle. The code uses the existing neutral ground and Habitat state kernel.
