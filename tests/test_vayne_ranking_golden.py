"""베인 러너 이관 동작 보존 골든 — weighted 4:4:3:3 고정.
값 출처: 2026-07-14 C44 %증폭 스코프 정정(W/Q 미증폭, 오직 기본 평타 AA 만) 이후 재캡처.
직전 스냅샷 이후 변화: C44 를 포함한 빌드(yuntal25-c44-ie-ldr) 만 W/Q 증폭 손실로 소폭 하락.
비-C44 빌드(kraken-pd-ie-ldr, kraken-guinsoo-ie-pd, CTRL) 는 완전 불변.
값 변경 = 동작 변화 신호."""
from adc_sim.simulations.vayne import _rank_rows, CONTROL_PATH

PATHS = [CONTROL_PATH, ("kraken", "pd", "ie", "ldr"), ("yuntal25", "c44", "ie", "ldr"),
         ("guinsoo", "botrk", "terminus", "pd"), ("kraken", "guinsoo", "ie", "pd")]

GOLDEN = {
    # (path 튜플): (rel_dpg_score, weighted_dpg)
    ("yuntal25", "c44", "ie", "ldr"): (122.767314, 121.425689),
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
