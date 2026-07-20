"""PtA(집중공격) 룬 선택 회귀 — 8% 증폭이 은화살 고정딜에 적용됨을 잠금.
동시에 CoupDeGrace(최후의 일격) 도 같은 채널로 증폭되는지 검증(HP≤40%)."""
from adc_sim.champion import Vayne, Target
from adc_sim.runes import PressTheAttack, CutDown, CoupDeGrace
from adc_sim.simulations.vayne import simulate_vayne_core_path, CONTROL_PATH


def _true_component(champ, target, time=0.0):
    p_base, m_base, p_onhit, m_onhit, t_base, t_onhit = champ.get_one_hit_damage(target, time)
    return t_base + t_onhit


def test_pta_active_amplifies_silverbolts():
    """PtA 3스택 활성 + CutDown 고HP → 은화살 300 * (1+0.08+0.08) = 348."""
    v = Vayne(level=11, w_level=5)
    v.set_rune(PressTheAttack())
    v.set_sub_rune(CutDown())
    v.init_combat_state()
    v.rune.stacks = 3            # PtA 활성 강제(3타 도달 뒤 상태)
    v.rune.active = True
    target = Target(hp=3000, armor=0, magic_resist=0, bonus_hp=1500)
    v.get_one_hit_damage(target); v.get_one_hit_damage(target)  # 은화살 스택 0→1→2
    assert abs(_true_component(v, target) - 348.0) < 1e-6


def test_coupdegrace_low_hp_amplifies_silverbolts():
    """CoupDeGrace(HP≤40%) → 은화살 300 * 1.08 = 324."""
    v = Vayne(level=11, w_level=5)
    v.set_sub_rune(CoupDeGrace())
    v.init_combat_state()
    target = Target(hp=3000, armor=0, magic_resist=0, bonus_hp=1500)
    target.current_hp = target.max_hp * 0.30  # 30% HP → CoupDeGrace active
    v.get_one_hit_damage(target); v.get_one_hit_damage(target)
    assert abs(_true_component(v, target) - 324.0) < 1e-6


def test_simulate_vayne_core_path_accepts_pta_keystone():
    """simulate_vayne_core_path 가 keystone_cls=PressTheAttack 을 받아 DPS>0 을 낸다(스모크)."""
    dps, gold = simulate_vayne_core_path(CONTROL_PATH, 2, keystone_cls=PressTheAttack)
    assert dps > 0 and gold > 0
