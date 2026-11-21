# Opt-in, hash-bound private GLB previews — experimental Habitat integration

**State:** Tested source candidate stacked on Habitat local-room PR #35.
This is neither an approved avatar nor a deployed Habitat, identity service,
trained model, Blender master, or automatically running local service.

The objective is narrow and observable: load an already-existing experimental
3D export into the corresponding model *station*, while keeping the original
two-slot local model conversation path and explicit forwarding intact. A model
slot does not authenticate a person, and visual geometry does not authenticate
a model. Neither participant receives new permissions through the preview.

## Opt-in invocation

The independently started, loopback-only `vera-habitat-local-room` CLI adds
these optional paired arguments:

- `--vera-preview-glb <absolute private .glb path>`
- `--vera-preview-sha256 <exact lowercase SHA-256>`
- Analogous `--jack-preview-glb` and `--jack-preview-sha256`.

One field without its partner fails before the listener starts. The default
without preview arguments remains the previous abstract, unverified mannequins.
Use a separately occupied-free loopback port; port 8765 may already belong to
an unrelated host service and must not be displaced.

## Trust and renderer contract

The server resolves and validates a local GLB of at most 16 MiB, exact SHA-256,
glTF 2 header, complete aligned JSON, and a single embedded BIN chunk. Any
`uri` anywhere inside glTF JSON is rejected; external textures or resources
are unavailable in this path. The SHA-256 is checked before server binding
**and again on every GET**, so a changed local asset fails with HTTP 503.
A missing/unconfigured slot returns 404. The fixed `/api/preview-assets`
metadata contains only slot, relative URL, digest and
`UNVERIFIED_EXPERIMENTAL_PREVIEW` label, never a private filesystem path.

The browser's locally vendored Three.js 0.187.0 `GLTFLoader` imports a GLB
only from `/sandbox/previews/{vera|jack}.glb` after receiving its matching
opt-in slot metadata. On success, it fits the visual candidate inside the
existing station, hides the mannequin, keeps the model slot unchanged, and
labels the mesh **EXPERIMENTAL GLB · NOT APPROVED**. If it is unavailable, the
original geometry remains. The original server-side `/api/scene` projection
and room state remain non-authoritative; no file upload or generic file URL
endpoint was added. Only localhost Host/Origin requests are accepted.

The GLTFLoader, SkeletonUtils and BufferGeometryUtils source is taken from
the exact pinned official `three@0.187.0` npm package already used by Habitat.
The imports were rewritten only to point to the locally bundled Three.js
module. The original MIT LICENSE remains bundled. No runtime CDN or npm call.

## Host verification and meaningful limitations

On an isolated Lappy checkout stacked on PR35, a pre-existing, noncanonical
Vera experimental GLB was validated in-memory, served over a random loopback
port, and rendered by a real Microsoft Edge browser. Its exact SHA-256 and
private path are held in local receipts, not bundled in this repository.
Browser acceptance verified movement, beacon, manual fake-model forwarding,
transcript clearing, nonblank screenshot, zero JavaScript errors, and zero
external requests. The server was shut down after the test.

The first **real** two-model trial returned HTTP 503 from the generic Vera
test slot. Direct Ollama diagnosis found that the local Qwen3.5 0.8B model
spent all 160 generated tokens on hidden thinking with zero visible response.
A new test first failed when `think` was absent from the Ollama request.
The local-room client now explicitly sets `think:false`. The real trial then
returned visible text from the generic Vera test model and from the separate
private source-calculated native JACK model after one explicit forward.
A second new room process restored both private model/mesh bindings and
received another native JACK reply. No generated private text is logged here.

This is a **reversible local preview**, not a service deployment or user
acceptance of either character. In particular: neither finished Vera nor
Patrick mesh is supplied; the tested GLB is an older experimental candidate;
the Vera-slot model is generic/unverified; JACK is a partial word-trigram
model, not a fluent, identity-qualified neural person. World movements and
conversation history are browser/session-local, not durable world-memory.
Private source coverage, likeness, rights and final release remain on HOLD.
