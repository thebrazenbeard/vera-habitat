# Trusted anti-rollback checkpoint contract V1

**Status:** Source-only optional interface; NO_AUTO_BIND. No anchor deployed.

The caller may supply `TrustedAnchor` and a durable `anchor_id` when creating
`AuthenticatedFileStore`. `AnchorHead(anchor_id, sequence, seal)` is the
independently trusted high-water mark for one checkpoint stream. The provider
MUST authenticate reads and writers, keep monotonic state on a separate
rollback domain from the local file and key, and implement linearizable,
durable `compare_and_advance(expected, successor)` compare-and-swap.
`read_head()` returning None means verifiably empty first-use state, **not**
an outage. Errors must propagate. A file, backup, hash, HMAC, lock or database
subject to the same rollback attack is NOT a trusted anchor.

Example (provider separately supplied and audited):
```python
store = AuthenticatedFileStore(
    "/private/world/checkpoint.json", key, writer_id="operator",
    anchor=trusted_anchor, anchor_id="habitat/world-a",
)
restored = store.load()
next_checkpoint = store.save(world, expected_seal=restored.seal)
```

On save, a local cooperating-writer lock protects predecessor validation;
the signed checkpoint is written and fsynced to a temporary file; only then
does the external authority CAS its high-water mark forward. On confirmed
CAS success, the temporary file replaces the old checkpoint. On load, the
verified local MAC/sequence must exactly equal the external head.

**Failure semantics:** An outage, mismatch, malformed head, CAS rejection or
ambiguous transport response fails closed. If the process crashes AFTER anchor
CAS but BEFORE local replace, the old file is stale and must not be loaded.
The package intentionally has no automatic reconciliation, anchor reversal,
distributed transaction or recovery authority. Any repair requires independently
governed review of the durable anchor state and previously staged/backup data.
Absent an anchor the old local-only semantics and rollback exposure remain.

The tests use an in-memory fake, **not** a trusted backend. No deployed provider,
durability, linearizability, key management, recovery, security audit, installation
or production binding has been established.
