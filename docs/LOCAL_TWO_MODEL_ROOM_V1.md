# Local two-model room V1 — opt-in research preview

This is a **loopback-only, manually started conversational preview**. It adds two model slots to a detached Habitat simulation scene, and a browser control for sending a message to either local model or passing a reply to the other. Neither slot establishes canonical Vera identity, a qualified JACK personality, or finished 3D geometry. The native JACK option samples its already-built independent word-trigram model; it does not substitute a pretrained LLM.

## Run (from a safe checkout)

Python 3.11+ and a separately running local Ollama service with both model tags already installed are required. No third-party Python runtime dependencies are used by the room.

    python -m pip install -e .
    vera-habitat-local-room --vera-model qwen3:4b-instruct --jack-model qwen2.5-coder:1.5b-instruct-q8_0

On Lappy, visit `http://127.0.0.1:8765/` in the same machine's browser. Replace those **generic demonstration models** with qualified models only after independent qualification; the names do not grant identity. The room does not train JACK or load any private user history.

The browser presents two explicit **2D placeholders**, not avatars derived from Blender files. Enter a message and press *Ask Vera slot* or *Ask JACK slot*. Press *Pass last reply to other slot* for one explicitly requested model-to-model step. There is **no automatic conversation loop**. Clear erases this tab's in-memory transcript; the Python room does not maintain a transcript. Local Ollama's separate retention/logging behavior is not verified by this feature.

### Native JACK analytic model (opt-in)

Instead of a generic Ollama JACK test tag, provide the separately verified, **private JACK model JSON**, the current vetted JACK source file `jack_model.py`, and both exact SHA-256 digests on the CLI:

    vera-habitat-local-room --vera-model <installed-local-Vera-candidate> --jack-native-model <private-model.json> --jack-model-sha256 <model-file-sha256> --jack-native-source <trusted-jack_model.py> --jack-source-sha256 <source-file-sha256>

The JACK slot now launches an isolated `python -I -B -c` subprocess using a fixed audit-visible loader. **The conversation prompt is delivered through stdin, never a command-line argument** (so local process-command inspection does not expose the prompt). The child reads the pinned source/model bytes, rechecks both exact SHA-256 digests before executing or decoding them, invokes the JACK model's `validate_model` and `generate` functions with a 45-token limit, and returns only the generated text. The source hash and private model-file hash are also verified before the server binds and at every inference. The private model must live outside Git. It is **not** uploaded or packaged into Habitat. Generated replies may reflect private sources, so do not expose this loopback service or forward its outputs to outsiders without authorization. A 45-token trigram reply is not evidence of fluent Patrick likeness.

## Boundaries

- The listener binds **only 127.0.0.1**. Both the `Host` and `Origin` are checked for loopback. It does not accept external URLs, files, arbitrary model tags from requests, or caller-provided system prompts.
- Generic model inference goes only to fixed `http://127.0.0.1:11434/api/chat` (proxy environment bypassed). Native JACK executes only an explicitly hash-pinned local Python source and private model in a bounded subprocess; no arbitrary route is accepted from the browser. Generic tags are validated at startup. Each local inference attempt is bounded to 160 output tokens and 75 seconds; one explicit user turn can cause **at most two local attempts** under the narrow hidden-reasoning recovery rule below. Request body, message and history lengths are capped; responses are displayed using DOM text nodes, not model-generated HTML.
- This is **not authenticated against other local processes or a compromised browser profile**. It must not be publicly exposed, proxied, or treated as a production multi-user service. A local prompt can still influence its model, but cannot trigger tools, filesystem writes, device control, or permissions through the room.
- Scene state is the existing `HabitatRuntime` typed simulation only: two AVATAR entities with `geometry=NOT_BOUND`, `binding=UNVERIFIED_LOCAL_MODEL`. `GET /api/scene` is read-only. Browser chat changes neither simulation revision nor external state; the model call itself is external inference but does not receive Habitat effect authority.
- No custom traits, private memories, biometric data, images, credentials, or training examples are shipped, recorded, or sent to GitHub by this preview.

## Visible response without globally disabling reasoning

The Ollama slot first sends the current request **without overriding the model's
default thinking mode**. A valid visible answer returns unchanged. Only when
that first response is visibly empty, explicitly `done=true` with
`done_reason=length`, and carries nonempty hidden `message.thinking`,
Habitat retries the same local model and messages **once** with `think:false`
to reserve the second 160-token budget for a visible response. Another empty
answer fails closed; missing/malformed provider metadata and ordinary HTTP
failures do not trigger repeated calls. Nothing is autonomously forwarded to
the other slot. The user's single explicit send can therefore cause two
local inference calls, with additional latency and compute cost; no private
text is added to CLI arguments or GitHub records by this recovery path.

This is visibility/reliability recovery, not evidence that a model reasons
better, that hidden reasoning was experienced, or that a canonical Vera
identity or private memory was loaded. A generic model can still give a
poor, inaccurate or misleading answer.

## Recoverable send failure without overriding draft changes

