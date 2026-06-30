"""Navori Flickerblade(평타당 Q/W/E 쿨 15%↓) + Wit's End(온힛 45 마법). [H-NAVORI-1]
Run: .venv/bin/python -m tests.test_navori_witend
"""
from adc_sim.champion import CogMaw, Target
from adc_sim.engine import run_simulation
from adc_sim.runes import LethalTempo, CutDown
from adc_sim.data.items_registry import create_item_from_key


def test_witend_data_and_onhit():
    w = create_item_from_key("wit")
    assert w.name == "Wit's End" and w.cost == 2800
    assert abs(w.stats["as"] - 0.50) < 1e-9 and w.stats["mr"] == 45
    # Fray 온힛 45 마법(2번째 슬롯). 구인수×2·황혼과새벽 가산·증폭은 부모 get_one_hit_damage 가 처리.
    assert w.on_hit(None, None) == (0, 45, 0, 0)


def test_navori_data():
    n = create_item_from_key("navori")
    assert n.name == "Navori Flickerblade" and n.cost == 2650
    assert abs(n.stats["as"] - 0.40) < 1e-9 and abs(n.stats["crit"] - 0.25) < 1e-9
    assert n.is_navori is True and abs(n.ability_cdr_per_attack - 0.15) < 1e-9


def test_navori_reduces_qwe_cooldowns_not_r():
    c = CogMaw(level=13, q_level=3, w_level=4, e_level=2, r_level=2); c.init_combat_state()
    c.add_item(create_item_from_key("navori"))
    c.cooldowns_remaining = {"q": 7.0, "w": 17.0, "e": 12.0, "r": 100.0}
    c.on_basic_attack(1.0)
    assert abs(c.cooldowns_remaining["q"] - 7.0 * 0.85) < 1e-9
    assert abs(c.cooldowns_remaining["w"] - 17.0 * 0.85) < 1e-9
    assert abs(c.cooldowns_remaining["e"] - 12.0 * 0.85) < 1e-9
    assert c.cooldowns_remaining["r"] == 100.0  # 궁(R)은 기본스킬 아님 → 불변
    c.on_basic_attack(2.0)                        # 누적(평타당 ×0.85)
    assert abs(c.cooldowns_remaining["q"] - 7.0 * 0.85 * 0.85) < 1e-9


def test_no_navori_hook_is_noop():
    c = CogMaw(level=13); c.init_combat_state()
    before = {"q": 7.0, "w": 17.0, "e": 12.0, "r": 100.0}
    c.cooldowns_remaining = dict(before)
    c.on_basic_attack(1.0)
    assert c.cooldowns_remaining == before  # 나보리 없으면 no-op


def test_engine_calls_on_basic_attack_per_attack():
    """엔진 통합: run_simulation 이 평타마다 champion.on_basic_attack 을 호출하는지(나보리 쿨감 배선)."""
    c = CogMaw(level=11, w_level=5, q_level=2, e_level=1, r_level=1)
    c.set_rune(LethalTempo()); c.set_sub_rune(CutDown())
    c.add_item(create_item_from_key("berserker"))
    c.add_item(create_item_from_key("guinsoo"))
    calls = [0]
    orig = c.on_basic_attack
    def spy(t):
        calls[0] += 1
        return orig(t)
    c.on_basic_attack = spy
    run_simulation(c, Target(hp=1700, armor=50, magic_resist=25), verbose=False)
    assert calls[0] > 0  # 평타마다 1회 호출됨


if __name__ == "__main__":
    for nm, f in sorted(globals().items()):
        if nm.startswith("test_") and callable(f):
            f(); print(f"PASS {nm}")
    print("ALL PASS")
