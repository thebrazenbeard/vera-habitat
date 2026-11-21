# Local two-model room V1 — opt-in research preview

This is a **loopback-only, manually started conversational preview**. It adds two model slots to a detached Habitat simulation scene, and a browser control for sending a message to either local model or passing a reply to the other. Neither slot establishes canonical Vera identity, a trained JACK personality, or finished 3D geometry.

## Run (from a safe checkout)

Python 3.11+ and a separately running local Ollama service with both model tags already installed are required. No third-party Python runtime dependencies are used by the room.

    python -m pip install -e .
    vera-habitat-local-room --vera-model qwen3:4b-instruct --jack-model qwen2.5-coder:1.5b-instruct-q8_0

On Lappy, visit `http://127.0.0.1:8765/` in the same machine's browser. Replace those **generic demonstration models** with qualified models only after independent qualification; the names do not grant identity. The room does not train JACK or load any private user history.

The browser presents two explicit **2D placeholders**, not avatars derived from Blender files. Enter a message and press *Ask Vera slot* or *Ask JACK slot*. Press *Pass last reply to other slot* for one explicitly requested model-to-model step. There is **no automatic conversation loop**. Clear erases this tab's in-memory transcript; the Python room does not maintain a transcript. Local Ollama's separate retention/logging behavior is not verified by this feature.

## Boundaries

- The listener binds **only 127.0.0.1**. Both the `Host` and `Origin` are checked for loopback. It does not accept external URLs, files, arbitrary model tags from requests, or caller-provided system prompts.
- The only outgoing request is to fixed `http://127.0.0.1:11434/api/chat`; configured model tags are validated at startup. Each inference is bounded to 160 output tokens and 75 seconds. Request body, message and history lengths are capped; responses are displayed using DOM text nodes, not model-generated HTML.
- This is **not authenticated against other local processes or a compromised browser profile**. It must not be publicly exposed, proxied, or treated as a production multi-user service. A local prompt can still influence its model, but cannot trigger tools, filesystem writes, device control, or permissions through the room.
- Scene state is the existing `HabitatRuntime` typed simulation only: two AVATAR entities with `geometry=NOT_BOUND`, `binding=UNVERIFIED_LOCAL_MODEL`. `GET /api/scene` is read-only. Browser chat changes neither simulation revision nor external state; the model call itself is external inference but does not receive Habitat effect authority.
- No custom traits, private memories, biometric data, images, credentials, or training examples are shipped, recorded, or sent to GitHub by this preview.

## Completion blockers for the requested outcome

1. **JACK:** Establish a private, user-reviewed source corpus, scoped consent/rights, base-model choice, training/evaluation controls, real persona-fidelity tests, and a runnable qualified model tag. The public `jack` README alone is not a model.
2. **Vera + Patrick visual models:** Finish/approve distinct rigged assets, provide verified rights and exportable GLB files, test expressions, animation, and asset identity binding. Existing Selfimage research candidates are not automatically canonical.
3. **Habitat interaction:** Add vetted local or authenticated browser GLB renderer/animation, bind each verified model to its verified avatar, add speech/gesture routing if wanted, carry out real browser usability and privacy tests, and obtain scoped deployment authority before persistent hosting or remote exposure.

Tests: `python -m pytest tests/test_local_room.py`. These include origin rejection, request bounds, neutral fake model exchanges, read-only projection, and XSS text handling. Live local smoke tests may use generic Ollama tags; they are not demonstrations of the eventual two personal AI models.
