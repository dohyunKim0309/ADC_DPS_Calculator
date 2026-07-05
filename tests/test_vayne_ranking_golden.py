"""베인 러너 이관 동작 보존 골든 — 이관 전 _rank_rows 실측값(2026-07-06, weighted 4:4:3:3 고정).
값 출처: 이관 직전 커밋에서 캡처 스크립트 실행(값 변경 = 동작 변화 신호)."""
from adc_sim.simulations.vayne import _rank_rows, CONTROL_PATH

PATHS = [CONTROL_PATH, ("kraken", "pd", "ie", "ldr"), ("yuntal25", "c44", "ie", "ldr"),
         ("guinsoo", "botrk", "terminus", "pd"), ("kraken", "guinsoo", "ie", "pd")]

GOLDEN = {
    # (path 튜플): (rel_dpg_score, weighted_dpg)  ← 캡처 출력으로 채울 것
    ("yuntal25", "c44", "ie", "ldr"): (137.764911, 137.599482),
    ("kraken", "pd", "ie", "ldr"): (116.407474, 116.448122),
    ("kraken", "guinsoo", "ie", "pd"): (106.337693, 106.591555),
    ("botrk", "guinsoo", "terminus", "pd"): (100.0, 100.143652),
}
GOLDEN_N_ROWS = 4        # 캡처 출력의 n_rows
GOLDEN_CTRL_WDPG = 100.143652   # 캡처 출력의 ctrl weighted_dpg


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
