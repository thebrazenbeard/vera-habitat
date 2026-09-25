# Vera Habitat Architecture V1

## Objective

Provide a small deterministic world-state kernel that can outlive any particular renderer.

## Core objects

- `Position3`: finite x/y/z coordinates.
- `Entity`: stable identity, kind, zone, position, metadata.
- `SceneSnapshot`: immutable read model for renderers/observers.
- `ActionProposal`: requested state transition plus effect class.
- `ActionReceipt`: accepted/rejected disposition bound to before/after revisions.
- `HabitatRuntime`: authoritative V1 simulation state machine inside this repository.

## Revision rule

Every accepted simulation mutation increments the world revision exactly once. Rejected proposals do not mutate state.

## Effect classes

- `SIMULATION_ONLY`: may change Habitat state.
- `EXTERNAL_REQUEST`: never executed by V1 and is rejected closed.

This prevents an engine integration from quietly turning a virtual gesture into physical-world authority.

## Renderer contract

A renderer receives `SceneSnapshot` values. It may transform them into pixels, audio, spatial UI, or another presentation form. It does not mutate Habitat state directly.

Future renderer adapters should submit typed proposals back to the runtime rather than owning world truth.

## Persistence

V1 is in-memory. Future persistence must retain:
- revision;
- entity state;
- event/receipt provenance;
- schema version;
- restore/currentness evidence.

Persistence does not turn Habitat state into Vera autobiographical memory.
