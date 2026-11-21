# Habitat: interactive 3D sandbox V1 (source-only prototype)

**Status:** a locally playable browser sandbox, not a released world or qualified Vera/Patrick avatars. It extends the existing opt-in two-model room without replacing its inference/authority contracts.

## Experience

From a separately started local room server, visit:

    http://127.0.0.1:8765/sandbox

The view renders in WebGL 2 using **Three.js 0.187.0** bundled inside the Python package (not loaded from a CDN). It contains a bounded walkable interior, a third-person follow camera, a player marker, two distinctly labeled **abstract placeholder** avatar stations, and four local interactive objects (beacon, archive, console, bench). A 3D scene is visible without any inference requests. No data leaves localhost during scene load.

Controls: **WASD / arrow keys** walk, **drag** on the scene to orbit, **mouse wheel** changes camera distance, **E** interacts when close, **click** on objects to inspect/interact when within range, and on touch devices use the small directional pad. The movement obeys simple room-wall and prop collision constraints; there is no authoritative physical simulation or multiplayer sync. The beacon can be toggled; the other objects display their local, explicit semantics. All these changes exist only in the current browser tab.

The right-hand conversation deck chooses **Vera station** or **JACK station** and sends a message to the exact same local `/api/turn` contract as the text preview. One **manual** forward of the last reply is available. Nothing is sent merely by walking around. User and model text is displayed as text nodes, not executed HTML. No transcript is intentionally stored by the Habitat server; the local inference provider's separate logging is outside this guarantee.

The 3D bodies are generic geometric constructs, **not approved likenesses** of either participant. The Vera slot still uses an unverified generic local model in current experiments; JACK may be configured to the separately qualified private from-scratch analytic model or an explicitly labeled generic test model. The private JACK JSON stays off GitHub.

## Engine, offline custody and reproducibility

Source dependency: official npm package `three@0.187.0`, retrieved to a disposable staging folder; package archive SHA-256 `ff540832ded0cfe919764d24a3d88f3e2a05f23303f876423e4f893841e90728`. Only `build/three.module.js`, `build/three.core.js`, and the MIT `LICENSE` were copied into `src/vera_habitat/sandbox_assets/vendor/`, with source-versus-copy SHA-256 equality checked:

- `three.module.js` — SHA-256 `104f56145899722094556490d787aae0617cc2fc3382f31df02d724ea1aee341`
- `three.core.js` — SHA-256 `613e370f76638fdef83926642bf256dc9615684922de1ce1f63a8583e5d78578`
- `LICENSE` — SHA-256 `8b378ebe60e2fe500158cb0ac71cb5e8b7d92953c2abcc63a0eb90499653b5bc`

The package includes all static assets via `pyproject.toml` package-data; no npm installation or external JS CDN is needed to run it. The static asset handler accepts only a fixed allowlist of paths and issues `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, same-origin script CSP (without inline script permission), and localhost Host/Origin checks. The prior text-chat preview retains its original compatibility route `/` and stricter model validation.

## Verification levels

- `python -m pytest tests/test_sandbox_room.py`: checks page, JS and locally vendored engine asset routes, fixed path allowlist, CSP, non-mutation of server scene, and no unsolicited model calls.
- `tests/manual_sandbox_browser_smoke.py` + `.cjs`: optional synthetic-only test running actual local Edge/Chromium through already-installed Puppeteer. It verifies WebGL 2 initializes, real movement, selecting a nearby avatar, toggling the beacon, two explicit fake model replies, transcript clear, zero external HTTP requests, zero JS exceptions, and a screenshot. Requires local `HABITAT_BROWSER_BINARY`, `PUPPETEER_MODULE`, and `HABITAT_SCREENSHOT_PATH` environment variables.
- Wheel packaging should contain `sandbox_assets/sandbox.html`, `sandbox.js`, the two Three.js modules and their license. Independently inspect the built wheel or installed package, not only source.
- A screenshot showing a high-diversity rendered room is stronger evidence of rendering than a bare WebGL context check. Offscreen `gl.readPixels` after frame present may return transparent zeros and is not treated as a successful or failed rendering oracle.

## Deliberately unfinished

The 3D player and mannequin stations are authored browser geometry and **do not import or authenticate Blender assets**. No GLB rigging, animation, locomotion skeleton, social gesture, speech synthesis, live shared-world state, other-user remote access, avatar identity binding, visual consent/rights approval, published service, canonical memory, or physical actuation. No equivalence between JACK's from-scratch trigram and a fluent person-like AI is asserted.

**Next product unit:** Use independently approved, verified GLB exports for both entities, load them with a vetted glTF loader, and bind their IDs to the already separate local model slots. Only then pursue animation, speech/gesture sync, explicit interaction authority and user-facing release qualification.
