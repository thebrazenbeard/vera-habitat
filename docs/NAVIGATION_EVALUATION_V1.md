# Neutral navigation evaluation V1

**Status:** experimental, deterministic, simulation-only. No ARK gameplay,
no trained Vera policy, no native Vera runtime binding, no external effects.
This source was integrated into Habitat `main` by PR #15. It remains
simulation-only; integration does not qualify ARK gameplay or live Vera use.

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
The optional `build_layout_audit(split=..., family=..., episodes=...)` API and
`python -m vera_habitat.navigation_eval --layout-audit-only` CLI produce a
**separate** `VERA_HABITAT_NAV_LAYOUT_AUDIT_V1` diagnostic. It counts unique
evaluated obstacle layouts, unique training layouts, and reused training
episodes/layouts. This is qualification metadata, not a leakage-resistant
split or evidence of model generalization. Ordinary V1 report payloads,
sealed bundle fingerprints and V1 replay verification remain unchanged;
the audit is intentionally not inserted into them.

### Opt-in geometry-disjoint diagnostic

To exclude training obstacle *shapes*, including shapes that differ only by
global horizontal translation, use a separate holdout report. Its public
signature subtracts the minimum obstacle-left coordinate from each obstacle's
left/right bounds, rounds translated floats to nine decimal places, retains
the exact vertical bounds, and sorts the resulting rectangle tuples. The
selector walks existing holdout seeds in order, keeping the first previously
unseen normalized signature. It removes both training collisions and repeated
selected shapes:

```bash
python -m vera_habitat.navigation_eval --geometry-disjoint --family zigzag
python -m vera_habitat.navigation_eval --geometry-disjoint --family zigzag --episodes 4 --policies greedy oracle
```

At this revision the bounded public pool yields **no unseen barrier shapes**:
all 8 raw-coordinate novel barrier layouts are horizontal translations of
training shapes. Thus `--geometry-disjoint --family barrier` fails with an
explicit zero-capacity error instead of inventing evidence. The zigzag family
yields **9 unseen shapes** (`1000, 1001, 1002, 1004, 1006, 1008, 1014, 1015,
1019`). Without `--episodes`, all available disjoint zigzag shapes are
evaluated. Requesting more than capacity fails closed; the selector does not
silently supplement from overlapping shapes. The mode accepts only the
holdout split and rejects V1 `--bundle` and `--layout-audit-only` combinations
rather than reusing their identities.

The JSON schema is `VERA_HABITAT_NAV_GEOMETRY_DISJOINT_EVAL_V1`, separate from
the established seed-disjoint `VERA_HABITAT_NAV_EVALUATION_V1` schema. Neither
historical V1 reports nor sealed replay payloads nor their fingerprints are
changed. Run the ordinary CLI to reproduce old reports and verify old replay
bundles. This additional report is a public, synthetic diagnostic: generators,
seeds, layouts, and selection are known, so it **cannot qualify model
generalization**, unseen dynamics, visual navigation, runtime learning,
or actual ARK/PS4 performance. This normalization does not equate rotations,
vertical translations, altered start/goal relationships or changes in
navigation dynamics, and remains narrower than semantic or motion-model
novelty. `NO_AUTO_BIND` remains in force.

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
Nor do distinct seeds imply distinct geometry. At this revision the 20
holdout seeds reproduce layouts found in the training set in **6/20** barrier
episodes and **3/20** zigzag episodes; the generator has only 32 possible
barrier geometries. The current `holdout` means **seed-disjoint**, not
**previously unseen obstacle configuration**. These collisions are exposed
via the separate audit and documented here, without silently changing
historical seed lists, benchmark outcomes, or V1 bundles.

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
