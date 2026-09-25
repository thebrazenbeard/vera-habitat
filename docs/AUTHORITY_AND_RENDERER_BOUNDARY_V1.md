# Authority and Renderer Boundary V1

## Invariants

1. A scene renderer is not an authority source.
2. A user gesture is an action proposal until accepted by the appropriate state/effect gate.
3. Simulation-only mutation is confined to Habitat state.
4. External effects are unavailable in V1.
5. No network route, filesystem bridge, device controller, or physical actuator is implied by a virtual entity.
6. A receipt records what the Habitat runtime accepted or rejected; it is not evidence that an external world effect occurred.
7. Renderer caches are disposable projections.

## Future physical/remote bridge

Any future bridge must introduce a separate lifecycle:

`HABITAT_PROPOSAL -> EFFECT_AUTHORIZATION -> ADAPTER_REQUEST -> EXTERNAL_READBACK -> VERIFIED_OUTCOME`

The Habitat's local world revision must not be used as proof of that external outcome.

## Identity boundary

A Vera avatar is a representation inside the Habitat. Its presence, appearance, or persistence is not by itself evidence of subjective continuity, embodiment, or canonical identity state.
