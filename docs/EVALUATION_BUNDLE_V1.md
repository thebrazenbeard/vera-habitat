# Navigation evaluation replay bundle V1

Optional, simulation-only candidate. `NO_AUTO_BIND` is unchanged.

`python -m vera_habitat.navigation_eval --split holdout --episodes 4 --bundle`
prints a JSON bundle with `schema_version`, `report`, and a public SHA-256
fingerprint over canonical JSON of the report. Without `--bundle`, V1 output
is unchanged. The bundle does not write a file, contact a service or execute
a controller.

A verifier can read saved JSON text and call:

```python
from vera_habitat.eval_bundle import verify_evaluation_bundle
report = verify_evaluation_bundle(bundle_json_text)
```

Verification rejects duplicate JSON keys, malformed schemas, oversized input,
nonfinite values, changed report bytes, unrecognized seeds/splits and altered
metrics even if someone recomputes the *public* SHA-256. The verifier
reconstructs the expected restricted/privileged policy summary using the
**same installed simulation evaluator** and compares exact fields.

For resource bounds, bundling and replay require
`episodes * max_steps * number_of_policies <= 20000`. No remote provider,
independent test implementation, source attestation or authentication exists.
A forged hash and a modified evaluator can fabricate results; replay does
not prove unbiased holdouts, sim-to-real transfer or live Vera competence.
