"""A spatial view uses scene *copies*, not physics or rendering authority."""
from random import Random

import pytest

from vera_habitat import Entity, HabitatRuntime, Position3
from vera_habitat.spatial import AABB3, SpatialProjection, brute_force_candidates
from vera_habitat.rendering import render_scene_json


def world():
    w = HabitatRuntime()
    for name, zone in (("a", "room"), ("b", "room"),
                       ("c", "room"), ("d", "outside")):
        w.spawn(Entity(name, "OBJECT", zone, Position3(0, 0, 0)))
    return w


def test_3d_candidates_include_touching_and_ignore_just_xy_overlap():
    snapshot = world().snapshot()
    boxes = [
        AABB3("a", "room", Position3(0, 0, 0), Position3(1, 1, 1)),
        AABB3("b", "room", Position3(1, .2, .2), Position3(2, .8, .8)),
        AABB3("c", "room", Position3(0, 0, 10), Position3(1, 1, 11)),
        AABB3("d", "outside", Position3(0, 0, 0), Position3(1, 1, 1)),
    ]
    projection = SpatialProjection.from_scene(snapshot, boxes)
    assert projection.revision == snapshot.revision
    assert projection.candidate_pairs() == (("a", "b"),)
    assert projection.candidate_pairs() == brute_force_candidates(boxes)
    assert projection.candidate_pairs() == SpatialProjection.from_scene(
        snapshot, list(reversed(boxes))).candidate_pairs()
    assert snapshot.revision == world().snapshot().revision


def test_randomized_sweep_matches_independent_quadratic_reference():
    rng = Random(123)
    names = [f"e{i:03d}" for i in range(100)]
    w = HabitatRuntime()
    boxes = []
    for i, name in enumerate(names):
        zone = "room1" if i % 2 else "room2"
        w.spawn(Entity(name, "OBJECT", zone, Position3(0, 0, 0)))
        xyz = [rng.uniform(-3, 3) for _ in range(3)]
        size = [rng.uniform(.01, 2) for _ in range(3)]
        boxes.append(AABB3(name, zone, Position3(*xyz),
                           Position3(*(xyz[j] + size[j] for j in range(3)))))
    assert SpatialProjection.from_scene(w.snapshot(), boxes).candidate_pairs() == (
        brute_force_candidates(boxes)
    )


@pytest.mark.parametrize("boxes", [
    [AABB3("missing", "room", Position3(0, 0, 0), Position3(1, 1, 1))],
    [AABB3("a", "wrong-zone", Position3(0, 0, 0), Position3(1, 1, 1))],
    [AABB3("a", "room", Position3(0, 0, 0), Position3(1, 1, 1)),
     AABB3("a", "room", Position3(0, 0, 0), Position3(1, 1, 1))],
])
def test_invalid_scene_bindings_fail_closed(boxes):
    with pytest.raises(ValueError):
        SpatialProjection.from_scene(world().snapshot(), boxes)


def test_invalid_3d_bounds_are_rejected():
    with pytest.raises(ValueError):
        AABB3("a", "room", Position3(2, 0, 0), Position3(1, 1, 1))
    with pytest.raises(ValueError):
        AABB3("a", "room", Position3(0, 0, 0), "wrong-type")


def test_renderer_serialization_is_deterministic_and_disposable():
    import json
    w = world()
    p1 = render_scene_json(w.snapshot())
    p2 = render_scene_json(w.snapshot())
    assert p1 == p2
    data = json.loads(p1)
    assert data["schema_version"] == "VERA_HABITAT_RENDER_V1"
    assert data["world_revision"] == w.revision
    assert [e["entity_id"] for e in data["entities"]] == ["a", "b", "c", "d"]
    assert data["authority"] == "READ_ONLY_PROJECTION"
    data["entities"][0]["position"]["x"] = 900
    assert w.snapshot().entities[0].position.x == 0
