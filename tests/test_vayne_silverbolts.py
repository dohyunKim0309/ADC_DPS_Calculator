"""Task 2: 베인 W 은화살 — 3타마다 max(floor,%maxHP) 고정피해, 증폭 O·경감 X, 구인수 2배 X."""
from adc_sim.champion import Vayne, Target
from adc_sim.runes import CutDown
from adc_sim.data.items_registry import create_item_from_key


def _true_component(champ, target, time=0.0):
    """get_one_hit_damage 6튜플의 고정피해 합(true_base+true_onhit) 반환."""
    p_base, m_base, p_onhit, m_onhit, true_base, true_onhit = champ.get_one_hit_damage(target, time)
    return true_base + true_onhit


def test_silverbolts_every_third_hit():
    v = Vayne(level=11, w_level=5)          # W5 → 10% maxHP, floor 110
    v.init_combat_state()
    target = Target(hp=3000, armor=0, magic_resist=0, bonus_hp=1500)
    # 평타 1,2 = 0, 평타 3 = 발동, 4,5 = 0, 6 = 발동
    trues = [_true_component(v, target) for _ in range(6)]
    assert trues[0] == 0 and trues[1] == 0
    assert trues[2] > 0
    assert trues[3] == 0 and trues[4] == 0
    assert trues[5] > 0


def test_silverbolts_uses_max_of_floor_and_pct():
    # 고HP 대상: 10%·3000 = 300 > floor 110 → 300
    v = Vayne(level=11, w_level=5)
    v.init_combat_state()
    big = Target(hp=3000, armor=0, magic_resist=0, bonus_hp=1500)
    v.get_one_hit_damage(big); v.get_one_hit_damage(big)
    assert abs(_true_component(v, big) - 300.0) < 1e-6
    # 저HP 대상: 10%·500 = 50 < floor 110 → 110
    v2 = Vayne(level=11, w_level=5)
    v2.init_combat_state()
    small = Target(hp=500, armor=0, magic_resist=0, bonus_hp=0)
    v2.get_one_hit_damage(small); v2.get_one_hit_damage(small)
    assert abs(_true_component(v2, small) - 110.0) < 1e-6


def test_silverbolts_amplified_by_damage_increase_not_mitigation():
    # CutDown(고HP 8%) 활성 → 은화살 300 × 1.08 = 324. 방어력은 은화살에 영향 없어야(경감 우회).
    v = Vayne(level=11, w_level=5)
    v.set_sub_rune(CutDown())
    v.init_combat_state()
    target = Target(hp=3000, armor=200, magic_resist=200, bonus_hp=1500)  # 방어 높아도 true 불변
    v.get_one_hit_damage(target); v.get_one_hit_damage(target)
    assert abs(_true_component(v, target) - 324.0) < 1e-6


def test_silverbolts_burst_amp_not_doubled_by_guinsoo():
    # 구인수 미풀스택(1~3번 평타 stack 0→1→2→3, 4미만) 구간에선 apps=1 이라
    # 3번째 평타 버스트 = 1회분(=300, 증폭없음). 버스트 대미지 자체는 구인수로 2배가 되지 않음.
    v = Vayne(level=11, w_level=5)
    v.init_combat_state()
    v.add_item(create_item_from_key("guinsoo"))
    target = Target(hp=3000, armor=0, magic_resist=0, bonus_hp=1500)
    v.get_one_hit_damage(target); v.get_one_hit_damage(target)
    assert abs(_true_component(v, target) - 300.0) < 1e-6


def test_silverbolts_accelerated_by_guinsoo_phantom_hit():
    """구인수 풀스택(4) 이후 팬텀히트가 은화살 스택을 가속. [H-VAYNE-W-GUI]

    사용자 명시 패턴(풀스택 뒤 sb=0 시작):
      평(1)  평(2)  평(3버스트→1)  평(2)  평(3버스트)  평(1,2)
    → apps 시퀀스 = 1,1,2,1,1,2 (팬텀히트 = 3평마다), 버스트는 3번째·5번째 평타에서만 발동.
    """
    v = Vayne(level=11, w_level=5)
    v.init_combat_state()
    gui = create_item_from_key("guinsoo")
    v.add_item(gui)
    # 구인수 풀스택 + 카운터 리셋 상태로 셋업(램프 스킵 — 사용자 패턴 재현).
    gui.stack = 4
    gui.full_stack_attack_counter = 0
    target = Target(hp=3000, armor=0, magic_resist=0, bonus_hp=1500)  # 은화살 300/burst

    trues = [_true_component(v, target) for _ in range(6)]
    # 버스트는 평타 3(2→3버스트) 과 평타 5(2→3버스트) 에서만.
    assert trues[0] == 0, f"attack1 should not burst, got {trues[0]}"
    assert trues[1] == 0, f"attack2 should not burst, got {trues[1]}"
    assert abs(trues[2] - 300.0) < 1e-6, f"attack3 (phantom→burst→+1) expected 300, got {trues[2]}"
    assert trues[3] == 0, f"attack4 should not burst, got {trues[3]}"
    assert abs(trues[4] - 300.0) < 1e-6, f"attack5 (burst) expected 300, got {trues[4]}"
    assert trues[5] == 0, f"attack6 (phantom, sb 0→1→2, no burst) got {trues[5]}"
    # 6평 뒤 sb 스택은 정확히 2 (다음 평타가 3→버스트 예정).
    assert v.sb_stacks == 2, f"sb_stacks after 6 attacks expected 2, got {v.sb_stacks}"


def test_smoke_autos_plus_w_runs():
    from adc_sim.engine import run_simulation
    from adc_sim.runes import LethalTempo
    v = Vayne(level=11, w_level=5, q_level=5, r_level=2)
    v.set_rune(LethalTempo()); v.set_sub_rune(CutDown())
    v.add_item(create_item_from_key("botrk"))
    target = Target(hp=2000, armor=50, magic_resist=30, bonus_hp=500)
    _, dps, kill_time = run_simulation(v, target, verbose=False, respawn_to_full_kills=1)
    assert dps > 0 and kill_time > 0
