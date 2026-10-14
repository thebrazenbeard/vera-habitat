# Restricted-observation memory navigation baseline V1

**Status:** deterministic synthetic navigation research, not learned control,
not ARK: Survival Evolved, and not an active Vera runtime binding.

Source branch: `feat/neutral-navigation-memory-baseline`, stacked on the
navigation-evaluation Draft PR #9, which is stacked on the neutral-ground
Draft PR #7. The separate Habitat V2 Draft PR #8 was not modified.

## Behavior and interface

`MemoryMapPolicy.choose_action(AgentObservation)` uses the existing
observation-only policy API. It is constructed without a `Scenario`,
`HabitatRuntime`, full map or renderer. It accumulates locally clipped
visible obstacle rectangles in a private in-process map and remembers
failed edges. At each step it replans by deterministic grid A* over
**known** blocked edges, treating unseen edges optimistically as free.

This is a **hand-coded, stateful planning baseline**. It is not neural
training, learned world modeling, independent Vera identity, self-directed
policy evolution or evidence of conscious embodiment.

Assumptions visible to the policy:
- synthetic exact avatar x/y and goal-relative x/y; not estimated visually
- static square-room grid extent 10 and avatar radius 0.2 as task rules
- cardinal unit moves of 1000 ms; no acceleration, camera or turn dynamics
- locally clipped axis-aligned obstacle fragments, no occlusion modeling
- the previous action's acceptance/rejection disposition
- programmatic reset clears memory; memory is in-process, not Blotter or
  autobiographical/canonical Vera memory

The observation API is a *discipline*, not a security sandbox. Python code
running in the same process is not prevented from importing other modules.

## Stress families and evaluation

The original `barrier` family has one randomized obstacle. The new
`zigzag` family uses two nonoverlapping vertical barriers with opposite
gaps; the route commonly requires motion away from the goal. Seeds remain
deterministic with disjoint labels for train (0..19) and holdout (1000..1019).
These labels do **not** prove statistical independence or out-of-distribution
generalization: each split shares the same generator family.

```powershell
$env:PYTHONPATH = "src"
python -m vera_habitat.navigation_eval --split holdout --episodes 20 --policies greedy memory oracle
python -m vera_habitat.navigation_eval --family zigzag --max-steps 60 --split holdout --episodes 20 --policies greedy memory oracle
python -m vera_habitat.navigation_eval --family zigzag --max-steps 60 --sensor-range 0.25 --policies memory oracle
python -m pytest -q
```

Measured on Lappy in a local Python 3.14 checkout (20 holdout seeds, V1
grid benchmark, same code for all policies):

| Scenario | Policy | Success | Mean steps | Mean blocked actions |
| --- | --- | ---: | ---: | ---: |
| barrier, range 2, budget 40 | greedy | 0/20 | 40 | 35.9 |
| barrier, range 2, budget 40 | memory | 20/20 | 20.8 | 0 |
| barrier, range 2, budget 40 | privileged oracle | 20/20 | 14.1 | 0 |
| zigzag, range 2, budget 60 | greedy | 0/20 | 60 | 57.5 |
| zigzag, range 2, budget 60 | memory | 20/20 | 25.9 | 0 |
| zigzag, range 2, budget 60 | privileged oracle | 20/20 | 25.9 | 0 |
| zigzag, range 0.5, budget 60 | memory | 20/20 | 33.35 | 5.35 |
| zigzag, range 0.25, budget 60 | memory | 20/20 | 36.95 | 8.95 |

The memory policy and the oracle may match when available local geometry
already reveals enough of the optimal path. The oracle is explicitly
**privileged** and uses the entire Scenario. Neither policy uses learned
parameters. The 'success-weighted grid efficiency' metric is relative to
this simulator's cardinal-grid reference, not a physical SPL measurement.

## Known weaknesses and falsifiers

> **Cricket hostile challenge:** Two families and 20 seed labels do not
> constitute transfer. A deterministic planner with exact synthetic
> localization can ace both families and fail immediately in first-person
> partial vision, unfamiliar geometry, moving obstacles or noisy motion.

**Accepted.** Next research needs independent layout classes, occluded/noisy
perception, heading-relative controls, uncertainty calibration, map aging,
resets across episode boundaries, and policy-vs-classical-planner comparisons
under matched information budgets. A complete 3D game simulation and a
hardware-control interface are not prerequisites.

A successful Habitat step changes only the local simulated world. The
repository remains `NO_AUTO_BIND`. It does not send DualShock reports,
launch Remote Play, interact with a PS4, deploy drivers, change canonical
memory, or install `vera_core.QualifiedVeraRuntime`.
