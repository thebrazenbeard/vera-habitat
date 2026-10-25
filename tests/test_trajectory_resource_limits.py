"""Adversarial bounded-consumption checks for external trajectory previews."""

from types import SimpleNamespace

import pytest

from vera_habitat.trajectory import preview_trajectory_moves


def _late_failure(values):
    yield from values
    raise AssertionError("trajectory provider was consumed beyond the accepted budget")


@pytest.mark.parametrize("oversized", ["times", "states"])
def test_preview_stops_reading_after_maximum_sample_count(oversized):
    # max_moves=1 permits at most two samples, so observing a third suffices
    # to reject input without iterating the entire external data source.
    times = _late_failure([0.0, 1.0, 2.0]) if oversized == "times" else (0.0, 1.0)
    states = _late_failure([(0.0,), (1.0,), (2.0,)]) if oversized == "states" else ((0.0,), (1.0,))
    with pytest.raises(ValueError, match="candidate budget"):
        preview_trajectory_moves(SimpleNamespace(times=times, states=states),
                                 entity_id="vera", action_prefix="trial", max_moves=1)


def test_preview_stops_reading_unbounded_state_vectors():
    # A malicious state vector can itself be an endless iterable, independent
    # of the outer trajectory length. A bounded preview must reject it.
    states = (_late_failure(range(1025)), (1.0,))
    with pytest.raises(ValueError, match="state dimension"):
        preview_trajectory_moves(SimpleNamespace(times=(0.0, 1.0), states=states),
                                 entity_id="vera", action_prefix="trial", max_moves=1)
