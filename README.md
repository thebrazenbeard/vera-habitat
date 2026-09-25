> **License:** Source-visible, not open source. Original material is proprietary. Commercial use, redistribution, hosted-service use, and commercial derivative products require written permission. See [LICENSE](LICENSE) and [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md). Separately identified third-party components retain their own licenses.

# vera-habitat

Engine-neutral virtual-environment substrate for Vera.

The Habitat is a modeled world Vera may observe and interact with. It is not Vera's identity, memory authority, control plane, or automatic bridge to the physical world.

## V1 thesis

A useful habitat needs a deterministic state core before it needs a renderer.

V1 therefore implements:
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

## Quick start

```bash
python -m pip install -e .[dev]
pytest
python -m vera_habitat.demo
```

The demo creates a room, spawns a Vera avatar, applies a simulation-only move, and prints the resulting snapshot and receipt.

## Runtime binding

The canonical Vera portfolio currently classifies this repository as `NO_AUTO_BIND`. This source foundation does not change that. A renderer, Vera runtime route, embodiment link, network transport, or physical-world actuator requires separate design, authorization, and qualification.

See [docs/ARCHITECTURE_V1.md](docs/ARCHITECTURE_V1.md) and [docs/AUTHORITY_AND_RENDERER_BOUNDARY_V1.md](docs/AUTHORITY_AND_RENDERER_BOUNDARY_V1.md).
