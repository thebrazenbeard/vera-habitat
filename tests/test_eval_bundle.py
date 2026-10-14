"""Reproducible navigation reports can be replay-checked without trust claims."""
import copy
import hashlib
import json

import pytest

from vera_habitat.eval_bundle import seal_evaluation_report, verify_evaluation_bundle
from vera_habitat.navigation_eval import main


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"),
                      allow_nan=False, ensure_ascii=False).encode("utf-8")


def sample(capsys):
    assert main(["--split", "holdout", "--episodes", "3", "--policies",
                 "random", "memory", "oracle", "--bundle"]) == 0
    return json.loads(capsys.readouterr().out)


def test_cli_bundle_reproducible_and_replay_verifiable(capsys):
    first = sample(capsys)
    assert first["schema_version"] == "VERA_HABITAT_NAV_EVAL_BUNDLE_V1"
    assert first["report"]["split"] == "holdout"
    assert first["report"]["seeds"] == [1000, 1001, 1002]
    assert verify_evaluation_bundle(json.dumps(first)) == first["report"]
    assert sample(capsys) == first


def test_default_cli_output_stays_unchanged(capsys):
    assert main(["--episodes", "2"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["schema_version"] == "VERA_HABITAT_NAV_EVALUATION_V1"
    assert "sha256" not in report and "report" not in report


def test_broken_digest_is_rejected(capsys):
    bundle = sample(capsys)
    bundle["report"]["seeds"][0] = 19
    with pytest.raises(ValueError, match="fingerprint"):
        verify_evaluation_bundle(json.dumps(bundle))


@pytest.mark.parametrize("change", ["seeds", "result", "split", "limits"])
def test_forged_public_hash_cannot_bypass_replay_verification(capsys, change):
    bundle = sample(capsys)
    report = bundle["report"]
    if change == "seeds":
        report["seeds"] = [1001, 1002, 1003]
    elif change == "result":
        report["baselines"][0]["success_rate"] = 0.125
    elif change == "split":
        report["split"] = "train"
    elif change == "limits":
        report["max_steps"] = 10001
    bundle["sha256"] = hashlib.sha256(canonical(report)).hexdigest()
    with pytest.raises(ValueError, match="replay"):
        verify_evaluation_bundle(json.dumps(bundle))


def test_duplicate_keys_and_unknown_fields_fail_closed(capsys):
    bundle = sample(capsys)
    duplicate = json.dumps(bundle).replace('"schema_version":', '"schema_version": "fake", "schema_version":', 1)
    with pytest.raises(ValueError, match="duplicate"):
        verify_evaluation_bundle(duplicate)
    bundle["unexpected"] = "field"
    with pytest.raises(ValueError, match="bundle"):
        verify_evaluation_bundle(json.dumps(bundle))


def test_report_is_detached_and_bounded(capsys):
    bundle = sample(capsys)
    original = copy.deepcopy(bundle["report"])
    sealed = seal_evaluation_report(original)
    original["seeds"][0] = 17
    assert sealed["report"]["seeds"][0] == 1000
    with pytest.raises(ValueError, match="budget"):
        verify_evaluation_bundle(" " * 300000)


def test_schema_and_nonfinite_fail_closed(capsys):
    bundle = sample(capsys)
    bundle["schema_version"] = "OTHER"
    with pytest.raises(ValueError, match="bundle"):
        verify_evaluation_bundle(json.dumps(bundle))
    with pytest.raises(ValueError):
        seal_evaluation_report({"schema_version": "VERA_HABITAT_NAV_EVALUATION_V1", "nan": float("nan")})


def test_bundle_rejects_excessive_replay_work_before_simulation(monkeypatch):
    import vera_habitat.navigation_eval as navigation_eval

    def unexpected(**kwargs):
        pytest.fail("replay budget should reject before evaluation")

    monkeypatch.setattr(navigation_eval, "evaluate_baselines", unexpected)
    with pytest.raises(SystemExit):
        main(["--episodes", "20", "--max-steps", "10000", "--bundle"])
