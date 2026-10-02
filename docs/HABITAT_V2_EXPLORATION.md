# Vera Habitat V2 Exploration

Date: 2026-10-02
Status: EXPLORATION / DESIGN CANDIDATE / NO RUNTIME BINDING

## What V1 actually is

V1 is a small deterministic in-memory world-state kernel:
- finite 3D positions;
- typed entities with free-form metadata;
- spawn and move transitions;
- monotonically increasing world revision;
- immutable sorted snapshots;
- append-only in-process receipts;
- hard rejection of external-effect proposals.

That is a useful seed, but it is not yet a habitat in the richer sense. There is no simulation clock, persistence/replay, spatial topology, perception model, interaction/affordance system, multi-agent ownership, physics/collision model, renderer protocol implementation, or durable event history.

World Zero is not a successor or duplicate: World Zero models real-world system dynamics for scientific comparison; Habitat models an interactive virtual environment.

## V2 thesis

A Habitat should be an engine-neutral, deterministic, replayable **world authority** that can support many renderers and many participants while keeping simulation truth, participant perception, identity, memory and physical-world effects distinct.

```
WORLD_STATE != RENDERED_SCENE
WORLD_STATE != PARTICIPANT_MEMORY
OMNISCIENT_STATE != PERCEIVED_STATE
AVATAR != IDENTITY
SIMULATION_TIME != WALL_TIME
SIMULATED_EFFECT != EXTERNAL_EFFECT
```

## Proposed layers

### 1. Deterministic time and event identity

Introduce explicit simulation ticks and stable event IDs. A transition binds:
- prior revision;
- simulation tick;
- actor/proposer;
- exact action;
- exact target;
- deterministic result;
- resulting revision.

Wall-clock timestamps may be observation metadata but must not determine simulation ordering.

### 2. Durable event log and replay

Replace in-process receipt history as the only record with an append-only event log plus checkpoints. Replaying from a checkpoint plus events must reconstruct the exact world digest.

Required properties:
- idempotent event identity;
- revision CAS;
- deterministic snapshot digest;
- corruption detection;
- checkpoint/current-head verification;
- explicit schema migration.

### 3. World topology and spatial rules

Positions need a world model around them:
- zones/rooms/regions;
- adjacency and traversal;
- bounds;
- occupancy/collision policy;
- portals/doors;
- coordinate-frame identity.

Do not smuggle physical realism into generic coordinates. Physics should be an optional ruleset.

### 4. Typed components and affordances

Move beyond a free-form `kind` plus metadata blob toward typed components/capabilities:
- transform/spatial;
- visible/renderable;
- container/inventory;
- interactable;
- movable;
- agent/avatar;
- sensor/perception source.

Affordances define what actions are valid for a particular entity in a particular state. They do not grant external authority.

### 5. Participant and proposal attribution

Multiple actors should be able to inhabit one world without sharing authority accidentally. Every proposal should bind the participant, represented avatar/entity if any, session/capability context and exact world revision it was based on.

Avatar possession is a simulation relationship, not proof of real-world identity.

### 6. Perception boundary

Do not give every participant the omniscient `SceneSnapshot` by default.

Add a derived perception surface:
```
WORLD_STATE -> SENSOR/PERCEPTION POLICY -> PARTICIPANT_VIEW
```

A participant view can depend on location, line-of-sight, visibility, permissions, sensor type and disclosure rules while remaining a projection of world state.

### 7. Interaction vocabulary

Generalize beyond `MOVE_ENTITY` with typed actions such as:
- move/traverse;
- inspect;
- take/drop/place;
- open/close;
- use;
- speak/signal;
- create/remove where world rules permit.

V2 should prefer small composable verbs over a renderer-specific command language.

### 8. Renderer/engine adapters

Godot, web/Three.js, terminal, VR or other renderers should consume snapshots/views and emit typed proposals. They do not own authoritative world state.

An engine adapter must be replaceable without changing world semantics.

### 9. External-world bridge remains separate

Any physical/device/network side effect stays behind:
```
HABITAT_PROPOSAL
  -> EXTERNAL_EFFECT_REQUEST
  -> AUTHORITY/CURRENTNESS GATE
  -> ADAPTER EFFECT
  -> EXTERNAL READBACK
  -> VERIFIED OUTCOME
```

A virtual light switching on cannot be treated as proof that a real light switched on.

## Candidate first implementation slice

Build the smallest V2 vertical slice around:
1. deterministic simulation tick;
2. append-only event record;
3. world digest + replay;
4. revision-CAS proposal admission;
5. simple room/portal topology;
6. participant-scoped perception query.

Keep physics and graphical rendering out of the first slice.

## Hostile review

> **HOSTILE REVIEWER:** An ECS, physics model, social layer and renderer abstraction could turn a tiny useful kernel into a game engine project with no clear consumer.

**PARTIALLY ACCEPTED.** V2 should not build a game engine. The first implementation slice stops at deterministic state, topology, replay and perception. Rendering and physics remain adapters/rulesets until an actual use case demands them.

> **HOSTILE REVIEWER:** If Vera Mono already has durable state/effect machinery, Habitat may duplicate infrastructure.

**ACCEPTED AS A DESIGN CONSTRAINT.** Habitat should reuse or adapt generic durable-state/effect primitives where interfaces fit, rather than cloning them. World semantics remain Habitat-owned; generic persistence/effect fencing does not.

## Open questions

- Should Habitat remain Vera-branded or become a general `habitat`/virtual-world package with Vera as one participant?
- Is the first real renderer terminal/web, Godot, or another engine?
- Should social dialogue exist as world events or remain outside the simulation state?
- What minimum persistence interface allows local SQLite today without coupling V2 to one storage engine?
- Which Vera Mono primitives are reusable without importing Vera identity semantics?

## Effect boundary

This exploration changes no runtime route, renderer, physical device, provider, credential, deployment or canonical identity/memory state.
