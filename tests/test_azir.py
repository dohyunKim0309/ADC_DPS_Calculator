"""Azir — 병사(W) 평타 대체 + 충전/수명 이벤트 + Q/E/R + AP 아이템 스킬 효과.
[검증: 나무위키 2026-08-27 + LoL Wiki V26.16 + CDragon bin 3소스] spec 2026-08-27-azir-design.md
Run: .venv/bin/python -m pytest tests/test_azir.py -q
"""
import pytest

from adc_sim.champion import Azir, Target
from adc_sim.engine import run_simulation
from adc_sim.runes import LethalTempo, PressTheAttack, CutDown
from adc_sim.data.items_registry import create_item_from_key
from adc_sim.data.items_data import ITEMS, pen_rule_ok, MAGIC_PEN_EXCLUSIVE
from adc_sim.simulations import azir as azir_sim


def _azir(level=13, **kw):
    a = Azir(level=level, q_level=5, w_level=5, e_level=3, r_level=2, **kw)
    a.init_combat_state()
    return a


def test_azir_base_stats():
    """AD 56(+3.5), AS 0.625(ratio 0.694, +5%/lvl), 사거리 525, 마나 320(+40), mp5 8(+0.8)."""
    a = Azir(level=1)
    assert a.base_ad == 56 and abs(a.ad_growth - 3.5) < 1e-9
    assert abs(a.base_as - 0.625) < 1e-9 and abs(a.as_ratio - 0.694) < 1e-9 and abs(a.as_growth - 5.0) < 1e-9
    assert a.range == 525
    assert a.base_mana == 320 and a.mana_growth == 40
    assert abs(a.base_mp5 - 8.0) < 1e-9 and abs(a.mp5_growth - 0.8) < 1e-9


def test_w_damage_level_bonus_and_soldier_multiplier():
    """W = base + (lv≥10: 8/lv) + AP계수. 2번째 병사부터 25%: 1/1.25/1.5."""
    a9 = _azir(level=9, fixed_soldiers=1)
    assert abs(a9.w_damage(1) - 110.0) < 1e-9                 # AP 0, lv9 → 레벨 보너스 0
    a13 = _azir(level=13, fixed_soldiers=1)
    a13.bonus_ap = 100.0
    single = 110.0 + 32.0 + 0.65 * 100.0                     # lv13 → +8×4
    assert abs(a13.w_damage(1) - single) < 1e-9
    assert abs(a13.w_damage(2) - single * 1.25) < 1e-9
    assert abs(a13.w_damage(3) - single * 1.50) < 1e-9
    assert Azir.W_RECHARGE == [12.0, 10.5, 9.0, 7.5, 6.0] and Azir.W_MAX_CHARGES == 2
    assert Azir.W_AP == [0.35, 0.425, 0.50, 0.575, 0.65]


def test_soldier_attack_replaces_aa_and_onhit_is_halved():
    """병사 공격: 물리 기본 0, 마법 기본 = W, 아이템 온힛(내셔) ×0.5."""
    a = _azir(fixed_soldiers=1)
    a.add_item(create_item_from_key("nashor"))
    t = Target(hp=3000, armor=100, magic_resist=50)
    p_base, m_base, p_on, m_on, tb, to = a.get_one_hit_damage(t, 0.0)
    assert p_base == 0.0 and tb == 0.0 and to == 0.0
    assert abs(m_base - a.w_damage(1)) < 1e-9
    assert abs(m_on - 0.5 * (15.0 + 0.15 * a.total_ap)) < 1e-9


def test_rune_onhit_factor_pta_full_lt_half():
    """PtA 3타 폭발 100%, LT 풀스택 온힛 50% — 사용자 확정 2026-08-27 (둘 다 적응형 → AP 빌드라 마법)."""
    t = Target(hp=9999, armor=50, magic_resist=30)
    a = _azir(fixed_soldiers=1); a.bonus_ap = 100.0
    a.set_rune(PressTheAttack())
    for _ in range(2):
        a.get_one_hit_damage(t, 0.0)
    _, _, _, m_on, _, _ = a.get_one_hit_damage(t, 0.0)     # 3타: 폭발 40~160(lv13 → 124.7) ×1.0
    # 폭발 직후 PtA 활성(8% 증폭)이 같은 타격의 온힛에도 곱해지는 것은 베이스 엔진과 동일 규약.
    expected = (40 + 120 * (13 - 1) / 17) * 1.08
    assert abs(m_on - expected) < 1e-9
    b = _azir(fixed_soldiers=1); b.bonus_ap = 100.0
    b.set_rune(LethalTempo())
    for _ in range(6):
        b.get_one_hit_damage(t, 0.0)
    _, _, _, m_on_lt, _, _ = b.get_one_hit_damage(t, 0.0)
    _, rm = b.rune.get_on_hit_damage(t, b)
    assert abs(m_on_lt - 0.5 * rm) < 1e-9 and rm > 0


