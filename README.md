> **License:** Source-visible, not open source. Original material is proprietary. The [license](LICENSE) permits limited private, noncommercial evaluation; redistribution, commercial use, hosted use, and commercial derivatives require written permission. See [commercial terms](COMMERCIAL_LICENSE.md) and [third-party notices](NOTICE).

# Vera Habitat — deterministic virtual-world toolkit

Vera Habitat is a **Python library for building isolated, inspectable virtual environments**. Applications can maintain a small typed world, propose simulation-only movements, receive acceptance or rejection receipts, export integrity-checked checkpoints, and give renderers detached read-only scene data. Optional utilities support synthetic navigation exercises and reproducible evaluation.

It is designed as a **reusable simulation substrate**: the consumer supplies its own agents, renderer, user interface, and governance. There is no game engine, background daemon, physical actuator, agent identity service, or automatically activated integration with another system.

## What is implemented

| Area | Available source behavior | Boundary |
| --- | --- | --- |
| World state | Typed entities, finite 3D positions, revisions, simulation movement proposals, receipts | One in-memory `HabitatRuntime` owns mutations; external effects are rejected |
| Read-only views | Immutable `SceneSnapshot` and deterministic JSON scene projection | Renderers receive no mutation or transport authority |
| Checkpoints | Canonical JSON export/import with SHA-256 content fingerprint and action-ID replay guard | Integrity is not origin authentication or trusted anti-rollback |
| Optional local persistence | Explicit HMAC-authenticated file save/load and cooperative writer lock | Caller supplies the secret; no service, key, user authentication, or distributed lock is installed |
| Optional rollback anchor | `TrustedAnchor` protocol for a separately protected monotonic compare-and-swap service | Only an interface: no independently trusted provider ships in this repository |
| Spatial and navigation tools | Read-only AABB broad phase, bounded trajectory previews, synthetic navigation and evaluation bundles | Candidate geometry and simulated scores are not contact physics or real-world learning results |
| Physica bridge | Opt-in swept-envelope broad-phase shadow with fail-closed candidate checks | Does not import external actuation rights or prove physical accuracy |

The package is currently version **0.3.5** (`pyproject.toml`) and supports **Python 3.11+**. Its core declares no third-party runtime dependencies; the development extra adds pytest.

## Quick start

From a checkout:

```sh
python -m pip install -e ".[dev]"
python -m pytest
python -m vera_habitat.demo
python -m vera_habitat.neutral_demo
```

The demos create synthetic scenes and print simulation results; they do not contact a device or connect to a host agent.

Minimal standalone application example:

```python
from vera_habitat import (
    ActionProposal, Entity, HabitatRuntime, Position3, render_scene_json,
)

world = HabitatRuntime()
world.spawn(Entity("agent-1", "AVATAR", "test-room", Position3(0, 0, 0)))

receipt = world.propose(ActionProposal.move("agent-1", Position3(1, 0, 0)))
assert receipt.accepted

scene = world.snapshot()
print(render_scene_json(scene))  # Detached JSON for a renderer

checkpoint = world.export_checkpoint()
restored = HabitatRuntime.from_checkpoint(checkpoint)
assert restored.snapshot() == scene
```

An accepted movement changes this *simulated* state only. Reusing a proposal action ID is rejected; restoring a checkpoint does not bind the reconstructed scene to an existing runtime, trusted owner, or device.

## Optional research and integration surfaces

- **Synthetic navigation:** `python -m vera_habitat.navigation_eval --help` documents reproducible train/holdout comparisons, an optional layout-overlap audit, and replay-verifiable evaluation bundles. See [navigation evaluation](docs/NAVIGATION_EVALUATION_V1.md) and [evaluation bundle](docs/EVALUATION_BUNDLE_V1.md). Scores do not establish trained-model generalization.
- **Spatial projection:** [Architecture V2](docs/ARCHITECTURE_V2.md) describes the read-only AABB index, bounded trajectory previews, and replay checks. A broad-phase candidate is not a confirmed collision.
- **Local recovery:** [Authenticated file recovery](docs/LOCAL_AUTHENTICATED_RECOVERY_V1.md) describes explicit HMAC file persistence, atomic replacement, and cooperative locking. Neither hashes nor HMAC alone prevent a valid older checkpoint from being replayed.
- **Trusted anti-rollback:** [Trusted anchor contract](docs/TRUSTED_ANTI_ROLLBACK_V1.md) specifies the separately governed compare-and-swap authority a caller must provide. Without that provider, anti-rollback remains unqualified.
- **Optional physics adapter:** [Physica bridge](docs/PHYSICA_BRIDGE_V1.md) explains the shadow broad-phase and fail-closed cross-check. It is not a full physical simulation or an automatically enabled dependency.
- **Evidence collection:** [Evaluation bundle](docs/EVALUATION_BUNDLE_V1.md) verifies deterministic same-code replays, not an authenticated independent source.

## Integration and authority

Habitat has a deliberate **`NO_AUTO_BIND`** boundary. Importing the package starts no process, opens no network route, installs no renderer, and grants no external permission. A simulated proposal or a scene snapshot is neither consent nor host authorization.

The source does **not** provide cryptographically bound provider identity, a coherent host authorization service, persistent personal identity, an autonomously operating agent, or a route to physical hardware. Applications seeking those capabilities need separate authenticated, host-owned controls and independent qualification. See [Authority and renderer boundary](docs/AUTHORITY_AND_RENDERER_BOUNDARY_V1.md) and [Architecture V1](docs/ARCHITECTURE_V1.md).

## Tests, security and contributions

The [test workflow](.github/workflows/test.yml) exercises supported Python versions and optional integration checks. Run `python -m pytest` after installing the development extra. Source tests and successful CI demonstrate bounded repository behavior, not live-host deployment or a formal proof of safety.

Review [contribution terms](CONTRIBUTING.md), [license](LICENSE), and [security boundaries](docs/AUTHORITY_AND_RENDERER_BOUNDARY_V1.md) before redistributing, integrating or contributing. Historical Vera-specific designs remain in `docs/` for provenance; applications need not adopt their particular identities or device topology.
