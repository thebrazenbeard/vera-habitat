# Vera Habitat V2: reconstruction, spatial observation and simulation previews

Source-scoped expansion of the deterministic engine-neutral Habitat. No renderer,
network endpoint, runtime activation, identity persistence, autonomous decision
loop, hardware actuator, or background service was installed.

## State and authority contract

- **One state authority:** `HabitatRuntime` owns scene mutations, revisions
  and receipt order in memory.
- **No duplicate action application:** each well-formed proposal action ID is
  admitted at most once, including rejections. Replays return
  `DUPLICATE_ACTION_ID` without changing the scene revision.
- **No external effects:** `EffectClass.EXTERNAL_REQUEST` still fails closed;
  `MOVE_ENTITY` can only update an in-memory entity.
- **Checkpoint export/import:** `export_checkpoint()` serializes scene,
  receipt history and the duplicate-action guard as stable canonical JSON.
  `from_checkpoint(json_text)` verifies SHA-256, schema, value types, sorted
  membership, receipt-revision continuity and action-ID correspondence.
  The importer rejects causally impossible duplicates: duplicate-spawn
  rejection without a prior accepted spawn, duplicate-action rejection without
  an earlier proposal, and multiple accepted applications of one action ID.
  Ordinary duplicate rejections remain importable and replay-safe.
  Restoring constructs a *new isolated runtime*, not a current Vera endpoint.
- **Checkpoint caveat:** SHA-256 is a *content fingerprint*, not a digital
  signature, trusted production currentness, or proof of actual historical
  actions. Anyone who can rewrite a file can recompute its digest. There is
  no disk persistence or authenticated writer in V2.
- **Bounded import:** checkpoints are capped at one MiB. Duplicate JSON keys
  are rejected. Changing or forging scene state cannot cause an external effect.
- **Read-only 3D spatial view:** `SpatialProjection` accepts scene snapshots
  and explicit validated `AABB3` boxes. Overlaps are filtered by zone,
  x/y/z dimensions and stable entity IDs. This is a *broad-phase candidate*
  pass, **not** contact mechanics or interpenetration correction.
- **Renderer-safe export:** `render_scene_json(snapshot)` creates a detached
  JSON projection bearing world revision and
  `authority:READ_ONLY_PROJECTION`. Editing the JSON cannot mutate the world.
- **Numerical trajectory preview:** `preview_trajectory_moves` uses the
  `times`/`states` interface of Physica `Trajectory`, validates finite
  monotonic samples and enforces a candidate budget **while reading external
  iterables**: at most `max_moves + 2` samples are read before rejection,
  each state row is limited to 1,024 values, and the entire preview to
  1,000,000 state values. Before proposals are created, the sum of all
  generated action-ID lengths is capped at 1,000,000 characters, preventing
  a large caller-provided prefix from being multiplied by every move.
  Huge integers that cannot represent finite coordinates or timestamps
  are rejected with `ValueError`. These limits prevent accidental unbounded
  materialization; Python iterator callbacks are not a security sandbox.
  It produces
  **simulation-only proposals without submitting any of them**.
  Explicit `HabitatRuntime.propose` still applies the authority gate.
- **No asserted memory/identity:** a scene avatar, receipt, restore or renderer
  projection is not Vera's logical identity, subjective experience or memory.

## Reproduction

From an isolated source checkout:

```sh
python -m pip install -e ".[dev]"
python -m pytest -q
python -m vera_habitat.demo
```

Python 3.11-3.13 GitHub CI tests the dependency-free core. A sample session:

```python
from vera_habitat import (
    HabitatRuntime, Entity, Position3, ActionProposal, AABB3,
    SpatialProjection, render_scene_json,
)

world = HabitatRuntime()
world.spawn(Entity("vera", "AVATAR", "home", Position3(0, 0, 0)))
proposal = ActionProposal.move("vera", Position3(1, 0, 0))
accepted = world.propose(proposal)
assert accepted.accepted
assert world.propose(proposal).disposition == "DUPLICATE_ACTION_ID"
checkpoint = world.export_checkpoint()
restored = HabitatRuntime.from_checkpoint(checkpoint)
assert restored.snapshot() == world.snapshot()
renderer_data = render_scene_json(restored.snapshot())
```

`ActionProposal.move` generates a new UUID by design; callers requiring
deterministic replay IDs can construct explicit `ActionProposal` records or
use a bounded numerical trace preview.

## Source mechanism review (inspected Git revisions)

