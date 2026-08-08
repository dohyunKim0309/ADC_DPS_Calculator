"""Task 4: 베인 R 결전 — 고정 추가AD 버프·Q 쿨감·만료원복·마나 80."""
from adc_sim.champion import Vayne, Target


def test_r_adds_bonus_ad_on_cast():
    v = Vayne(level=16, r_level=3)   # R3 → +65 AD
    v.init_combat_state()
    ad_before = v.total_ad
    v._cast_r(time=0.0)
    assert abs(v.total_ad - (ad_before + 65.0)) < 1e-6
    assert v.r_active is True


def test_r_reduces_q_cooldown():
    v = Vayne(level=16, q_level=5, r_level=3)   # Q5 쿨 2.0, R3 CDR 50%
    v.init_combat_state()
    cd_no_r = v._q_cooldown()          # R 비활성
    v._cast_r(time=0.0)
    cd_with_r = v._q_cooldown()        # R 활성 → ×0.5
    assert abs(cd_with_r - cd_no_r * 0.5) < 1e-6


def test_r_expires_and_reverts_bonus_ad():
    v = Vayne(level=16, r_level=3)     # 지속 12s
    v.init_combat_state()
    target = Target(hp=99999, armor=0, magic_resist=0, bonus_hp=0)
    ad_before = v.total_ad
    v._cast_r(time=0.0)
    assert v.total_ad > ad_before
    # 지속(12s) 경과 → 만료 원복
    v.advance_combat_time(delta_time=13.0, current_time=13.0, target=target)
    assert v.r_active is False
    assert abs(v.total_ad - ad_before) < 1e-6


def test_r_mana_cost_and_gate():
    v = Vayne(level=16, r_level=3)
    v.init_combat_state()
    assert v._cost("r") == 80.0
    v.current_mana = 50.0
    assert v._can_cast_skill("r") is False


def test_r_cast_at_t0_via_skill_plan():
    """Q를 끄고 t=0 R 추가 AD 자체가 DPS를 높이는지 검증한다."""
    from adc_sim.engine import run_simulation
    from adc_sim.runes import LethalTempo, CutDown
    from adc_sim.data.items_registry import create_item_from_key
    def _run(r_on):
        v = Vayne(level=16, q_level=5, w_level=5, r_level=3)
        v.set_rune(LethalTempo()); v.set_sub_rune(CutDown())
        v.add_item(create_item_from_key("botrk"))
        t = Target(hp=2500, armor=60, magic_resist=40, bonus_hp=1000)
        plan = {"manual_casts": [(0.0, "r")] if r_on else [],
                # 이 테스트는 R의 AD 기여만 격리한다.
                "auto_cast": {"q": False, "r": False}, "auto_order": ["q"]}
        return run_simulation(v, t, verbose=False, skill_plan=plan, respawn_to_full_kills=2)[1]
    assert _run(True) > _run(False)   # R 추가AD 로 DPS 증가
