# Neutral navigation ground — experimental

This is a deterministic, simulation-only training exercise in the
`vera-habitat` V1 state kernel. It is not ARK: Survival Evolved, does not
contact PS4, Remote Play, or virtual HID, and does not activate Vera runtime
routes. The repository remains `NO_AUTO_BIND`.

## Scope

- 10m x 10m synthetic room, on Habitat's z=0 plane
- immutable `AVATAR`, `GOAL`, and static `OBSTACLE` scene entities
- one bounded `MOVE` or `NOOP` dry-run action per step
- direct world-axis control, configured synthetic metres/second, **not
  ARK-calibrated DualShock-stick dynamics**
- conservative swept avatar-versus-expanded-obstacle AABB intersection checks
  before each accepted `MOVE_ENTITY` proposal
- rejected paths and boundary excursions do not mutate Habitat revisions
- deterministic observations and step receipts with synthetic progress reward,
  terminal goal success, and episode step budget
- ASCII renderer is a disposable scene projection, not an authority source

The adapter does not mutate the existing Habitat V1 core, or install a
hardware / network adapter. Proposals that pass the training guard enter
`HabitatRuntime.propose` as `SIMULATION_ONLY` moves. Rejected candidates are
recorded in a separate in-memory `TrainingStep` ledger rather than falsely
claiming that Habitat's V1 core processed them. The full physics, constraints,
and memory of a real environment are **not** present.

## Run

```bash
python -m pip install -e .
python -m vera_habitat.neutral_demo
python -m pytest -q
```

The scripted demo deliberately attempts an obstructed path, detours around
the wall, and reaches a goal. It is a deterministic **reference course**, not
an autonomous agent, trained policy, or proof of improvement.

## Bridge towards Physica and VERA ARK

The existing [Physica](https://github.com/thebrazenbeard/physica)
`spatial.broad_phase_pairs` is a candidate broad-phase comparison oracle.
The [VERA ARK](https://github.com/thebrazenbeard/vera-ark) dry-run action schema
is a future optional input adapter. The proposed experimental Physica
ARK motion bridge in Draft PR #4 is **not** treated as a merged dependency.

> **HOSTILE REVIEWER:** A 2D path and inflated rectangles fail to model slopes,
> jump arcs, climbing, controller latency, heading-relative axes, game collision
> meshes and unobserved world state. An environment like this could encourage
> false confidence about playing ARK.

**Accepted.** Restrict qualification to deterministic input validation, state
revision discipline, candidate collision rejection, and reproducible synthetic
navigation. A later phase must add partial/noisy perception, temporal dynamics,
calibration and independent held-out evaluation before proposing ARK integration.

There is no claim of calibration, embodiment, gameplay transfer or physical
collision accuracy.
