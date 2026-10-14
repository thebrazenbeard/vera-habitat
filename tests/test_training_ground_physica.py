"""Optional independent broad-phase comparison against Physica V0.3.

The test skips when Physica is not installed: it is a research aid, not a
mandatory runtime dependency and not physical collision validation.
"""
from random import Random

import pytest

physica_spatial = pytest.importorskip("physica.spatial")
from vera_habitat.training_ground import Obstacle2, _swept_aabb_hit


def test_physica_broad_phase_never_misses_synthetic_segment_candidate():
    AABB = physica_spatial.AABB
    broad_phase_pairs = physica_spatial.broad_phase_pairs
    rng = Random(108)
    box = Obstacle2("wall", 4, 2, 6, 7)
    wall = AABB("wall", (box.left, box.bottom), (box.right, box.top))
    seen_contacts = 0
    broad_only = 0
    for _ in range(500):
        start = (rng.uniform(0, 10), rng.uniform(0, 10))
        end = (rng.uniform(0, 10), rng.uniform(0, 10))
        radius = 0.2
        swept = AABB(
            "motion",
            (min(start[0], end[0]) - radius, min(start[1], end[1]) - radius),
            (max(start[0], end[0]) + radius, max(start[1], end[1]) + radius),
        )
        broad = ("motion", "wall") in broad_phase_pairs((swept, wall))
        narrow_candidate = _swept_aabb_hit(start, end, box, radius)
        if narrow_candidate:
            seen_contacts += 1
            assert broad, "candidate escaped Physica broad-phase envelope"
        elif broad:
            broad_only += 1
    assert seen_contacts > 0
    assert broad_only > 0  # broad-phase candidates are not actual contacts
