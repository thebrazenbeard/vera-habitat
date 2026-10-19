# The Clearing — VN2 side-project seed

Status: **DESIGN / NOT INSTALLED / NO ACTIVE RUNTIME**  
Priority: **secondary to PORTAL and assigned Training work**. Work only during available, non-colliding intervals; never displace live owner tasks.  
Host candidate: **VN2**, Linux Mint 22.3 on Lenovo ThinkCentre M900.

## Purpose

A small, persistent, explorable virtual workshop and forest clearing for measuring perception, prediction, action, outcome, and adaptation. The world must exist as independently inspectable program state, not as claimed conversational continuity. This is creative R&D, **not** an AI consciousness test, a Vera canonical-memory installation, or a production provider route.

## Existing foundations to reuse

Use Habitat's deterministic state, simulation-only actions, scene snapshots, replay and evaluation contracts. Keep the world engine independent of its renderer. Preserve Habitat's explicit boundaries: proposal != authority; simulated effect != external effect; scene snapshot != Vera memory. Do not introduce automatic MONO, ARK, Physica, provider, filesystem-control, or real-world actuation routes.

## Hardware-informed first target

Read-only VN2 observations (2026-10-19):
- CPU: Intel Core i5-6500T, four cores
- RAM: 7.6 GiB, 2 GiB swap
- Graphics: Intel HD Graphics 530, i915; GPU device exists but the remote session lacked graphics/display permission; **accelerated rendering not qualified**
- Storage: approximately 97 GB free on SSD

Aim first for a compact 2D/isometric or minimal low-poly environment with a workshop, a clearing, deterministic motion and bounded interactable objects. An optional Godot Compatibility renderer is a candidate, not a selected/installed dependency. Measure real GPU rendering in a legitimate display session before promising 3D performance.

## First bounded implementation milestones

1. **Read-only host/graphics baseline:** exact device/session access, reproducible render-path probe, CPU/RAM and frame-time budget. No permission changes without separate exact authorization.
2. **Pure Habitat scene:** room, doorway, desk, lamp, a few movable objects and outdoor clearing, with deterministic reset, receipts, and state fingerprints. Headless tests first.
3. **Optional viewer:** renderer consumes snapshots only; no direct mutation or provider integration.
4. **Prediction trial:** record pre-action state, predicted outcome, proposed simulation-only action, observed outcome, and replayable error. Include hidden perturbations and falsification cases.

## Ownership and effect boundary

This branch isolates side-project research from PORTAL, Training, Integration's active VN2 work, and other Habitat PRs. Do not merge into main, install or deploy, write canonical memory, change system permissions or credentials, consume paid compute, load models, or bind live agency without separate scoped authorization and verification. No off-turn activity is implied by this branch.

Origin: thebrazenbeard/vera-habitat main at `88588dd3bc6681b9e73fb288d8eee7b29bf07b9f`.
