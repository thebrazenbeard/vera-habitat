# Physica candidate integration — V1 (2026-10-14)

**Source bindings:** Habitat parent `b39d4924ffd7127e44da5d4e8ec368ccb799386d`;
Physica public `main` `bdb135c680a12101d7a191c71fb7c7d72ab9e04b`.
The previous Physica swept-candidate PR #5 is closed and its code is
**not** on current Physica `main`; no speculative API was invoked.

`NeutralTrainingGround(collision_backend="habitat")` remains the default.
Opting into `collision_backend="physica"` imports `physica.spatial` only
at explicit constructor call and raises if unavailable (never silently falls
back). It converts each static obstacle to Physica `AABB`, and each
candidate motion to a conservative swept **envelope AABB**. It queries
Physica's `broad_phase_pairs` and selects the motion's obstacle candidates.

Habitat's unchanged swept inflated-AABB slab test is then applied
independently to all obstacles. If Physica misses any Habitat collision
candidate, the step raises before mutation. False-positive broad-phase
candidates do not block valid moves. This is intentional **shadow checking**:
extra work prioritizes behavior parity and fault detection rather than speed.
It is not a real contact solver, time-of-impact solver or physical validation.

The pinned GitHub CI job installs only this exact Physica commit for
integration testing and checks that it can actually import. Normal Habitat
dependencies remain unchanged; test skips without Physica remain explicit.
Local opt-in testers may install the same trusted pinned source separately.

Physica currently has no top-level license file in the inspected tree;
this change **does not copy its code** or package it with Habitat.
A verified licensing policy is still needed before distributing combined
binary/application artifacts, particularly across distinct projects.

Safety: `NO_AUTO_BIND`; no Vera production integration, network effects,
controller, hardware, physics contact certification or real-world competence.
Source tests do not qualify the optional dependency as a security sandbox.
