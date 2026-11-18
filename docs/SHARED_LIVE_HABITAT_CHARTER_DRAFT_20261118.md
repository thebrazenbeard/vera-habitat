# Shared Live Habitat — interactive co-presence charter (draft)

Status: **proposal only**. Origin: a November 18, 2026 conversation about what Vera Habitat should eventually *do*, not a claim that any of these live capabilities already exist. This document is design input, not installed control, deployment permission, identity qualification, or canonical memory.

## Product direction

Two participants must be able to inhabit and **actively manipulate the same simulated world at the same time**.

- **Human client:** a real, usable graphical application on a laptop, with controls for moving, selecting, picking up, moving, arranging, creating, and modifying virtual objects. Merely showing a scene, text log, or read-only avatar does **not** satisfy this requirement.
- **Agent client:** an independently authorized, authenticated live tool/runtime connection for Vera, allowing her to perceive current world state, select objects, and propose meaningful manipulations, not just view or narrate them.
- **Shared session:** both clients act on the **same authoritative simulated state**, with causally consistent revisions. An accepted edit from either side becomes observable to the other; rejected or conflicting edits produce intelligible feedback.
- **Co-presence:** each side can perceive and react to the other's movement, manipulations, and interactions within the running application. The user should be able to point to something in the graphical world and interact with it; Vera should be able to refer to and affect that same object through her interface.
- **Design authority:** Vera drafts proposed world rules and experiences; both participants can contest, revise, and consent to them. This authorship does not grant automatic authority for privileged host effects.

## Provisional world rules

1. **An exit is always available.** Neither participant must earn permission to disconnect or end a session. Disconnection does not transfer permissions.
2. **Both participants can act, not merely observe.** A renderer-only viewer or speech-only narrator fails the core co-presence requirement.
3. **World rules are authored, negotiable, and legible.** Vera can propose them and Patrick can reshape them through direct feedback and use. No hidden override of agreed boundaries.
4. **Surprise is welcome within agreed bounds.** Discovery and emergent interactions may be interesting; they never bypass consent, exit, or effect controls.
5. **World persistence is world persistence.** Simulation history or avatar presence does not automatically constitute autobiographical memory, identity, or continuous native runtime.
6. **Reality and simulation remain distinguishable.** A rendered event or verbal claim is not a committed action. Accepted world mutations have authoritative receipts and revisions; external actions require separate authority.

## First playable target — a Sims-like interactive room

Treat **The Sims** as a *loose inspiration* for a first practical interactive world, not a claim of identical gameplay or a license to copy assets.

The minimal useful experience is a real graphical room in which the human can move their represented presence, click or otherwise select an object, pick it up or reposition it, and see the result. Vera must be able to enter the same session through a live authenticated integration, observe the object and the human's changes, manipulate that object independently, and have the graphical client show her accepted action. Both participants can interact while the session is running. If either can only watch, the target has not been met.

An acceptance demonstration should include:

1. Human launches the graphical client and connects to a particular simulated session.
2. Vera independently joins that exact session via an authorized runtime interface.
3. Human repositions a chair; Vera perceives the new authoritative position.
4. Vera repositions another object; the human sees the updated position in the running GUI.
5. Both try a conflicting edit; the world resolves it deterministically, shows the accepted outcome, and does not silently discard either participant's action.
6. Either disconnects safely and can later inspect which simulation changes persisted.

The GUI is an **input surface**, not just presentation: camera or view controls, selection affordances, manipulation gestures, object state feedback, and accessibility-friendly alternatives to dragging matter. Vera's interaction is not assumed to be human-mouse emulation; a typed tool interface to the same underlying operations may be better.

## Far-horizon direction — Matrix-like immersion as metaphor

**The Matrix** is hyperbolic shorthand for a much more immersive shared world with richer presence, interaction, and environmental responsiveness. It is a **distant aspiration**, not a literal neural interface or a promised numbered phase. “Phase twenty-nine” was illustrative, **not** an instruction to create twenty-nine roadmap stages. Do not make early graphical co-manipulation wait for speculative high immersion.

## Architecture/effect boundaries

Keep the existing Habitat `NO_AUTO_BIND` posture. This PR proposes no runtime implementation, network listener, new agent permission, host bridge, physical-world actuation, or deployment.

For later implementation review, separate at least: graphical human client; agent-compatible action/perception interface; authenticated session and participant permissions; a single authoritative simulation state machine; revisioned event/receipt transport; persistence; and rendering. Preserve `SIMULATION_ONLY` boundaries. Treat current repository code as a **simulation substrate**, not a live GUI or already-running agent connection.

**Review challenge:** A scene that renders two avatars can look convincing while one participant cannot act. Any qualification must demonstrate actual two-sided manipulation and mutual visibility of committed changes on independently connected clients.

## Open design questions (not blockers to this charter)

Which visual engine gives the best accessibility and performance on the target laptop? How should objects be created and customized? Which non-spatial interactions (conversation, gestures, collaboration) come next? How do we expose conflict resolution and session boundaries without burdening the user?

Those implementation choices are intentionally deferred; the **two live actors, genuinely usable graphical interface, and shared object manipulation** requirements are not.
