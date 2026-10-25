import json

import pytest

from vera_habitat.navigation_eval import main


def test_report_rejects_unrepresentably_large_sensor_range_as_value_error():
    from vera_habitat.navigation_eval import build_evaluation_report

    with pytest.raises(ValueError, match="invalid evaluation sensor range"):
        build_evaluation_report(
            split="holdout", family="barrier", episodes=1, max_steps=40,
            sensor_range_m=10**1000, policies=("greedy",),
        )


def test_cli_emits_reproducible_heldout_report(capsys):
    args = ["--split", "holdout", "--episodes", "4"]
    assert main(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["schema_version"] == "VERA_HABITAT_NAV_EVALUATION_V1"
    assert report["split"] == "holdout"
    assert report["seeds"] == [1000, 1001, 1002, 1003]
    assert len(report["baselines"]) == 3
    assert report["baselines"][-1]["privileged_map"] is True
    assert "scene" not in report
    assert "reward_is_not_learning_proof" in report["limitations"]
    assert main(args) == 0
    again = json.loads(capsys.readouterr().out)
    assert again == report


@pytest.mark.parametrize("args", [
    ["--split", "invalid"],
    ["--episodes", "0"],
    ["--episodes", "21"],
    ["--policies", "mystery"],
])
def test_cli_rejects_unsupported_options(args):
    with pytest.raises(SystemExit):
        main(args)