def test_w_charges_and_soldier_lifetime_events():
    """t=0: W(충전 2→1) + E(충돌 → 충전 +1=2). 1.5s 두 번째 W. 10s 후 첫 병사 만료. 충전 재생 6s×스킬가속."""
    a = _azir()
    a.set_rune(LethalTempo())
    a.init_combat_state({"manual_casts": [], "auto_cast": {"q": False, "w": True, "e": True, "r": False}})
    t = Target(hp=99999, armor=50, magic_resist=30)
    ev = a.pop_due_skill_events(0.0, t)
    assert [e[0] for e in ev] == ["w"]                                   # 시전 락아웃: E 는 같은 시각에 못 나감
    assert len(a.soldiers) == 1 and a.w_charges == 1 and abs(a.w_charge_ready_at - 6.0) < 1e-9
    assert abs(a.get_time_to_next_skill_event(0.0) - 0.25) < 1e-9       # W 시전 0.25s 뒤 E
    a.advance_combat_time(0.25, 0.25, t)
    assert [e[0] for e in a.pop_due_skill_events(0.25, t)] == ["e"]
    assert a.w_charges == 2 and a.w_charge_ready_at is None              # 충돌 → 충전 +1
    a.advance_combat_time(0.3, 0.55, t)
    assert abs(a.get_time_to_next_skill_event(0.55) - 0.95) < 1e-9      # W 쿨 1.5s(t=0 기준)
    a.advance_combat_time(0.95, 1.5, t)
    a.pop_due_skill_events(1.5, t)
    assert len(a.soldiers) == 2 and a.w_charges == 1
    assert abs(a.w_charge_ready_at - (1.5 + 6.0)) < 1e-9                # 스킬가속 0 → 6s
    a.advance_combat_time(3.0, 4.5, t)
    a.pop_due_skill_events(4.5, t)                                       # 남은 충전 1 → 3번째 병사(W-E-W-W)
    assert len(a.soldiers) == 3 and a.w_charges == 0
    assert abs(a.w_charge_ready_at - 7.5) < 1e-9                         # 타이머는 1.5s 시작분 유지
    assert abs(a.get_time_to_next_state_event(4.5) - 3.0) < 1e-9        # 충전 7.5s 가 첫 상태 이벤트
    a.advance_combat_time(3.0, 7.5, t)
    assert a.w_charges == 1 and abs(a.w_charge_ready_at - 13.5) < 1e-9  # 아직 <2 → 타이머 재시작
    a.pop_due_skill_events(7.5, t)                                       # 4번째 병사
    assert len(a.soldiers) == 4 and a.w_charges == 0
    a.advance_combat_time(2.5 + 1e-6, 10.0 + 1e-6, t)                    # t=0 병사 만료
    assert len(a.soldiers) == 3


def test_w_haste_applies_to_recharge():
    """[H-AZIR-1] 재충전 12→6s 에 스킬가속 적용: AH 20 → 6×100/120 = 5s."""
    a = _azir()
    a.ability_haste = 20.0
    a.init_combat_state({"manual_casts": [], "auto_cast": {"q": False, "w": True, "e": False, "r": False}})
    t = Target(hp=99999, armor=50, magic_resist=30)
    a.pop_due_skill_events(0.0, t)
    assert abs(a.w_charge_ready_at - 5.0) < 1e-9


def test_liandry_dot_ticks_and_suffering_amp():
    """리안드리: 병사 타격 시 0.5s 마다 최대체력 1% × 6틱, 고난 2%/s ≤ 6%."""
    a = _azir(fixed_soldiers=1)
    a.add_item(create_item_from_key("liandry"))
    a.init_combat_state({"auto_cast": {"q": False, "w": False, "e": False, "r": False}})   # E 자동시전이 DoT 를 갱신하지 않도록
    t = Target(hp=2000, armor=50, magic_resist=0)
    a.get_one_hit_damage(t, 0.0)                    # 병사 타격 → DoT 등록
    assert "liandry" in a.dots
    ticks = []
    for step in range(1, 8):
        tm = 0.5 * step
        a.advance_combat_time(0.5, tm, t)
        ticks += [e for e in a.pop_due_skill_events(tm, t) if e[0] == "liandry"]
    assert len(ticks) == 6
    amp0 = 1.0 + a.inventory[0].get_damage_modifier(t, a)   # 시각은 마지막 advance 시점(3.5s → 6%)
    assert abs(amp0 - 1.06) < 1e-9
    assert all(abs(e[2] - 20.0 * (1.0 + min(0.06, 0.02 * int(0.5 * i)))) < 1e-6 for i, e in enumerate(ticks, start=1))


