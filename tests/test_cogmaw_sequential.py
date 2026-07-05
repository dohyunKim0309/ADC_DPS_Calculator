"""순차 최적화 DP 코어 테스트 — 주입식 power/후보맵, 시뮬 무의존."""
from adc_sim.simulations.cogmaw_sequential import (
    legal_next_items, solve_sequential, extract_trajectory, node_alternatives,
    default_candidates_map, SLOT5_CANDIDATES, PEN_EXCLUSIVE, PowerCache,
)

# 수계산 합성 사례: horizon=2, γ=0.5
CANDS = {1: ["a", "b"], 2: ["a", "b", "c"]}
POWERS = {
    frozenset({"a"}): 10.0, frozenset({"b"}): 8.0,
    frozenset({"a", "b"}): 20.0, frozenset({"a", "c"}): 30.0,
    frozenset({"b", "c"}): 5.0,
}


def _power(state):
    return POWERS[state]


def test_dp_matches_hand_computation():
    W, best = solve_sequential(_power, gamma=0.5, horizon=2, candidates_map=CANDS)
    # W({a}) = max(0.5*20, 0.5*30) = 15 (best=c) ; W({b}) = max(0.5*20, 0.5*5) = 10 (best=a)
    assert abs(W[frozenset({"a"})] - 15.0) < 1e-9
    assert best[frozenset({"a"})] == "c"
    assert abs(W[frozenset({"b"})] - 10.0) < 1e-9
    assert best[frozenset({"b"})] == "a"
    # W(∅) = max(0.5*(10+15), 0.5*(8+10)) = 12.5 (best=a)
    assert abs(W[frozenset()] - 12.5) < 1e-9
    assert best[frozenset()] == "a"


def test_trajectory_follows_best_chain():
    _, best = solve_sequential(_power, gamma=0.5, horizon=2, candidates_map=CANDS)
    assert extract_trajectory(best) == ["a", "c"]


def test_node_alternatives_ranked():
    W, _ = solve_sequential(_power, gamma=0.5, horizon=2, candidates_map=CANDS)
    alts = node_alternatives(frozenset(), W, _power, 0.5, CANDS, top_n=3)
    assert [a[0] for a in alts] == ["a", "b"]
    assert abs(alts[0][1] - 12.5) < 1e-9 and abs(alts[1][1] - 9.0) < 1e-9


def test_legal_next_items_pen_exclusive_and_dup():
    cands = {2: ["terminus", "ldr", "guinsoo", "nashor"]}
    owned = frozenset({"ldr"})
    out = legal_next_items(owned, 2, cands)
    assert "terminus" not in out and "ldr" not in out
    assert set(out) == {"guinsoo", "nashor"}


def test_default_candidates_map_shape():
    m = default_candidates_map()
    assert set(m.keys()) == {1, 2, 3, 4, 5}
    assert m[5] == SLOT5_CANDIDATES and "c44" in m[1]


def _fake_sim(full_path, core_tier, doran_key=None, boots_key=None,
              rune_as_bonus=0.0, keystone_cls=None):
    return 100.0 * core_tier, 1000.0 * core_tier


def test_power_cache_memoizes_and_computes_dpg():
    pkg = {"doran": "doranblade", "boots": "berserker", "rune_as": 0.0, "label": "T"}
    pc = PowerCache(pkg, keystone_cls=None, sim_fn=_fake_sim)
    s2 = frozenset({"a", "b"})
    assert abs(pc.dps(s2) - 200.0) < 1e-9
    assert abs(pc.dpg(s2) - 100.0) < 1e-9      # 200 / (2000/1000)
    assert pc.sim_calls == 1                    # dps→dpg 재호출에도 시뮬 1회
    pc.dps(s2)
    assert pc.sim_calls == 1


def test_power_cache_passes_sorted_tuple_and_tier():
    seen = {}

    def spy(full_path, core_tier, **kw):
        seen["path"], seen["tier"] = full_path, core_tier
        return 1.0, 1.0

    pkg = {"doran": "doranblade", "boots": "berserker", "rune_as": 0.0, "label": "T"}
    pc = PowerCache(pkg, keystone_cls=None, sim_fn=spy)
    pc.dps(frozenset({"b", "a", "c"}))
    assert seen["path"] == ("a", "b", "c") and seen["tier"] == 3


def test_run_scenario_reduced_pool_end_to_end():
    """실제 시뮬로 축소풀(3슬롯) end-to-end — 궤적 합법성과 필드 형태 검증."""
    from adc_sim.simulations.cogmaw_sequential import run_scenario
    from adc_sim.runes import LethalTempo
    from adc_sim.data.items_data import ADC_PACKAGES
    small = {1: ["guinsoo", "kraken"], 2: ["guinsoo", "kraken", "nashor"],
             3: ["nashor", "terminus", "ldr"]}
    out = run_scenario(LethalTempo, ADC_PACKAGES[1], "dpg",
                       candidates_map=small, horizon=3)
    traj = out["trajectory"]
    assert len(traj) == 3 and len(set(traj)) == 3
    assert sum(1 for k in traj if k in {"terminus", "ldr", "mortal"}) <= 1
    assert len(out["steps"]) == 3
    for step in out["steps"]:
        assert step["dps"] > 0 and step["gold"] > 0
    assert len(out["alternatives"]) == 3
