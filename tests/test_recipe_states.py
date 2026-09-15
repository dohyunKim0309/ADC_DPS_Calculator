"""하프 코어(아이템 사이 구간) 후보 열거 규칙 테스트."""
from adc_sim.data.items_data import ITEMS
from adc_sim.data.recipe_states import (
    component_pen_flags,
    component_stats,
    half_core_candidates,
    half_core_window,
    partial_states,
)


def test_window_is_half_price_rounded_up_to_100():
    assert half_core_window("kraken") == (1500, 1600)   # 3000 / 2
    assert half_core_window("ie") == (1800, 1900)       # 3500 / 2 = 1750 → 1800
    assert half_core_window("pd") == (1400, 1500)       # 2650 / 2 = 1325 → 1400


def test_partial_states_recurse_into_sub_components():
    """경계 = 곡궁 + 롱소드 2개처럼 하위템의 하위템도 개별 구매 대상이다."""
    states = dict((tuple(names), cost) for cost, names in partial_states("terminus"))
    assert ("곡궁", "롱소드", "롱소드") in states
    assert states[("곡궁", "롱소드", "롱소드")] == 1400


def test_partial_states_exclude_empty_and_complete():
    costs = [cost for cost, _ in partial_states("guinsoo")]
    assert costs, "부분 상태가 있어야 한다"
    assert min(costs) > 0
    assert max(costs) < ITEMS["guinsoo"]["cost"]


def test_candidates_inside_window_when_window_is_non_empty():
    lo, hi = half_core_window("guinsoo")
    candidates = half_core_candidates("guinsoo")
    assert candidates
    assert all(lo <= cost <= hi for cost, _ in candidates)


def test_window_relaxes_downward_only_when_empty():
    """경계는 창 [1500,1600]이 비어 100 내려간 [1400,1600]에서 두 조합을 얻는다."""
    lo, hi = half_core_window("terminus")
    assert not any(lo <= cost <= hi for cost, _ in partial_states("terminus"))
    candidates = half_core_candidates("terminus")
    assert {cost for cost, _ in candidates} == {1400, 1450}
    assert all(cost <= hi for cost, _ in candidates), "상단 완화는 없다"


def test_deep_relaxation_keeps_upper_bound():
    """라바돈은 1200(쓸큰지 1개) 다음이 2400이라 창을 크게 밑돌지만 hi 는 안 넘는다."""
    _, hi = half_core_window("rabadon")
    candidates = half_core_candidates("rabadon")
    assert candidates == ((1200, ("쓸데없이 큰 지팡이",)),)
    assert all(cost <= hi for cost, _ in candidates)


def test_component_stats_filters_unmodeled_keys():
    stats = component_stats(("열정의 검",))
    assert stats == {"as": 0.15, "crit": 0.15}, "ms_percent 는 STAT_KEYS 밖이라 빠진다"


def test_component_pen_flags_marks_blighting_jewel():
    assert component_pen_flags(("역병의 보석",)) == (False, True)
    assert component_pen_flags(("곡궁",)) == (False, False)


def test_every_recipe_item_has_at_least_one_half_state():
    missing = [key for key, spec in ITEMS.items()
               if spec.get("recipe") and not half_core_candidates(key)]
    assert not missing, f"조합식이 있는데 하프 후보가 없는 아이템: {missing}"
