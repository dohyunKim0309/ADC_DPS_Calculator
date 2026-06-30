"""CogMaw 4-core ranking. Run: .venv/bin/python -m tests.test_cogmaw_ranking"""
from adc_sim.simulations.cogmaw import get_cogmaw_4core_top1_build


def test_top1_has_control_in_search_and_score():
    top1 = get_cogmaw_4core_top1_build()
    assert isinstance(top1["path"], tuple) and len(top1["path"]) == 4
    assert top1["score"] > 0
    # control build must exist in the search space (실전 메타 빌드로 변경됨)
    assert tuple(sorted(top1["control_path"])) == tuple(sorted(("guinsoo", "navori", "terminus", "wit")))


if __name__ == "__main__":
    test_top1_has_control_in_search_and_score()
    print("PASS test_top1_has_control_in_search_and_score")
    print("ALL PASS")