All eleven external repositories supplied during the Physica continuation,
plus Physica itself, informed the *interfaces*, not copied implementation:

| Source | Mechanism examined | Habitat disposition |
| --- | --- | --- |
| [PhysicsJS @ b9eca16](https://github.com/wellcaffeinated/PhysicsJS/tree/b9eca1634b6db222571e7e820a09404513fe2e46) | Deterministic-ish discrete world update, integrator/timestep and sleep | Separate world state from temporal execution; no archived JS runtime dependency |
| [Jolt @ a4b24c3](https://github.com/jrouwe/JoltPhysics/tree/a4b24c3fadd7eade0435f27e9d6a07564273eb5f) | Native broad/narrow-phase, body layers and body lifecycle | Keep 3D candidate detection distinct from collision response or native integration |
| [PhysicsNeMo @ f9b2721](https://github.com/NVIDIA/physicsnemo/tree/f9b2721dfbc0299a39bd6322a039b0dd268a35cb) | Scientific learning and explicit validation | No model/training claims or GPU requirement in Habitat V2 |
| [TheAlgorithms C++ @ fdcc29b](https://github.com/TheAlgorithms/C-Plus-Plus/tree/fdcc29b0ac2848e9d1a8d926e171cc5b39f97759) | Computational geometry tests | Use independent quadratic 3D oracle; no educational source copied |
| [Isaac Lab @ bbcbab6](https://github.com/isaac-sim/IsaacLab/tree/bbcbab6b64d5538c1e6800646d57b462389c1410) | Explicit RL environment action, observation, reset boundaries | No autonomous step, joint-actuator route or Isaac Sim install |
| [MuJoCo @ 4110357](https://github.com/google-deepmind/mujoco/tree/4110357126a3c6f35d828500044d67d7ba660533) | Articulated model definitions and simulator compilation | Future optional translator must specify units and zones, not assert scene equivalence |
| [Box2D @ ac7c751](https://github.com/erincatto/box2d/tree/ac7c751eaeddbabdc1c4d41ae4f3a25d78627790) | Separately usable geometry/broad-phase query | Implement independent zone-bound AABB candidate layer, not a rigid-body engine |
| [UnrealEnginePython @ 4b5da5b](https://github.com/20tab/UnrealEnginePython/tree/4b5da5bf4ca598e8d0f67eb938749bc381a67d6c) | Legacy engine Python/physics bridge and actor lifecycle | Explicitly defer any embedded engine control or UE4 deployment |
| [miyosuda/UNREAL @ 31d4886](https://github.com/miyosuda/unreal/tree/31d4886149412fa248f6efa490ab65bd2f425cde) | UNsupervised REinforcement and Auxiliary Learning; reward-aware experience frames | Distinguish offline candidate/observation flows from training and action authority; *not Unreal Engine* |
| [UnrealCLR @ 8a517e2](https://github.com/nxrighthere/UnrealCLR/tree/8a517e23b3b76399d77d50a3b8ad0cb8887c2a8e) | Managed runtime/engine host lifecycle and marshaling | No .NET/UE host automatically launched or installed |
| [Dumper-7 @ dd8fe34](https://github.com/Encryqed/Dumper-7/tree/dd8fe34df8283378a1055386eee195005a100924) | Game-specific injected SDK generation | Excluded: no need for game-process introspection or injection |
| [Physica @ c3c7986](https://github.com/thebrazenbeard/physica/tree/c3c7986f6c69fb09254d11eb46d0814876801b9b) | SI numerical trajectories, reproducible simulation and research ceilings | Define a pure *preview* adapter for compatible `times`/`states`; no required runtime dependency |

This is architectural source study, not compatibility certification or a
line-by-line audit. Third-party license obligations remain applicable to any
future library/code adoption. No upstream code is embedded in Habitat V2.

## Separate integration gates

1. Scene persistence needs an authenticated store and write/readback protocol;
   JSON export alone cannot establish durable or current Vera state.
2. A renderer must consume read-only snapshots, never own world state.
3. A physics engine integration must define full shape, units, timestep,
   provenance and collision semantics; contact candidates are not collisions.
4. Any RL policy must be tested in a sandbox with separated train/evaluation
   data and still pass the simulation-only proposal authority gate.
5. Any external or physical action requires new explicit scope, authorization,
   adapter request and separately verified external outcome.

Existing open [PR #6](https://github.com/thebrazenbeard/vera-habitat/pull/6)
hardens identity input types independently. This V2 work does not alter its
branch, merge, or source qualification.
