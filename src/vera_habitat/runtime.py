from __future__ import annotations

from dataclasses import replace

from .model import ActionProposal, ActionReceipt, EffectClass, Entity, SceneSnapshot


class HabitatRuntime:
    SCHEMA_VERSION = "VERA_HABITAT_SCENE_V1"

    def __init__(self) -> None:
        self._revision = 0
        self._entities: dict[str, Entity] = {}
        self._receipts: list[ActionReceipt] = []

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def receipts(self) -> tuple[ActionReceipt, ...]:
        return tuple(self._receipts)

    def spawn(self, entity: Entity) -> ActionReceipt:
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
        before = self._revision

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

    def _reject(self, proposal: ActionProposal, disposition: str, before: int) -> ActionReceipt:
        receipt = ActionReceipt(
            action_id=proposal.action_id,
            accepted=False,
            disposition=disposition,
            revision_before=before,
            revision_after=before,
        )
        self._receipts.append(receipt)
        return receipt
