"""Authoritative *simulation-only* world state.

No rendering, user identity, network, device, or external effects are authorized
by state transitions in this module.
"""
from __future__ import annotations

from dataclasses import replace

from .model import (
    ActionProposal, ActionReceipt, EffectClass, Entity, Position3, SceneSnapshot,
    _require_utf8,
)


class HabitatRuntime:
    SCHEMA_VERSION = "VERA_HABITAT_SCENE_V1"

    def __init__(self) -> None:
        self._revision = 0
        self._entities: dict[str, Entity] = {}
        self._receipts: list[ActionReceipt] = []
        self._seen_action_ids: set[str] = set()

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def receipts(self) -> tuple[ActionReceipt, ...]:
        return tuple(self._receipts)

    def spawn(self, entity: Entity) -> ActionReceipt:
        if not isinstance(entity, Entity) or not isinstance(entity.position, Position3):
            raise ValueError("spawn requires an Entity with a valid Position3")
        if any(type(k) is not str or type(v) is not str
               for k, v in entity.metadata.items()):
            raise ValueError("entity metadata must contain text keys and values")
        before = self._revision
        if entity.entity_id in self._entities:
            receipt = ActionReceipt(
                action_id=f"spawn:{entity.entity_id}",
                accepted=False,
                disposition="DUPLICATE_ENTITY_REJECTED",
                revision_before=before,
                revision_after=before,
            )
            self._receipts.append(receipt)
            return receipt

        self._entities[entity.entity_id] = entity
        self._revision += 1
        receipt = ActionReceipt(
            action_id=f"spawn:{entity.entity_id}",
            accepted=True,
            disposition="SIMULATION_ENTITY_SPAWNED",
            revision_before=before,
            revision_after=self._revision,
        )
        self._receipts.append(receipt)
        return receipt

    def propose(self, proposal: ActionProposal) -> ActionReceipt:
        if not isinstance(proposal, ActionProposal):
            raise ValueError("only typed ActionProposal records are accepted")
        if type(proposal.action_id) is not str or not proposal.action_id.strip():
            raise ValueError("proposal requires a nonempty text action_id")
        _require_utf8(proposal.action_id, "action_id")

        before = self._revision
        if proposal.action_id in self._seen_action_ids:
            return self._reject(proposal, "DUPLICATE_ACTION_ID", before)
        self._seen_action_ids.add(proposal.action_id)

        if (type(proposal.entity_id) is not str or not proposal.entity_id.strip()
                or type(proposal.action) is not str
                or (proposal.target_position is not None
                    and not isinstance(proposal.target_position, Position3))):
            return self._reject(proposal, "INVALID_PROPOSAL", before)

        if proposal.effect_class is not EffectClass.SIMULATION_ONLY:
            return self._reject(proposal, "EXTERNAL_EFFECT_UNAVAILABLE", before)

        if proposal.action != "MOVE_ENTITY" or proposal.target_position is None:
            return self._reject(proposal, "UNSUPPORTED_ACTION", before)

        current = self._entities.get(proposal.entity_id)
        if current is None:
            return self._reject(proposal, "UNKNOWN_ENTITY", before)

        self._entities[proposal.entity_id] = replace(
            current,
            position=proposal.target_position,
        )
        self._revision += 1
        receipt = ActionReceipt(
            action_id=proposal.action_id,
            accepted=True,
            disposition="SIMULATION_MOVE_APPLIED",
            revision_before=before,
            revision_after=self._revision,
        )
        self._receipts.append(receipt)
        return receipt

    def snapshot(self) -> SceneSnapshot:
        return SceneSnapshot(
            schema_version=self.SCHEMA_VERSION,
            revision=self._revision,
            entities=tuple(sorted(self._entities.values(), key=lambda item: item.entity_id)),
        )

    def export_checkpoint(self) -> str:
        """Portable integrity-bound JSON; does NOT prove a trusted author."""
        from .checkpoint import dump_checkpoint
        return dump_checkpoint(self.snapshot(), self.receipts,
                               frozenset(self._seen_action_ids))

    @classmethod
    def from_checkpoint(cls, encoded: str) -> "HabitatRuntime":
        """Reconstruct isolated V1 scene and replay guard; never bind a runtime."""
        from .checkpoint import load_checkpoint
        revision, entities, receipts, seen = load_checkpoint(encoded)
        instance = cls()
        instance._revision = revision
        instance._entities = entities
        instance._receipts = receipts
        instance._seen_action_ids = seen
        return instance

    def _reject(self, proposal: ActionProposal, disposition: str,
                before: int) -> ActionReceipt:
        receipt = ActionReceipt(
            action_id=proposal.action_id,
            accepted=False,
            disposition=disposition,
            revision_before=before,
            revision_after=before,
        )
        self._receipts.append(receipt)
        return receipt
