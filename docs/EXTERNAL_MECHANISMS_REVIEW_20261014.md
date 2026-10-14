# External mechanism research — 2026-10-14

Inspection subjects are immutable GitHub tree objects, not package qualifications.
No upstream source copied and no new third-party runtime dependencies admitted.

- **SandboxEngine**, tree `292978297541ebea2b1dc9aa8627c70e18b1cfe5`:
  C++ OpenGL/GLFW/ImGui octree/chunk prototype. No root LICENSE observed.
  Renderer-specific application loop is unsuitable for authoritative deterministic
  stepping; use conceptual spatial partitioning only, not code.
- **replit-archive/jsrepl**, tree `36d79b6288ca5d26208e8bade2a168c6ebcb2376`:
  Archived browser Worker/iframe polyglot REPL with dynamic message routing.
  No verified license grant for reuse; browser sandbox is not OS isolation.
  Reject as untrusted executable substrate.
- **SCTY-Inc/mirofish-cli**, tree `6f8cc654b3204e20ff6ae4faf5606479ed8978d0`:
  AGPL-3.0; multi-agent LLM scenario engine with OASIS/CAMEL dependencies,
  run manifests and machine-readable verdict artifacts. Borrow conceptual
  independent evaluation manifests, not framework code or nondeterministic LLMs.
- **pypa/virtualenv**, tree `7dae9874f0a72629bb33ad28d7b34756a74db9eb`:
  MIT; discover/create/seed/activate plugins. Appropriate for developer Python
  dependency separation but NOT adversarial process isolation; no new dependency.
- **isaacs/nave**, tree `4b13fa8029ffe7749f4f708ad548f3b56a79bd43`:
  Blue Oak; shell/Node version selection, not a sandbox. Reject for Python core.
- **ekalinin/nodeenv**, tree `ecb4b7437098dc037df383a50e2f72cbfb4e4494`:
  BSD-style 3-clause LICENSE; Node environment provisioning + optional Python
  virtualenv integration. Redundant before a justified Node runner exists.
- **TanvirHossain2/NEXTVM**, tree `f581a6642596db396a6fe606addd735979403b6b`:
  Apache-2.0 Android Binder/ActivityThread/native-hook virtualization prototype.
  Not a proven OS security/VM boundary. Reject hooks/identity spoofing.

Separation: simulation != rendering; dependency environment != OS isolation;
language worker != hypervisor; social scenario simulation != reproducible
independent evaluation. The adopted mechanism is an original narrow trusted
anchor *interface*, not an upstream component or a deployed authority.
