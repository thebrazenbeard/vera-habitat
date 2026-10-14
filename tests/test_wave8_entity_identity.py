import unittest
from vera_habitat.model import Entity, Position3

class IdentityTypeTests(unittest.TestCase):
    def test_entity_id_exact_string(self):
        for invalid in (None, True, 12):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                Entity(invalid, "avatar", "zone-a", Position3(0.0,0.0,0.0))
