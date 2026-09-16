"""베인 러너 이관 동작 보존 골든 — weighted 4:4:3:3 고정.
값 출처: 2026-08-16 성장 곡선 정정(`adc_sim/growth.py`, 선형 → 실 LoL 곡선) 이후 재캡처(2026-09-15).
코어 티어 레벨이 전부 18 미만이라 전 챔프 스탯이 내려갔고 컨트롤 weighted_dpg 도 97.94 → 67.53 으로
하락했다(RelDPG 는 컨트롤 대비 비율이라 재정규화). 중복 정의돼 있던 GOLDEN_CTRL_WDPG 한 줄도 제거.
값 변경 = 동작 변화 신호."""
from adc_sim.simulations.vayne import _rank_rows, CONTROL_PATH

PATHS = [CONTROL_PATH, ("kraken", "pd", "ie", "ldr"), ("yuntal25", "c44", "ie", "ldr"),
         ("guinsoo", "botrk", "terminus", "pd"), ("kraken", "guinsoo", "ie", "pd")]

GOLDEN = {
    # (path 튜플): (rel_dpg_score, weighted_dpg)
    ("yuntal25", "c44", "ie", "ldr"): (120.495580, 81.470230),
    ("kraken", "pd", "ie", "ldr"): (110.024102, 74.111842),
    ("kraken", "guinsoo", "ie", "pd"): (105.773041, 70.984633),
    ("botrk", "guinsoo", "terminus", "pd"): (100.0, 67.528109),
}
GOLDEN_N_ROWS = 4
GOLDEN_CTRL_WDPG = 67.528109


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
