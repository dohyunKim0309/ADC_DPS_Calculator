# -*- coding: utf-8 -*-
"""타깃 아키타입(딜러/브루저/탱커) 계약 — 유나라 시뮬 연동 포함.

이 테스트가 잠그는 것:
  · 아키타입 교체가 **완성 코어와 하프 구간 둘 다** 바꾼다(한쪽만 바뀌면 곡선이 어긋난다).
  · 하프 = 인접 코어 선형 보간, 1코어 하프 = 코어1.
  · 추가체력 = max(0, HP−1600) 규약.
  · 유나라 기본 아키타입 = 브루저, 기본 혼합 = 적1:적2:적3 = 1:1:1.
"""
import pytest

from adc_sim.simulations import yunara as Y
from adc_sim.simulations.target_archetypes import (
    BONUS_HP_BASELINE, DEFAULT_ARCHETYPE, TARGET_ARCHETYPES,
    bonus_hp, core_target_stats, half_target_stats,
)


@pytest.fixture(autouse=True)
def restore_archetype():
    """테스트가 활성 아키타입을 건드리므로 원복한다(모듈 전역 상태)."""
    before = Y.ACTIVE_ARCHETYPE
    yield
    Y.set_target_archetype(before)


def test_three_archetypes_cover_all_tiers():
    for name, spec in TARGET_ARCHETYPES.items():
        assert set(spec["tiers"]) == {1, 2, 3, 4, 5}, name
        hps = [spec["tiers"][t][0] for t in range(1, 6)]
        armors = [spec["tiers"][t][1] for t in range(1, 6)]
        assert hps == sorted(hps), f"{name} 체력이 코어 진행과 함께 줄어든다"
        assert armors == sorted(armors), f"{name} 방어력이 코어 진행과 함께 줄어든다"


def test_dealer_is_softest_tank_is_hardest():
    d = core_target_stats("dealer")[5]
    b = core_target_stats("bruiser")[5]
    t = core_target_stats("tank")[5]
    assert d["hp"] < b["hp"] < t["hp"]
    assert d["armor"] < b["armor"] < t["armor"]


def test_tank_mr_grows_four_per_level():
    """탱커 마저 = 레벨당 +4 → 코어 사이(2레벨) +8. 사용자 확정 2026-09-16."""
    tiers = TARGET_ARCHETYPES["tank"]["tiers"]
    for tier in range(2, 6):
        assert tiers[tier][2] - tiers[tier - 1][2] == 8


def test_half_is_midpoint_and_tier1_matches_core1():
    stats = core_target_stats("dealer")
    assert half_target_stats(1, "dealer") == stats[1]
    mid = half_target_stats(3, "dealer")
    assert mid["hp"] == pytest.approx((stats[2]["hp"] + stats[3]["hp"]) / 2)
    assert mid["armor"] == pytest.approx((stats[2]["armor"] + stats[3]["armor"]) / 2)


def test_bonus_hp_rule():
    assert bonus_hp(BONUS_HP_BASELINE - 300) == 0
    assert bonus_hp(BONUS_HP_BASELINE + 800) == 800


def test_unknown_archetype_raises():
    with pytest.raises(ValueError):
        core_target_stats("nope")
    with pytest.raises(ValueError):
        Y.set_target_archetype("nope")


def test_switch_moves_both_core_and_half_targets():
    Y.set_target_archetype("dealer")
    dealer_core = Y.build_target_for_core(3)
    dealer_half = Y._half_tier_target(3)
    Y.set_target_archetype("tank")
    tank_core = Y.build_target_for_core(3)
    tank_half = Y._half_tier_target(3)
    assert tank_core.max_hp > dealer_core.max_hp
    assert tank_core.armor > dealer_core.armor
    assert tank_half.max_hp > dealer_half.max_hp, "하프 구간이 아키타입을 따라가지 않는다"
    assert tank_half.armor > dealer_half.armor


def test_yunara_defaults():
    assert DEFAULT_ARCHETYPE == "bruiser"
    assert Y.CORE_TARGET_STATS == core_target_stats(Y.ACTIVE_ARCHETYPE)
    weights = dict(Y.TARGET_MIX_WEIGHTS)
    assert set(weights) == {1, 2, 3}
    assert all(w == pytest.approx(1 / 3) for w in weights.values())
