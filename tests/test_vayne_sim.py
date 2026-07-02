"""Task 5: vayne.py 시뮬 — 컨트롤 존재·RelDPG 정합·top1/powercompare 산출."""
from adc_sim.simulations.vayne import (
    simulate_vayne_core_path, CONTROL_PATH,
    get_vayne_4core_top1_build, get_vayne_powercompare_builds,
)


def test_control_path_is_expected():
    assert CONTROL_PATH == ("botrk", "guinsoo", "terminus", "pd")


def test_simulate_core_path_positive():
    dps, cost = simulate_vayne_core_path(list(CONTROL_PATH), core_tier=2,
                                         doran_key="doranblade", boots_key="berserker")
    assert dps > 0 and cost > 0


def test_top1_build_has_control_metadata():
    top1 = get_vayne_4core_top1_build(rank_by="dpg")
    assert "path" in top1 and len(top1["path"]) == 4
    assert top1["control_path"] == CONTROL_PATH
    assert top1["score"] > 0 and top1["weighted_dpg"] > 0


def test_powercompare_builds_shape():
    best, meta = get_vayne_powercompare_builds()
    for b in (best, meta):
        assert len(b["path"]) == 4
        assert b["doran"] and b["boots"]
    assert meta["path"] == CONTROL_PATH   # meta = 컨트롤(실전 기준)
