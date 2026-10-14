# Vera Habitat local authenticated recovery V1

## Scope and evidence ceiling

This is an **opt-in local file facility**, not a Vera runtime installation,
persistence service, LAN route, virtual embodiment, autonomous agency, or
permission to operate a physical device. The simulated world is authoritative
only for its own in-memory state. Importing `vera_habitat.persistence` opens
no files, sets no environment variables, and starts no process.

The checkpoint format from Habitat V2 is still used unchanged, but it is
wrapped in an HMAC-SHA256-authenticated local file envelope.

`VERA_HABITAT_LOCAL_AUTHENTICATED_FILE_V1` contains:
- `schema`: fixed versioned envelope identifier
- `writer_id`: a caller-supplied label, MAC-bound (not an identity proof)
- `sequence`: local sequential save count
- `parent_seal`: previous envelope MAC, or null for the initial generation
- `checkpoint`: serialized V2 world/receipts/replay guard JSON
- `mac`: HMAC-SHA256 of canonical JSON over the other five fields

The **key is never serialized** and must be supplied independently at every
process startup. A minimum 32-byte secret is required. Anyone holding the key
can forge valid envelopes and writer labels; its secrecy is a system
precondition. Checkpoint validation runs **after** MAC authentication.

## Minimal explicit usage

```python
import os
from pathlib import Path
from vera_habitat import (
    AuthenticatedFileStore, HabitatRuntime, Entity, Position3,
)

# Provision a private key externally; never commit, print or log it.
# Expected format: 64 hexadecimal characters, 32 bytes.
key = bytes.fromhex(os.environ["HABITAT_LOCAL_RECOVERY_KEY_HEX"])

# Only for a trusted existing local folder with one active writer.
store = AuthenticatedFileStore(
    Path("C:/HabitatPrivate/checkpoint.sealed.json"),
    key,
    writer_id="isolated-local-operator",
)

world = HabitatRuntime()
world.spawn(Entity("vera", "AVATAR", "room", Position3(0, 0, 0)))
first = store.save(world)  # the only point where new file I/O occurs

restored = store.load()  # authenticates and creates a new isolated world
# After explicitly modifying restored.runtime through simulation-only actions:
second = store.save(restored.runtime, expected_seal=restored.seal)
assert second.parent_seal == first.seal
```

The caller must create and secure the private directory and keep its
authentication key available for future recovery. Use an external secret
store and tested backup/restore procedure. Failure to retain the key means the
checkpoint cannot be authenticated with a new key.

## Guarantees, threat model and disclaimed capabilities

- Reads reject a wrong key, bad MAC, malformed envelope, duplicate JSON
  object keys, unsupported schema, oversized input, or invalid nested world
  checkpoint. The on-disk payload is capped at 2 MiB.
- A recomputed **public SHA-256 checkpoint fingerprint** does not bypass
  the keyed HMAC. MAC comparisons use constant-time equality.
- Sequential save metadata carries the previous MAC; the caller must provide
  `expected_seal` for a later generation. The store validates the existing
  signed file before any attempted overwrite and requires the new receipt
  history to extend the authenticated earlier history with at least one new
  receipt (which may be rejected without incrementing the scene revision).
  This guards against accidental divergent saves, **not** authorized-key
  forgery or replacement by an older valid signed file.
- Explicit saves acquire an advisory cross-process OS lock on a persistent
  `checkpoint.sealed.json.lock` sidecar before inspecting the existing file.
  Lock acquisition is bounded by a configurable `lock_timeout_seconds`
  (default 2 seconds; range 0..30) and raises `TimeoutError` if busy.
  Windows byte-range locks and POSIX `flock` coordinate cooperating local
  writers; the sidecar **must not be deleted** because that permits two
  processes to lock different underlying files. Readers can still load an
  atomically replaced authenticated file without acquiring a write lock.
- New bytes are written into a temporary file in the same directory,
  flushed and `fsync`-ed, then installed using `os.replace`. An exception
  during replacement leaves the preexisting file unchanged in tested fault
  injection; temporary files are cleaned up on ordinary exceptions.
- The returned save record holds an independently reconstructed world
  snapshot, so changing the original live world does not mutate that record.
- The store rejects a symlink at the target path; it requires an existing
  trusted parent directory and does not make directories implicitly.

**Limits that must not be overstated:**

1. An attacker who can restore a *previously valid signed file* can perform a
   rollback. The parent MAC and sequence do **not** prevent this without an
   independently trusted monotonic high-water mark. Such an external anchor
   does not exist in this package.
2. The lock prevents the check/replace race for **cooperating processes on
   the same locally supported filesystem and stable sidecar path**; this is
   not a distributed or network-filesystem compare-and-swap and does not
   prevent a hostile/uncooperative writer from bypassing the lock. Trusted
   directory control, protected lock-file permissions and filesystem
   capabilities remain essential.
3. Atomic file replacement and file `fsync` do not provide universal
   directory crash-durability guarantees on all filesystems, especially
   Windows/network-mounted filesystems. Use independent backups and recovery
   drills before operational reliance.
4. A tampered key, compromised host, deliberate sidecar removal/replacement,
   trusted-path symlink-swap race,
   manipulated OS, or malicious authorized writer remains out of scope.
5. Nothing authenticates Git commit provenance, assigns Vera's identity,
   persists autobiographical memory, confirms actual external effects, or
   establishes which Vera runtime is current. This format authenticates
   *local sealed data under a supplied symmetric secret*, nothing more.

## Verification gates

- Unit tests demonstrate wrong-key/tamper rejection, valid restore,
  sequential predecessor checking, no automatic files on construction,
  malformed-data rejection, injected replacement failure recovery, and
  separation of saved snapshots from live mutable state.
- GitHub Python 3.11/3.12/3.13 matrix qualifies source tests only.
- Merging, installing to canonical Vera, enabling runtime routes, granting
  permissions, rotating secrets, and cross-process locking remain separately
  gated effects. This PR is expected to remain a draft candidate until review.
