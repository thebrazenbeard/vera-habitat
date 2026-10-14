"""Contract for an externally governed checkpoint high-water mark.

No provider is installed here. A caller must supply a genuinely independent,
authenticated, durable, monotonic compare-and-swap service. Local files, hashes,
HMAC keys and advisory locks do not qualify as independent rollback authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AnchorHead:
    anchor_id: str
    sequence: int
    seal: str

    def __post_init__(self) -> None:
        if (type(self.anchor_id) is not str or not self.anchor_id.strip()
                or len(self.anchor_id) > 128):
            raise ValueError("invalid anchor_id")
        if type(self.sequence) is not int or self.sequence < 1:
            raise ValueError("invalid anchor sequence")
        if (type(self.seal) is not str or len(self.seal) != 64
                or any(c not in "0123456789abcdef" for c in self.seal)):
            raise ValueError("invalid anchor seal")


class TrustedAnchor(Protocol):
    """Caller-provisioned, independently protected CAS authority.

    read_head must fail (raise), never default to None, on transport errors.
    None means verified first-use state for the exact anchor_id, not outage.
    compare_and_advance must atomically compare and durably commit the head.
    False means no commit. A raised/ambiguous response requires fresh readback,
    not blind retry. It must never regress to a previous head.
    """

    def read_head(self) -> AnchorHead | None:
        ...

    def compare_and_advance(
        self, expected: AnchorHead | None, successor: AnchorHead
    ) -> bool:
        ...
