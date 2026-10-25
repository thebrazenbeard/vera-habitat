"""Independent shadow-contract checks for optional Physica candidates.

Habitat's historical narrow predicate uses binary64 slab arithmetic, whereas
modern Physica evaluates translated AABB envelopes as exact rational numbers.
The latter must conservatively include every collision candidate identified by
the former, even where independently rounded expressions disagree by an ulp.

These are collision *candidate* checks, not physical contact qualification.
"""

from math import nextafter, inf
from random import Random

import pytest

pytest.importorskip("physica.spatial")

from vera_habitat.physica_adapter import PhysicaCandidates
from vera_habitat.training_ground import (
    NeutralTrainingGround, Obstacle2, TrainingAction, _swept_aabb_hit,
)


def _assert_no_shadow_false_negative(start, end, wall, radius):
    oracle_hit = _swept_aabb_hit(start, end, wall, radius)
    candidates = PhysicaCandidates((wall,)).candidates(start, end, radius)
    if oracle_hit:
        assert wall.entity_id in candidates, (
            "Physica under-approximated Habitat's finite-precision swept "
            f"candidate: {start=}, {end=}, {wall=}, {radius=}"
        )


@pytest.mark.parametrize("scale", [1e-8, 1e-4, 0.1, 1, 10, 1e4, 1e8])
def test_nominal_roundoff_touch_scales_must_remain_candidates(scale):
    wall = Obstacle2("wall", .9 * scale, 0, 1.1 * scale, scale)
    _assert_no_shadow_false_negative(
        (.2 * scale, .5 * scale), (.7 * scale, .5 * scale),
        wall, .2 * scale,
    )


def test_far_apart_finite_magnitudes_preserve_endpoint_candidate():
    # Exact real (start + rounded displacement) need not equal the original
    # endpoint. Here that discrepancy is tiny relative to a wall coordinate,
    # but Habitat's float slab arithmetic rounds the wall margin to 1e300.
    wall = Obstacle2("wall", 1e300, 0, nextafter(1e300, inf), 1)
    _assert_no_shadow_false_negative((-1.0, .5), (1e300, .5), wall, .1)


def test_decreasing_from_huge_start_to_small_end_is_conservative():
    # With a huge start and small destination, rounding end-start to binary64
    # can discard the entire destination. Moving the rounded delta one ulp
    # *toward* the exact result can leave the swept point ~1e284 short.
    wall = Obstacle2("wall", 0, 0, .2, 1)
    _assert_no_shadow_false_negative((1e300, .5), (.1, .5), wall, .05)


def test_floating_slab_quotient_can_round_a_near_miss_to_touch():
    # The Habitat slab divides two separately rounded large differences.
    # At the t=1 boundary this can round a very small spatial gap to a hit;
    # candidate broad-phase must still honor the established shadow policy.
    wall = Obstacle2("wall", 6.374894053336331e30, 0, 7e30, 1)
    _assert_no_shadow_false_negative(
        (-1.1151920278115158e31, .5),
        (1.7101638693177853e30, .5), wall,
        4.664730184018545e30,
    )


def test_roundoff_near_wall_does_not_break_replay_or_mutate_runtime():
    options = dict(
        width_m=5, height_m=5, radius_m=.2, start=(.2, .5),
        goal=(4, 4), obstacles=(Obstacle2("wall", .9, 0, 1.1, 1),),
    )
    normal = NeutralTrainingGround(collision_backend="habitat", **options)
    shadow = NeutralTrainingGround(collision_backend="physica", **options)
    action = TrainingAction("MOVE", 1.0, 0.0, 500)
    expected = normal.step(action)
    actual = shadow.step(action)
    assert (actual.accepted, actual.disposition, actual.observation) == (
        expected.accepted, expected.disposition, expected.observation,
    )


def test_seeded_sweep_shadow_parity_at_binary64_boundaries():
    rng = Random(0xB011D)
    observed_hits = 0
    for _ in range(500):
        radius = rng.choice((.1, .2, .3, .5))
        sx, sy = rng.uniform(-1, 1), rng.uniform(-1, 1)
        ex, ey = rng.uniform(-1, 1), rng.uniform(-1, 1)
        # Mix ordinary overlap with boundaries constructed from independently
        # rounded terms; a static broad-phase must be conservative for both.
        low_x = ex + radius if rng.randrange(2) else ex - radius
        low_y = ey + radius if rng.randrange(2) else ey - radius
        wall = Obstacle2("wall", low_x, low_y, low_x + 1, low_y + 1)
        start, end = (sx, sy), (ex, ey)
        observed_hits += _swept_aabb_hit(start, end, wall, radius)
        _assert_no_shadow_false_negative(start, end, wall, radius)
    assert observed_hits > 20
