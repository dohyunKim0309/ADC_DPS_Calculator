"""베인 러너 이관 동작 보존 골든 — weighted 4:4:3:3 고정.
값 출처: 2026-07-14 Q 추가딜 크리 미반영 픽스([H-VAYNE-Q-1]) 이후 재캡처.
(직전 스냅샷은 팬텀히트 픽스([H-VAYNE-W-GUI]) 직후. 이번엔 크리 빌드들의 절대 DPS 가
더 크게 하락 — Q 추가딜에서 크리 블렌드가 빠지면서 크리 코어(Yun/IE/LDR/PD/C44) 이득이 축소.)
값 변경 = 동작 변화 신호."""
from adc_sim.simulations.vayne import _rank_rows, CONTROL_PATH

PATHS = [CONTROL_PATH, ("kraken", "pd", "ie", "ldr"), ("yuntal25", "c44", "ie", "ldr"),
         ("guinsoo", "botrk", "terminus", "pd"), ("kraken", "guinsoo", "ie", "pd")]

GOLDEN = {
    # (path 튜플): (rel_dpg_score, weighted_dpg)
    ("yuntal25", "c44", "ie", "ldr"): (124.722663, 123.359228),
    ("kraken", "pd", "ie", "ldr"): (110.278381, 109.287311),
    ("kraken", "guinsoo", "ie", "pd"): (105.956339, 105.208764),
    ("botrk", "guinsoo", "terminus", "pd"): (100.0, 99.152716),
}
GOLDEN_N_ROWS = 4
GOLDEN_CTRL_WDPG = 99.152716


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