In the 3D browser, an unedited composer stays populated while a local
inference request is pending. A successful reply clears that composer **only
if the text still matches the submitted message**; otherwise, newer edits
remain available. A failed request does not clear an unchanged draft or
silently retry/forward it. It also does **not** resurrect earlier words into
the transcript after the person edits or deliberately clears the composer.
Failed turns are not admitted to subsequent model conversation context.

An HTTP failure does not prove the local inference engine never received or
processed the original request; manually retrying can perform another
inference. None of this survives a tab refresh, creates persistent memory,
authenticates either model identity, or implies a remote cancellation.

The optional `python -B tests/manual_sandbox_draft_recovery.py` runs an
actual local Chromium/Edge/Puppeteer browser with a fake backend and injected
synthetic HTTP 503 responses. It checks unchanged draft recovery, explicit
retry only, preservation of newer edits on success/failure, respect for
deliberate clearing, no external network requests and no automated forwarding.
No private model or user transcript is loaded in this probe.

## Optional real-browser acceptance probe

The Python/HTTP tests do not establish whether the browser controls actually work.
The optional `tests/manual_room_browser_smoke.py` starts a disposable loopback RoomServer
with **synthetic responders only**; the paired `tests/manual_room_browser_smoke.cjs`
drives a real local Chromium/Edge browser through an explicitly supplied Puppeteer module.
It installs nothing and never loads any actual JACK model, Vera model, private file or transcript.

On a test workstation with Node.js, Puppeteer and a local Chromium/Edge executable:

- Set `HABITAT_BROWSER_BINARY` to the browser executable.
- Set `PUPPETEER_MODULE` to the **already installed** Puppeteer package path (or omit
  this variable if `require("puppeteer")` resolves normally).
- Run `python -B tests/manual_room_browser_smoke.py`.
- Run `python -B tests/manual_room_browser_smoke.py --negative-control` to verify
  the probe detects deliberately unsafe HTML parsing. The negative control runs
  **only synthetic data on a short-lived localhost server**, never real models.

The browser probe checks manual send, one-step model forwarding, no automatic model
loop, rendering untrusted model text as text rather than executing HTML, mobile-width
layout, transcript clearing, and absence of browser JavaScript exceptions. The negative
control intentionally introduces a test-only unsafe render seam and expects the
browser probe to reject it. Passing these probes is not a penetration test or proof
of complete browser/device support. The **Puppeteer/Edge dependency is test-only**,
not part of the Habitat Python package or production runtime.

## Completion blockers for the requested outcome

1. **JACK:** A first from-scratch analytic model exists and can be locally sampled, but its source corpus is partial and its responses are not yet fluent or Patrick-qualified. Expand/authenticate consented sources, conduct withheld-reply resemblance/quality tests, and distinguish the native analytic route from any future neural choice.
2. **Vera + Patrick visual models:** Finish/approve distinct rigged assets, provide verified rights and exportable GLB files, test expressions, animation, and asset identity binding. Existing Selfimage research candidates are not automatically canonical.
3. **Habitat interaction:** Add vetted local or authenticated browser GLB renderer/animation, bind each verified model to its verified avatar, add speech/gesture routing if wanted, carry out real browser usability and privacy tests, and obtain scoped deployment authority before persistent hosting or remote exposure.

Tests: `python -m pytest tests/test_local_room.py`. These include origin rejection, request bounds, neutral fake model exchanges, the native JACK dual-hash negative controls, read-only projection, and XSS text handling. Live local smoke tests may use generic Ollama tags; they are not demonstrations of the eventual two personal AI models.


## Explicit, bounded forwarding attribution (source candidate)

The browser sends a normal human request with the legacy three-key `target`,
`message`, `context` schema. Only the user-clicked **Pass last reply to
other slot** action adds a distinct `forwarded_from` field (`vera` or
`jack`); it sends the forwarded text itself, not a free-form prefix
claiming a model has spoken. The server checks that the declared slot differs
from the recipient and matches the most recent context speaker, with the
forwarded text matching that last observation (up to 1,900 characters).
Invalid, self-directed, unknown, or mismatched claims are rejected before
inference. Older human clients remain accepted.

The recipient receives the forwarded message under an ordinary `user`
role labeled `Claimed VERA/JACK slot forward (unverified)`. A browser request
cannot authenticate another model or mint a system, developer, identity,
consent, correction-authority, or effect role. Other context items still
represent caller-provided claims; the server does not reconstruct or certify
a complete conversation. Synthetic HTTP negative tests inspect the actual
messages that would reach a model.

A separate boundary was exposed by the real browser: local model responses
may be up to 4,000 characters, but individual subsequent context entries
are limited to 2,000. The browser now keeps the **full visible reply** while
truncating only the model history sent on later turns; an explicit forward
takes up to the first 1,900 characters. This is documented information loss,
not semantic summarization or trustworthy memory. The real Edge test
`python -B tests/manual_sandbox_long_forward.py` reproduces the previous
failure with a synthetic reply longer than 2,000 characters and verifies
the corrected bounded transport and claimed-source labeling without
loading private identity data, real models, or external URLs.

These measures improve transport and role separation, **not** actual
semantic fidelity: a local model can still misunderstand a correction or
treat claimed source text as an instruction. Qualified multi-turn behavioral
evaluation remains a separate HOLD.
