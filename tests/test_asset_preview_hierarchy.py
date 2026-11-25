import hashlib
import pathlib
import tempfile
import unittest
from test_asset_preview_scene_graph import glb
from vera_habitat.asset_preview import preview_asset_bytes


class SceneHierarchyAndObjectReferences(unittest.TestCase):
    def admit(self, document):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "sample.glb"
            raw = glb(document)
            path.write_bytes(raw)
            return preview_asset_bytes(path, hashlib.sha256(raw).hexdigest())

    def test_multiple_parents_rejected(self):
        with self.assertRaises(ValueError):
            self.admit({"nodes": [{"children": [2]}, {"children": [2]}, {}],
                        "scenes": [{"nodes": [0, 1]}]})

    def test_child_cannot_also_be_scene_root(self):
        for scenes in ([{"nodes": [0, 1]}], [{"nodes": [0]}, {"nodes": [1]}]):
            with self.subTest(scenes=scenes), self.assertRaises(ValueError):
                self.admit({"nodes": [{"children": [1]}, {}], "scenes": scenes})

    def test_invalid_mesh_and_skin_references(self):
        for key, array in (("mesh", "meshes"), ("skin", "skins")):
            for value in (1, -1, True, "0", 0.0, None):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.admit({"nodes": [{key: value}], array: [{}]})
            for missing in ({}, {array: {}}, {array: [None]}):
                with self.subTest(key=key, missing=missing), self.assertRaises(ValueError):
                    self.admit({"nodes": [{key: 0}], **missing})

    def test_valid_reference_bounds_and_shared_scene_roots(self):
        doc = {"nodes": [{"mesh": 0, "skin": 0, "children": [1]}, {}],
               "meshes": [{}], "skins": [{}],
               "scenes": [{"nodes": [0]}, {"nodes": [0]}]}
        self.assertEqual(self.admit(doc), glb(doc))


if __name__ == "__main__":
    unittest.main()
