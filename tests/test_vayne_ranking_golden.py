"""베인 러너 이관 동작 보존 골든 — weighted 4:4:3:3 고정.
값 출처: 2026-07-20 Q 평타리셋 옵션화 (q_wall_reset=False 기본, 오픈 필드 실전 반영) 이후 재캡처.
[H-VAYNE-Q-WALL-1] Q 는 벽 붙은 상황에서만 평타 캔슬 가능 — 오픈 필드 기본에서는 리셋 없음.
직전 스냅샷(2026-07-20 amp 곱연산 정정) 이후 전 빌드 소폭 하락 (Q 강화평타 리셋 손실).
값 변경 = 동작 변화 신호."""
from adc_sim.simulations.vayne import _rank_rows, CONTROL_PATH

PATHS = [CONTROL_PATH, ("kraken", "pd", "ie", "ldr"), ("yuntal25", "c44", "ie", "ldr"),
         ("guinsoo", "botrk", "terminus", "pd"), ("kraken", "guinsoo", "ie", "pd")]

GOLDEN = {
    # (path 튜플): (rel_dpg_score, weighted_dpg)
    ("yuntal25", "c44", "ie", "ldr"): (118.393087, 85.250783),
    ("kraken", "pd", "ie", "ldr"): (109.624657, 78.904888),
    ("kraken", "guinsoo", "ie", "pd"): (108.913132, 78.511884),
    ("botrk", "guinsoo", "terminus", "pd"): (100.0, 72.061774),
}
GOLDEN_N_ROWS = 4
GOLDEN_CTRL_WDPG = 72.061774


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
