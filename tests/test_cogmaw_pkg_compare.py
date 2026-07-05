"""코그모 후보 풀 상수 + 패키지 A/B 비교 헬퍼 테스트."""

from adc_sim.simulations.cogmaw import _build_pkg_compare_rows


def test_cogmaw_pool_contains_c44_all_tiers():
    from adc_sim.simulations.cogmaw import COGMAW_CORE_CANDIDATES
    for tier in (1, 2, 3, 4):
        assert "c44" in COGMAW_CORE_CANDIDATES[tier], f"c44 missing in tier {tier}"


def _row(path, pkg_label, dpg):
    return {"path": path, "pkg_label": pkg_label, "dpg": dpg}


BASELINE = [100.0, 100.0, 100.0, 100.0]
WEIGHTS = [0.25, 0.25, 0.25, 0.25]


def test_pkg_compare_pairs_scores_delta_winner():
    rows = [
        _row(("a", "b", "c", "d"), "Bld+Zerk", [100.0, 100.0, 100.0, 100.0]),
        _row(("a", "b", "c", "d"), "Bow+Glut", [110.0, 110.0, 110.0, 110.0]),
    ]
    out = _build_pkg_compare_rows(rows, [("a", "b", "c", "d")], BASELINE, WEIGHTS)
    assert len(out) == 1
    row = out[0]
    assert abs(row["scores"]["Bld+Zerk"] - 100.0) < 1e-9
    assert abs(row["scores"]["Bow+Glut"] - 110.0) < 1e-9
    assert abs(row["delta_b_minus_a"] - 10.0) < 1e-9
    assert row["winner"] == "Bow+Glut"


def test_pkg_compare_winner_a_and_target_order_kept():
    rows = [
        _row(("a", "b", "c", "d"), "Bld+Zerk", [120.0] * 4),
        _row(("a", "b", "c", "d"), "Bow+Glut", [100.0] * 4),
        _row(("e", "f", "g", "h"), "Bld+Zerk", [90.0] * 4),
        _row(("e", "f", "g", "h"), "Bow+Glut", [95.0] * 4),
    ]
    out = _build_pkg_compare_rows(
        rows, [("e", "f", "g", "h"), ("a", "b", "c", "d")], BASELINE, WEIGHTS)
    assert [r["path"] for r in out] == [("e", "f", "g", "h"), ("a", "b", "c", "d")]
    assert out[1]["winner"] == "Bld+Zerk"
    assert abs(out[0]["delta_b_minus_a"] - 5.0) < 1e-9


def test_pkg_compare_skips_path_missing_a_package():
    rows = [_row(("a", "b", "c", "d"), "Bld+Zerk", [100.0] * 4)]
    out = _build_pkg_compare_rows(rows, [("a", "b", "c", "d")], BASELINE, WEIGHTS)
    assert out == []


def test_control2_path_is_legal_in_pools():
    from adc_sim.simulations.cogmaw import CONTROL2_PATH, COGMAW_CORE_CANDIDATES
    assert CONTROL2_PATH == ("c44", "pd", "ldr", "ie")
    assert len(set(CONTROL2_PATH)) == 4
    for tier, key in enumerate(CONTROL2_PATH, start=1):
        assert key in COGMAW_CORE_CANDIDATES[tier], f"{key} not in tier {tier}"
    pen_exclusive = {"terminus", "ldr", "mortal"}
    assert sum(1 for k in CONTROL2_PATH if k in pen_exclusive) <= 1
