"""Task 3: 베인 Q 구르기 — 강화 평타(총AD ratio·치명반영)·평타리셋·마나게이트."""
from adc_sim.champion import Vayne, Target, ANIM_CANCEL_CLIP


def test_q_auto_enabled_by_default_guards_both_default_lines():
    # Task3 회귀 가드: Q 오토 기본 True — __init__ 과 init_combat_state(_defaults) 두 라인 모두.
    # 어느 한 라인이라도 False 로 되돌아가면 이 테스트가 실패해야 한다.
    fresh = Vayne(level=11, q_level=5)
    assert fresh.auto_skill_enabled["q"] is True          # __init__ 기본
    fresh.init_combat_state()                              # skill_plan 미지정 → _defaults 적용
    assert fresh.auto_skill_enabled["q"] is True           # init_combat_state 기본


def test_empowered_attack_scales_p_base():
    v = Vayne(level=11, q_level=5, w_level=5)   # Q5 → ratio 1.15
    v.init_combat_state()
    target = Target(hp=99999, armor=0, magic_resist=0, bonus_hp=0)  # 안 죽게 큰 HP
    # 비강화 평타 물리
    v.q_empowered = False
    p_normal = v.get_one_hit_damage(target)[0]
    # 강화 평타 물리(같은 상태에서 arm) — 새 인스턴스로 sb 카운터 영향 배제
    v2 = Vayne(level=11, q_level=5, w_level=5)
    v2.init_combat_state()
    v2.q_empowered = True
    p_emp = v2.get_one_hit_damage(target)[0]
    assert abs(p_emp - p_normal * (1.0 + 1.15)) < 1e-6


def test_empowered_flag_consumed_after_one_attack():
    v = Vayne(level=11, q_level=5)
    v.init_combat_state()
    target = Target(hp=99999, armor=0, magic_resist=0, bonus_hp=0)
    v.q_empowered = True
    v.get_one_hit_damage(target)          # 소비
    assert v.q_empowered is False
    p_after = v.get_one_hit_damage(target)[0]
    v2 = Vayne(level=11, q_level=5); v2.init_combat_state()
    p_plain = v2.get_one_hit_damage(target)[0]
    # sb 카운터 차이 없는 물리 base 만 비교(둘 다 비강화) → 근사 동일
    assert abs(p_after - p_plain) < 1e-6


def test_q_auto_casts_and_resets_attack_interval():
    from adc_sim.engine import run_simulation
    from adc_sim.runes import LethalTempo, CutDown
    v = Vayne(level=11, q_level=5, w_level=5, r_level=2)
    v.set_rune(LethalTempo()); v.set_sub_rune(CutDown())
    target = Target(hp=3000, armor=50, magic_resist=30, bonus_hp=1500)
    # skill_plan 미지정 → Q auto 기본 활성
    _, dps, _ = run_simulation(v, target, verbose=False, respawn_to_full_kills=1)
    assert dps > 0
    # Q 리셋 클리핑 상수 노출 확인
    assert ANIM_CANCEL_CLIP == 0.33


def test_q_mana_gate_blocks_when_insufficient():
    v = Vayne(level=11, q_level=5)
    v.init_combat_state()
    v.current_mana = 10.0            # Q 30 미만
    assert v._can_cast_skill("q") is False
    v.current_mana = 30.0
    assert v._can_cast_skill("q") is True


def test_q_dps_higher_than_autos_only():
    from adc_sim.engine import run_simulation
    from adc_sim.runes import LethalTempo, CutDown
    from adc_sim.data.items_registry import create_item_from_key
    def _run(q_on):
        v = Vayne(level=13, q_level=5, w_level=5, r_level=2)
        v.set_rune(LethalTempo()); v.set_sub_rune(CutDown())
        v.add_item(create_item_from_key("botrk"))
        v.add_item(create_item_from_key("pd"))
        t = Target(hp=2500, armor=60, magic_resist=40, bonus_hp=1000)
        plan = {"auto_cast": {"q": q_on, "r": False}, "auto_order": ["q"]}
        return run_simulation(v, t, verbose=False, skill_plan=plan, respawn_to_full_kills=2)[1]
    assert _run(True) > _run(False)   # Q 강화가 DPS 증가
