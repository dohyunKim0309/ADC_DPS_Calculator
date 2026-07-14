"""베인 러너 이관 동작 보존 골든 — weighted 4:4:3:3 고정.
값 출처: 2026-07-14 팬텀히트 은화살 가속 픽스([H-VAYNE-W-GUI]) 이후 재캡처.
비-구인수 빌드(yuntal25-c44-ie-ldr / kraken-pd-ie-ldr)의 weighted_dpg 는 픽스 전과 동일,
rel_dpg_score 는 CTRL(구인수 보유) 의 wdpg 변동으로 재정규화되어 소폭 이동.
값 변경 = 동작 변화 신호."""
from adc_sim.simulations.vayne import _rank_rows, CONTROL_PATH

PATHS = [CONTROL_PATH, ("kraken", "pd", "ie", "ldr"), ("yuntal25", "c44", "ie", "ldr"),
         ("guinsoo", "botrk", "terminus", "pd"), ("kraken", "guinsoo", "ie", "pd")]

GOLDEN = {
    # (path 튜플): (rel_dpg_score, weighted_dpg)
    ("yuntal25", "c44", "ie", "ldr"): (138.495105, 137.599482),
    ("kraken", "pd", "ie", "ldr"): (116.995271, 116.448122),
    ("kraken", "guinsoo", "ie", "pd"): (110.752865, 110.310670),
    ("botrk", "guinsoo", "terminus", "pd"): (100.0, 99.638514),
}
GOLDEN_N_ROWS = 4
GOLDEN_CTRL_WDPG = 99.638514


def test_vayne_rank_rows_golden():
    rows, ctrl = _rank_rows(PATHS, weights_raw=[4.0, 4.0, 3.0, 3.0])
    assert len(rows) == GOLDEN_N_ROWS
    assert abs(ctrl["weighted_dpg"] - GOLDEN_CTRL_WDPG) < 1e-6
    for r in rows:
        key = tuple(r["path"])
        assert key in GOLDEN, f"unexpected row {key}"
        exp_rel, exp_wdpg = GOLDEN[key]
        assert abs(r["rel_dpg_score"] - exp_rel) < 1e-6
        assert abs(r["weighted_dpg"] - exp_wdpg) < 1e-6
