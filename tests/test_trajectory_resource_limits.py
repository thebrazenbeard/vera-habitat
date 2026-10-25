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


def test_preview_rejects_amplified_action_identifier_output():
    count = 16
    trace = SimpleNamespace(
        times=tuple(float(i) for i in range(count + 1)),
        states=tuple((float(i),) for i in range(count + 1)),
    )
    # Each output ID repeats the caller-controlled 64-KiB prefix. The
    # 16 resulting strings exceed a 1-million-character output budget.
    with pytest.raises(ValueError, match="action identifier budget"):
        preview_trajectory_moves(trace, entity_id="vera",
                                 action_prefix="p" * 65_536, max_moves=count)


def test_preview_allows_large_prefix_when_not_amplified():
    prefix = "p" * 65_536
    trace = SimpleNamespace(times=(0.0, 1.0), states=((0.0,), (1.0,)))
    proposals = preview_trajectory_moves(trace, entity_id="vera",
                                         action_prefix=prefix, max_moves=1)
    assert len(proposals) == 1
    assert proposals[0].action_id == f"{prefix}:1"


@pytest.mark.parametrize("field", ["y", "times", "states"])
def test_preview_rejects_unrepresentably_large_integers_as_value_error(field):
    huge = 10 ** 1000
    trace = SimpleNamespace(times=(0.0, 1.0), states=((0.0,), (1.0,)))
    kwargs = {"entity_id": "vera", "action_prefix": "trial"}
    if field == "y":
        kwargs["y"] = huge
    elif field == "times":
        trace.times = (0.0, huge)
    else:
        trace.states = ((0.0,), (huge,))
    # Bad coordinates/timestamps must follow the public ValueError contract,
    # not escape as OverflowError from float conversion inside isfinite().
    with pytest.raises(ValueError, match="finite"):
        preview_trajectory_moves(trace, **kwargs)
