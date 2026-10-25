> **License:** Source-visible, not open source. Original material is proprietary. Commercial use, redistribution, hosted-service use, and commercial derivative products require written permission. See [LICENSE](LICENSE) and [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md). Separately identified third-party components retain their own licenses.

# vera-habitat

Engine-neutral virtual-environment substrate for Vera.

The Habitat is a modeled world Vera may observe and interact with. It is not Vera's identity, memory authority, control plane, or automatic bridge to the physical world.

## V1 thesis

A useful habitat needs a deterministic state core before it needs a renderer.

The V1 foundation implements:
- versioned virtual world state;
- typed entities and 3D positions;
- deterministic simulation-only actions;
- immutable scene snapshots for renderers;
- append-only receipts for accepted/rejected proposals;
- an explicit boundary between virtual simulation and external effects;
- tests and CI.

`RENDERING != WORLD_STATE`

`SIMULATED_EFFECT != EXTERNAL_EFFECT`

`ACTION_PROPOSAL != AUTHORITY`

`SCENE_SNAPSHOT != MEMORY`

## V2: source-only reconstruction and spatial capability

V2 adds:
- a portable JSON checkpoint of scene, receipt history and replay guard, with
  schema validation and SHA-256 content fingerprinting (**not** authenticity);
- protection against applying the same proposal action ID more than once,
  including a restore-time check for causally impossible duplicate-action
  and duplicate-spawn receipts;
- a detached renderer JSON projection with no mutation authority;
- a read-only 3D AABB broad-phase candidate index, with independent tests;
- bounded `times`/`states` trajectory-to-*proposal* previews compatible
  with Physica's numerical output protocol, without automatic submission;
- adversarial regression tests, source-bound review of the eleven supplied
  physics, geometry, learning and Unreal interoperability repositories.

These are **not** a physical engine, persistent database, autonomous RL agent,
renderer, or a new authority route to Vera. See
[Architecture V2](docs/ARCHITECTURE_V2.md) for tested contracts and limits.

## V0.3 candidate: opt-in authenticated local recovery

`AuthenticatedFileStore` supports explicit local save/load of simulated
Habitat checkpoints, authenticated by an **externally supplied HMAC key**.
It preserves versioned state and action receipts, requires an expected prior
seal and an append-only receipt continuation before overwriting, and uses
same-directory temporary files with atomic replacement. Loading validates the keyed MAC before reconstructing the world.

Importing Habitat neither creates a file nor connects to Vera. This does
**not** authenticate the writer's personal identity, stop signed-file
rollback, coordinate concurrent writers, or establish canonical Vera
runtime/memory currentness. No secret keys or services are provisioned.

See [Local authenticated recovery V1](docs/LOCAL_AUTHENTICATED_RECOVERY_V1.md)
for an explicit usage example and the security/failure limitations.

## V0.3.1 candidate: cooperating local writer coordination

The optional authenticated file store now takes a persistent sidecar OS lock
for the full predecessor-check/write critical section. Timeouts fail closed;
a second cooperating process cannot overwrite a winning generation using a
stale predecessor seal. The lock does **not** solve trusted anti-rollback,
distributed/NAS concurrency, or hostile file tampering. See the
[recovery threat model](docs/LOCAL_AUTHENTICATED_RECOVERY_V1.md).

## V0.3.2 candidate: optional external anti-rollback anchor

An explicit `TrustedAnchor` protocol can guard opt-in local checkpoint
loads and saves against stale sealed files **only when supplied with a real,
independently protected monotonic compare-and-swap authority**. No anchor
provider, network connection, key, service, or external effect is installed.
The default unanchored store retains its previous rollback limitations.
A file-write failure after a successful high-water advance fails recovery
closed until separately governed reconciliation. See
[anchored recovery](docs/TRUSTED_ANTI_ROLLBACK_V1.md).

## V0.3.3 candidate: replay-verifiable navigation evaluation

The optional `navigation_eval --bundle` output has a deterministic public
SHA-256 report fingerprint and can be replay-checked with
`vera_habitat.eval_bundle.verify_evaluation_bundle`. Default CLI output is
unchanged. Same-code replay is **not** authentication or independent evidence.
See [evaluation bundle](docs/EVALUATION_BUNDLE_V1.md).

## Optional navigation layout-overlap audit

The opt-in command below reports repeated synthetic obstacle layouts
between the seed-disjoint training and holdout sets. It emits a separate
`VERA_HABITAT_NAV_LAYOUT_AUDIT_V1` diagnostic without modifying ordinary
navigation evaluation reports or historical sealed V1 bundles. It does not
demonstrate model generalization or physical prediction validity. See
[navigation evaluation](docs/NAVIGATION_EVALUATION_V1.md).

```bash
python -m vera_habitat.navigation_eval --layout-audit-only --split holdout --episodes 20
```

## Optional Physica shadow broad-phase

Habitat can explicitly use Physica's deterministic swept-envelope 2D AABB candidate sweep in
`NeutralTrainingGround(collision_backend="physica")`. The ordinary backend is
unchanged. The Physica adapter checks its candidates against Habitat's
independent swept collision logic and fails closed on missing candidates.
A separate pinned-source CI job tests this opt-in integration; it is **not**
full physics or contact certification. See [Physica integration](docs/PHYSICA_BRIDGE_V1.md).

## Quick start

```bash
python -m pip install -e .[dev]
pytest
python -m vera_habitat.demo
```

The demo creates a room, spawns a Vera avatar, applies a simulation-only
move, and prints the snapshot and receipt.

```python
from vera_habitat import (
    HabitatRuntime, AABB3, SpatialProjection, render_scene_json, Position3,
)

# World state is still owned by HabitatRuntime, never by its projection.
world = HabitatRuntime()
# After explicitly spawning entities and accepting any proposals:
checkpoint = world.export_checkpoint()
restored = HabitatRuntime.from_checkpoint(checkpoint)
scene_json = render_scene_json(restored.snapshot())
```

A checkpoint has a digest for integrity, not a signed origin. Its source label
and source-control commit do **not** imply a live Vera runtime was updated.

## Runtime binding

The canonical Vera portfolio currently classifies this repository as `NO_AUTO_BIND`. This source foundation does not change that. A renderer, Vera runtime route, embodiment link, network transport, or physical-world actuator requires separate design, authorization, and qualification.

See [Architecture V1](docs/ARCHITECTURE_V1.md), [Architecture V2](docs/ARCHITECTURE_V2.md), and [Authority and renderer boundary](docs/AUTHORITY_AND_RENDERER_BOUNDARY_V1.md).
