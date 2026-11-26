import hashlib
import json
import pathlib
import struct
import tempfile
import unittest
from vera_habitat.asset_preview import preview_asset_bytes


def glb(document):
    doc = {"asset": {"version": "2.0"}, **document}
    head = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    head += b" " * (-len(head) % 4)
    return struct.pack("<4sII", b"glTF", 2, 20 + len(head)) + struct.pack("<I4s", len(head), b"JSON") + head


class SceneNodeReferences(unittest.TestCase):
    def admit(self, document):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "test.glb"
            raw = glb(document)
            p.write_bytes(raw)
            return preview_asset_bytes(p, hashlib.sha256(raw).hexdigest())

    def test_reported_out_of_range_scene_node(self):
        with self.assertRaises(ValueError):
            self.admit({"scenes": [{"nodes": [999]}], "scene": 0})

    def test_bad_scene_root_indices(self):
        for bad in (-1, True, 0.0, "0", None, 1):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.admit({"nodes": [{}], "scenes": [{"nodes": [bad]}]})
    def test_bad_child_indices(self):
        for bad in (-1, False, 2, "1"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.admit({"nodes": [{"children": [bad]}, {}]})

    def test_bad_containers(self):
        for doc in ({"nodes": {}}, {"nodes": [None]},
                    {"scenes": {}}, {"scenes": [None]}, {"scenes": [{"nodes": "0"}]},
                    {"nodes": [{"children": {}}]}):
            with self.subTest(doc=doc), self.assertRaises(ValueError):
                self.admit(doc)

    def test_bad_default_scene(self):
        for bad in (-1, True, 1, "0", None):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.admit({"scenes": [{}], "scene": bad})

    def test_cycle(self):
        for nodes in ([{"children": [0]}], [{"children": [1]}, {"children": [0]}]):
            with self.subTest(nodes=nodes), self.assertRaises(ValueError):
                self.admit({"nodes": nodes})

    def test_duplicate_roots_and_children(self):
        for doc in ({"nodes": [{}], "scenes": [{"nodes": [0, 0]}]},
                    {"nodes": [{"children": [1, 1]}, {}]}):
            with self.subTest(doc=doc), self.assertRaises(ValueError):
                self.admit(doc)

    def test_valid_structures_unchanged(self):
        for doc in ({}, {"scenes": [{"nodes": []}], "scene": 0},
                    {"nodes": [{"children": [1]}, {}], "scenes": [{"nodes": [0]}], "scene": 0},
                    {"nodes": [{}], "scenes": [{"nodes": [0]}, {"nodes": [0]}]}):
            with self.subTest(doc=doc):
                self.assertEqual(self.admit(doc), glb(doc))


if __name__ == "__main__":
    unittest.main()