def test_ludens_echo_on_soldier_hit_with_cooldown():
    """루덴: 병사 타격도 스킬 효과 → (75+5%AP)×2, 12s 쿨."""
    a = _azir(fixed_soldiers=1); a.bonus_ap = 200.0
    a.add_item(create_item_from_key("ludens"))
    ap = a.total_ap
    t = Target(hp=9999, armor=50, magic_resist=0)
    _, m1, _, _, _, _ = a.get_one_hit_damage(t, 0.0)
    _, m2, _, _, _, _ = a.get_one_hit_damage(t, 1.0)
    _, m3, _, _, _, _ = a.get_one_hit_damage(t, 12.0)
    echo = (75.0 + 0.05 * ap) * 2.0
    assert abs(m1 - (a.w_damage(1) + echo)) < 1e-6
    assert abs(m2 - a.w_damage(1)) < 1e-6
    assert abs(m3 - (a.w_damage(1) + echo)) < 1e-6


def test_quest_bonus_and_tier3_boots_resolution():
    """[H-AZIR-4] 퀘스트 완료: 총AP ×1.08(라바돈과 곱). 코어2 부터 마관신→주문투척자."""
    a = Azir(level=13, quest_complete=True)
    a.add_item(create_item_from_key("rabadon"))
    assert abs(a.total_ap - 130.0 * 1.30 * 1.08) < 1e-9
    b = Azir(level=13, quest_complete=False)
    b.add_item(create_item_from_key("rabadon"))
    assert abs(b.total_ap - 130.0 * 1.30) < 1e-9
    assert azir_sim.resolve_boots_for_core("sorcerer", 1) == "sorcerer"
    assert azir_sim.resolve_boots_for_core("sorcerer", 2) == "spellslinger"
    assert ITEMS["spellslinger"]["stats"] == {"magic_pen_flat": 20, "magic_pen_percent": 0.08, "ms": 45}


def test_cryptbloom_void_exclusive():
    assert "cryptbloom" in MAGIC_PEN_EXCLUSIVE
    assert not pen_rule_ok(("nashor", "void", "cryptbloom"))
    assert pen_rule_ok(("nashor", "cryptbloom", "rabadon"))


def test_simulate_core_path_positive_and_control_in_pool():
    """컨트롤 4코어 DPS>0, 코어 증가 시 DPS 단조 증가, 컨트롤 아이템이 각 슬롯 풀에 존재."""
    prev = 0.0
    for tier in range(1, 5):
        dps, gold = azir_sim.simulate_azir_core_path(list(azir_sim.CONTROL_PATH), tier, keystone_cls=PressTheAttack)
        assert dps > prev and gold > 0
        prev = dps
    for slot, key in enumerate(azir_sim.CONTROL_PATH, start=1):
        assert key in azir_sim.AZIR_CORE_CANDIDATES[slot]


def test_full_sim_lichbane_spellblade_arms_on_w_and_halved():
    """리치베인: W(스킬) 시전 후 다음 병사 타격에 (75%기본AD+45%AP) 마법 온힛 ×0.5, 준비 중 공속 +50%."""
    a = _azir()
    a.add_item(create_item_from_key("lichbane"))
    a.init_combat_state({"manual_casts": [], "auto_cast": {"q": False, "w": True, "e": False, "r": False}})
    t = Target(hp=99999, armor=50, magic_resist=0)
    a.pop_due_skill_events(0.0, t)                                  # W → 주문검 arm
    assert a.inventory[0].is_spellblade_active
    as_armed = a.get_total_bonus_as_percent()
    _, _, _, m_on, _, _ = a.get_one_hit_damage(t, 0.3)
    assert abs(m_on - 0.5 * (0.75 * a.base_attack_ad + 0.45 * a.total_ap)) < 1e-9
    assert abs(as_armed - a.get_total_bonus_as_percent() - 0.5) < 1e-9


def test_existing_champions_untouched_smoke():
    """베이스 Champion 무수정 확인: 기존 챔프(Vayne) 컨트롤 DPS 는 회귀 스냅샷(test_regression_diff) 이 담당.
    여기선 Azir 전용 훅이 다른 챔피언 인벤토리에 영향 없음을 스모크로 확인."""
    from adc_sim.champion import Ashe
    ashe = Ashe(level=13)
    ashe.add_item(create_item_from_key("liandry"))    # on_spell_effect 는 Ashe 가 호출하지 않음
    ashe.init_combat_state()
    assert not hasattr(ashe, "apply_dot")
