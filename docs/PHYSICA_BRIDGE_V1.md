# Physica candidate integration — V1 (2026-10-14)

**Original V1 source bindings:** Habitat parent `f8ffb7dfbaef2e268e3a5e0b4f719956480625e1`;
Physica merged `main` `9cc1ae9c04f728c10d6bdd9f3b277083eb46a834` (PR #6). The
previous closed Physica PR #5 did not land. This adapter requires the actual
`swept_broad_phase_pairs` API from the newly verified revision.

`NeutralTrainingGround(collision_backend="habitat")` remains the default.
Opting into `collision_backend="physica"` imports `physica.spatial` only
at explicit constructor call and raises if unavailable (never silently falls
back). It converts each static obstacle to Physica `AABB`, and each
candidate motion to an initial radius-expanded AABB and exact displacement
map (zero vectors for static obstacles). It queries Physica's
`swept_broad_phase_pairs` and selects the motion's obstacle candidates. The
opt-in backend rejects an outdated provider rather than falling back to
a static query.

Habitat's unchanged swept inflated-AABB slab test is then applied
independently to all obstacles. If Physica misses any Habitat collision
candidate, the step raises before mutation. False-positive broad-phase
candidates do not block valid moves. This is intentional **shadow checking**:
extra work prioritizes behavior parity and fault detection rather than speed.
It is not a real contact solver, time-of-impact solver or physical validation.

The optional GitHub CI matrix installs one of two exact Physica commits:
the original `9cc1ae9c04f728c10d6bdd9f3b277083eb46a834` and the later
reviewed `8160ed36fb77d4764414f854847447fdc23794d6`. It imports the
actual provider and runs both ordinary and precision-edge integration tests.
Normal Habitat dependencies remain unchanged; test skips without Physica
remain explicit in ordinary test jobs.

**2026-10-25 compatibility correction:** The later Physica commit evaluates
swept bounds with exact rational arithmetic, while Habitat's independently
authoritative simulated slab test uses rounded binary64 operations. A nominal
touch can be missed by the naive Physica envelope even though Habitat would
reject the simulated move. The opt-in adapter now expands *candidate* bounds
using a finite scale-relative eight-ULP guard and outward-directed displacement
rounding; it does not change Habitat's collision decision or authority boundary.
This conservative margin has regression and adversarial test evidence, **not**
a formal proof covering every finite floating-point input or physically
validated contact dynamics. Missed candidates still fail closed.
Local opt-in testers may install the same trusted pinned source separately.

Physica had no top-level license file in the inspected source tree;
this change **does not copy its code** or package it with Habitat.
A verified licensing policy is still needed before distributing combined
binary/application artifacts, particularly across distinct projects.

Safety: `NO_AUTO_BIND`; no Vera production integration, network effects,
controller, hardware, physics contact certification or real-world competence.
Source tests do not qualify the optional dependency as a security sandbox.
