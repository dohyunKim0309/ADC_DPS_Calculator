"""코그모 5코어 receding-horizon(베인 방식) 모듈 동작 검증.

전체 후보 풀 탐색은 시나리오당 십수 초라 테스트에서는 축소 풀을 쓴다.
검증 항목: 궤적 길이·중복 없음·관통 배타 준수·골드 단조 증가·마지널 DPG 정의·
레퍼런스(CTRL/CTRL2) 확장이 4코어 순서를 보존하는지.

Run: .venv/bin/python -m pytest tests/test_cogmaw_receding.py -q
"""
from adc_sim.data.items_data import pen_rule_ok
from adc_sim.runes import LethalTempo
from adc_sim.data.items_data import ADC_PACKAGES
from adc_sim.simulations import cogmaw_receding as cr
from adc_sim.simulations import receding_core

SMALL_CANDIDATES = {
    1: ["guinsoo", "nashor", "terminus"],
    2: ["nashor", "terminus", "dawn"],
    3: ["nashor", "ldr", "void", "dawn"],
    4: ["shadowflame", "rabadon", "void"],
    5: ["shadowflame", "rabadon", "navori"],
}


def _solve_small():
    cache = cr.build_cache(LethalTempo, ADC_PACKAGES[0])
    out = receding_core.solve_greedy(cache, SMALL_CANDIDATES, cr.GAMMA, cr.HORIZON)
    return cache, out


def test_trajectory_shape_and_constraints():
    _cache, out = _solve_small()
    traj = out["trajectory"]
    assert len(traj) == cr.HORIZON
    assert len(set(traj)) == cr.HORIZON, "같은 아이템을 두 번 사면 안 된다"
    assert pen_rule_ok(tuple(traj)), "방관≤1 AND 마관≤1 (경계는 양쪽 겸비)"
    for slot, item in enumerate(traj, start=1):
        assert item in SMALL_CANDIDATES[slot]


def test_marginal_dpg_matches_definition():
    """각 슬롯의 marginal_dpg = ΔDPS / (Δ골드/1000) 여야 한다."""
    _cache, out = _solve_small()
    for step in out["steps"]:
        delta_dps = step["dps"] - step["baseline_dps_prev"]
        delta_gold = step["gold"] - step["baseline_gold_prev"]
        assert delta_gold > 0
        assert abs(step["marginal_dpg"] - delta_dps / (delta_gold / 1000.0)) < 1e-9
        # 코어가 늘수록 총 골드·총 DPS 는 증가한다(아이템 추가는 순증).
        assert step["dps"] > step["baseline_dps_prev"]


def test_full_pool_slot_candidates_cover_control_items():
    """컨트롤/레퍼런스 아이템이 실제 탐색 풀에 있어야 비교가 성립한다."""
    for path in (cr.CONTROL_PATH, cr.CONTROL2_PATH):
        for slot, key in enumerate(path, start=1):
            assert key in cr.CANDIDATES_BY_SLOT[slot], (path, slot, key)


def test_reference_extension_preserves_fixed_prefix():
    """레퍼런스는 4코어 순서를 그대로 두고 5코어째만 탐색으로 붙인다."""
    cache = cr.build_cache(LethalTempo, ADC_PACKAGES[0])
    locked = receding_core.solve_greedy(
        cache, SMALL_CANDIDATES, cr.GAMMA, cr.HORIZON,
        initial_fixed=("guinsoo", "nashor", "ldr", "shadowflame"))
    assert locked["trajectory"][:4] == ["guinsoo", "nashor", "ldr", "shadowflame"]
    assert len(locked["trajectory"]) == 5
    assert all(step.get("fixed_by_user") for step in locked["steps"][:4])
    assert not locked["steps"][4].get("fixed_by_user")


def test_slot5_pool_mirrors_slot4():
    """5코어 후보 = 4코어 후보 재사용(vayne.CORE5_CANDIDATES 관례)."""
    assert cr.CANDIDATES_BY_SLOT[5] == cr.CANDIDATES_BY_SLOT[4]
