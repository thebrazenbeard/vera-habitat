"""Source-only Clearing assertions; no GPU, provider or external effect."""
import json
import unittest
from math import isclose

from vera_habitat.clearing import make_clearing, run_prediction_trial
from vera_habitat.model import ActionProposal, EffectClass, Position3
from vera_habitat.rendering import render_scene_json
from vera_habitat.runtime import HabitatRuntime


class TestClearing(unittest.TestCase):
    def test_scene_is_deterministic_and_small(self):
        a, b = make_clearing(), make_clearing()
        self.assertEqual(a.snapshot(), b.snapshot())
        self.assertEqual(len(a.snapshot().entities), 9)
        self.assertEqual(a.revision, 9)
        self.assertEqual(
            {entity.zone for entity in a.snapshot().entities},
            {"workshop", "threshold", "clearing"},
        )
        self.assertEqual(a.receipts, b.receipts)

    def test_checkpoint_restores_exact_world_and_receipts(self):
        world = make_clearing()
        restored = HabitatRuntime.from_checkpoint(world.export_checkpoint())
        self.assertEqual(restored.snapshot(), world.snapshot())
        self.assertEqual(restored.receipts, world.receipts)
        self.assertEqual(restored.export_checkpoint(), world.export_checkpoint())

    def test_correct_prediction_has_zero_error(self):
        world = make_clearing()
        target = Position3(3.0, 2.0, 0.0)
        t = run_prediction_trial(
            world, action_id="walk-1", entity_id="avatar",
            target=target, predicted=target,
        )
        self.assertTrue(t.accepted)
        self.assertEqual(t.disposition, "SIMULATION_MOVE_APPLIED")
        self.assertEqual((t.revision_before, t.revision_after), (9, 10))
        self.assertEqual(t.observed, target)
        self.assertEqual(t.error_m, 0.0)
        self.assertEqual(len(t.snapshot_sha256), 64)

    def test_wrong_prediction_is_measurable(self):
        world = make_clearing()
        t = run_prediction_trial(
            world, action_id="walk-2", entity_id="avatar",
            target=Position3(3.0, 2.0, 0.0),
            predicted=Position3(4.0, 2.0, 0.0),
        )
        self.assertTrue(isclose(t.error_m, 1.0))

    def test_duplicate_action_does_not_reposition_again(self):
        world = make_clearing()
        old = Position3(3.0, 2.0, 0.0)
        first = run_prediction_trial(world, action_id="same", entity_id="avatar",
                                     target=old, predicted=old)
        replay = run_prediction_trial(
            world, action_id="same", entity_id="avatar",
            target=Position3(8.0, 8.0, 0.0), predicted=old,
        )
        self.assertTrue(first.accepted)
        self.assertFalse(replay.accepted)
        self.assertEqual(replay.disposition, "DUPLICATE_ACTION_ID")
        self.assertEqual(replay.observed, old)
        self.assertEqual(replay.revision_before, replay.revision_after)

    def test_unknown_entity_fails_without_side_effect(self):
        world = make_clearing()
        before = world.export_checkpoint()
        with self.assertRaisesRegex(ValueError, "unknown Clearing entity"):
            run_prediction_trial(
                world, action_id="unknown", entity_id="missing",
                target=Position3(1, 1, 0), predicted=Position3(1, 1, 0),
            )
        self.assertEqual(world.export_checkpoint(), before)

    def test_read_only_projection_is_detached(self):
        world = make_clearing()
        snapshot = world.snapshot()
        projection = json.loads(render_scene_json(snapshot))
        self.assertEqual(projection["authority"], "READ_ONLY_PROJECTION")
        projection["entities"][0]["position"]["x"] = 999.0
        self.assertEqual(snapshot, world.snapshot())
        self.assertEqual(world.revision, 9)

    def test_external_effect_proposals_remain_rejected(self):
        world = make_clearing()
        receipt = world.propose(ActionProposal(
            action_id="external", effect_class=EffectClass.EXTERNAL_REQUEST,
            action="MOVE_ENTITY", entity_id="avatar",
            target_position=Position3(10, 10, 0),
        ))
        self.assertFalse(receipt.accepted)
        self.assertEqual(receipt.disposition, "EXTERNAL_EFFECT_UNAVAILABLE")
        self.assertEqual(world.revision, 9)

    def test_v0_is_explicitly_not_collision_physics(self):
        world = make_clearing()
        # A reposition can overlap a workbench: no physical collision model.
        t = run_prediction_trial(
            world, action_id="teleport", entity_id="avatar",
            target=Position3(4.0, 2.0, 0.0),
            predicted=Position3(4.0, 2.0, 0.0),
        )
        self.assertTrue(t.accepted)
        self.assertEqual(t.observed, Position3(4.0, 2.0, 0.0))


if __name__ == "__main__":
    unittest.main()
