"""Deterministic evaluation report fingerprint and in-process replay validation.

Public fingerprints detect changes, not origin/authenticity.
"""
from __future__ import annotations

from hashlib import sha256
import json

BUNDLE_SCHEMA = "VERA_HABITAT_NAV_EVAL_BUNDLE_V1"
REPORT_SCHEMA = "VERA_HABITAT_NAV_EVALUATION_V1"
MAX_BUNDLE_BYTES = 262144
MAX_REPLAY_STEPS = 20000


def _canonical(report: dict) -> bytes:
    try:
        return json.dumps(report, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError("invalid evaluation report JSON") from exc


def seal_evaluation_report(report: dict) -> dict:
    """Make a detached JSON report with a public fingerprint."""
    if type(report) is not dict or report.get("schema_version") != REPORT_SCHEMA:
        raise ValueError("unsupported evaluation report")
    data = _canonical(report)
    if len(data) > MAX_BUNDLE_BYTES // 2:
        raise ValueError("evaluation report exceeds budget")
    return {
        "schema_version": BUNDLE_SCHEMA,
        "sha256": sha256(data).hexdigest(),
        "report": json.loads(data),
    }


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate evaluation JSON key")
        result[key] = value
    return result


def _reject_nonfinite(value: str):
    raise ValueError("nonfinite evaluation JSON value")


def verify_evaluation_bundle(source: str) -> dict:
    """Verify structure, public digest and deterministic replay.

    This does not authenticate the author, evaluator source or real-world effect.
    """
    if type(source) is not str or len(source.encode("utf-8")) > MAX_BUNDLE_BYTES:
        raise ValueError("evaluation bundle exceeds input budget")
    try:
        bundle = json.loads(source, object_pairs_hook=_no_duplicate_keys,
                            parse_constant=_reject_nonfinite)
    except (json.JSONDecodeError, UnicodeError, RecursionError) as exc:
        raise ValueError("invalid evaluation bundle JSON") from exc
    if type(bundle) is not dict or set(bundle) != {
        "schema_version", "sha256", "report"
    } or bundle["schema_version"] != BUNDLE_SCHEMA:
        raise ValueError("invalid evaluation bundle shape or schema")
    report = bundle["report"]
    if type(report) is not dict or report.get("schema_version") != REPORT_SCHEMA:
        raise ValueError("invalid evaluation bundle report")
    digest = bundle["sha256"]
    if type(digest) is not str or len(digest) != 64 or any(
        c not in "0123456789abcdef" for c in digest
    ) or sha256(_canonical(report)).hexdigest() != digest:
        raise ValueError("evaluation fingerprint mismatch")

    from .navigation_eval import build_evaluation_report
    try:
        baselines = report["baselines"]
        if type(baselines) is not list or not 1 <= len(baselines) <= 4:
            raise ValueError("invalid policies")
        policies = [b["policy"] for b in baselines]
        episodes = len(report["seeds"])
        steps = report["max_steps"]
        if (type(steps) is not int or
                episodes * steps * len(policies) > MAX_REPLAY_STEPS):
            raise ValueError("replay exceeds work budget")
        reference = build_evaluation_report(
            split=report["split"], family=report["family"],
            episodes=episodes, max_steps=steps,
            sensor_range_m=report["sensor_range_m"], policies=policies,
        )
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError("evaluation replay metadata invalid or exceeds budget") from exc
    if report != reference:
        raise ValueError("evaluation replay mismatch")
    return report
