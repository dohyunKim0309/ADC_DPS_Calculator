"""공통 랭킹 러너 — 합성 simulate_fn 으로 수계산 검증(시뮬 무의존)."""
from adc_sim.simulations.ranking_core import rank_builds

# 합성 세계: DPS = 앞 tier개 아이템 가치 합, gold = 1000×tier.
VALUE = {"a": 100.0, "b": 90.0, "c": 80.0, "x": 70.0, "y": 60.0}
PKGS = ({"key": "T", "label": "T", "doran": None, "boots": "berserker", "rune_as": 0.0},)


def _sim(path, tier, doran_key=None, boots_key=None, rune_as_bonus=0.0):
    return sum(VALUE[k] for k in path[:tier]), 1000.0 * tier


PATHS = [("a", "b", "x", "y"), ("b", "a", "x", "y"), ("c", "x", "y", "a"),
         ("x", "y", "a", "b")]  # 컨트롤 = ("x","y","a","b")


def test_rank_builds_dedup_control_and_scores():
    rows, best_ctrl = rank_builds(_sim, PATHS, ("x", "y", "a", "b"),
                                  weights_raw=[1, 1, 1, 1], packages=PKGS)
    # {a,b,x,y} 집합은 3개 순서 중 최고 dedupe_eff 하나 + 컨트롤 정규순서 고정 →
    # 컨트롤 집합은 컨트롤 순서 행만 잔존, {c,x,y,a} 1행 → 총 2행.
    assert len(rows) == 2
    assert best_ctrl["path"] == ("x", "y", "a", "b") and best_ctrl["is_control"]
    # 컨트롤 rel_dpg_score == 100 (자기 자신 baseline)
    assert abs(best_ctrl["rel_dpg_score"] - 100.0) < 1e-9
    # 수계산: {c,x,y,a} 경로 c-x-y-a 의 tier별 DPS = 80,150,210,310 / dpg = 80,75,70,77.5
    # 컨트롤 x-y-a-b: 70,130,230,320 → dpg 70,65,76.667,80
    other = next(r for r in rows if not r["is_control"])
    rel = [80 / 70, 75 / 65, 70 / (230 / 3), 77.5 / 80]
    expected = sum(r * 100 for r in rel) / 4
    assert abs(other["rel_dpg_score"] - expected) < 1e-9


def test_rank_builds_default_weights_from_settings():
    from adc_sim.settings import CORE_WEIGHTS_RAW
    rows, _ = rank_builds(_sim, PATHS, ("x", "y", "a", "b"), packages=PKGS)
    r = rows[0]
    w = [x / sum(CORE_WEIGHTS_RAW) for x in CORE_WEIGHTS_RAW]
    assert abs(r["weighted_dpg"] - sum(w[i] * r["dpg"][i] for i in range(4))) < 1e-9


def test_rank_builds_missing_control_raises():
    import pytest
    with pytest.raises(RuntimeError):
        rank_builds(_sim, [("a", "b", "x", "y")], ("c", "x", "y", "a"), packages=PKGS)


def test_rank_builds_pinned_paths_kept_and_tagged():
    rows, _ = rank_builds(_sim, PATHS, ("x", "y", "a", "b"), packages=PKGS,
                          pinned_paths=(("PIN1", ("c", "x", "y", "a")),))
    pinned = [r for r in rows if r.get("pinned_tag") == "PIN1"]
    assert len(pinned) == 1 and pinned[0]["path"] == ("c", "x", "y", "a")
