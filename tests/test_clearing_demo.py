"""The Clearing has a deterministic, no-side-effect CLI receipt."""
import contextlib
import io
import json
import unittest

from vera_habitat.clearing_demo import main


class TestClearingDemo(unittest.TestCase):
    def _receipt(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertIsNone(main())
        return output.getvalue()

    def test_headless_receipt_reproducible(self):
        first = self._receipt()
        self.assertEqual(first, self._receipt())
        receipt = json.loads(first)
        self.assertEqual(receipt["authority"], "SIMULATION_ONLY")
        self.assertFalse(receipt["physics_qualified"])
        self.assertEqual(receipt["schema"], "VERA_CLEARING_HEADLESS_TRIAL_V0")
        self.assertEqual(len(receipt["scene"]["entities"]), 9)
        self.assertEqual(receipt["scene"]["authority"], "READ_ONLY_PROJECTION")
        self.assertEqual(receipt["trial"]["error_m"], 0.0)
        self.assertTrue(receipt["trial"]["accepted"])
        self.assertEqual(receipt["trial"]["revision_before"], 9)
        self.assertEqual(receipt["trial"]["revision_after"], 10)


if __name__ == "__main__":
    unittest.main()
