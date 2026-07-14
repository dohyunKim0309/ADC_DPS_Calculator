"""C44 증폭 스코프 검증 — Vayne: 기본 평타 AA 물리만 증폭, W 은화살·Q 추가딜 미증폭.

사용자 확정 2026-07-14: C44 의 %증폭은 오로지 "기본 평타 대미지" 에만 적용된다.
- ✅ 평타 본체(phys_base = total_ad × crit_blend) — 이미 base 에서 적용.
- ❌ W 은화살 고정피해 — mod_factor(대미지증가) 만 적용, C44 미적용.
- ❌ Q 추가딜 (total_ad × ratio) — mod_factor 만 적용, C44 미적용.
- ❌ 아이템/룬 온힛 — mod_factor 만 적용 (기존 규약).
"""
from adc_sim.champion import Vayne, Target
from adc_sim.data.items_registry import create_item_from_key


def _get_dmg(v, target):
    """반환: dict(phys_base=…, p_onhit=…, m_onhit=…, pt_true=…) 로 성분 분리."""
    p_base, m_base, p_onhit, m_onhit, pt_base, pt_onhit = v.get_one_hit_damage(target)
    return {
        "phys_base": p_base, "m_base": m_base,
        "p_onhit": p_onhit, "m_onhit": m_onhit,
        "pt_true": pt_base + pt_onhit,
    }


def test_c44_amplifies_only_basic_aa_not_silverbolts():
    """C44 유무만 다르게 세팅 → 은화살 버스트(pt_true) 는 완전 동일해야 함."""
    def build(with_c44):
        v = Vayne(level=11, w_level=5)  # W5: 300 true on 3000 HP 대상
        v.init_combat_state()
        v.range = 500  # C44 최대 증폭 사거리
        if with_c44:
            v.add_item(create_item_from_key("c44"))
        return v
    target = Target(hp=3000, armor=0, magic_resist=0, bonus_hp=1500)
    v_no, v_yes = build(False), build(True)
    # 3번째 평타에서 은화살 버스트
    _get_dmg(v_no, target); _get_dmg(v_no, target)
    _get_dmg(v_yes, target); _get_dmg(v_yes, target)
    burst_no = _get_dmg(v_no, target)["pt_true"]
    burst_yes = _get_dmg(v_yes, target)["pt_true"]
    assert burst_no > 0 and burst_yes > 0, "3번째 평타에서 은화살 발동 예상"
    assert abs(burst_no - burst_yes) < 1e-6, (
        f"C44 은 은화살 버스트를 증폭하면 안 됨: no_c44={burst_no:.3f}, "
        f"with_c44={burst_yes:.3f}")


def test_c44_amplifies_only_basic_aa_not_q_bonus():
    """C44 %증폭이 Q 추가딜에 안 걸리는지 격리 검증.

    C44 는 AD·크리 스탯도 주므로 "C44 유무" 비교는 스탯 기여가 섞임.
    → C44 를 장착한 채 %증폭만 0/최대로 토글해서 Q 추가딜 델타를 관찰.
    C44 %증폭이 Q 에 안 걸리면 두 상태의 Q 추가딜이 완전 동일해야 함.
    """
    def q_bonus_at_range(rng):
        # 같은 챔프에 C44 장착, range 만 바꿔 %증폭을 0 (range=0) / 최대 (range=500) 로 토글
        v_plain = Vayne(level=11, q_level=5, w_level=5)
        v_plain.init_combat_state()
        v_plain.range = rng
        v_plain.add_item(create_item_from_key("c44"))
        p_plain = _get_dmg(v_plain, target)["phys_base"]

        v_emp = Vayne(level=11, q_level=5, w_level=5)
        v_emp.init_combat_state()
        v_emp.range = rng
        v_emp.add_item(create_item_from_key("c44"))
        v_emp.q_empowered = True
        p_emp = _get_dmg(v_emp, target)["phys_base"]
        return p_emp - p_plain

    target = Target(hp=99999, armor=0, magic_resist=0, bonus_hp=0)
    q_amp_zero = q_bonus_at_range(0)      # C44 %증폭 = 0%
    q_amp_max = q_bonus_at_range(500)     # C44 %증폭 = 10%(최대)
    assert q_amp_zero > 0 and q_amp_max > 0
    assert abs(q_amp_zero - q_amp_max) < 1e-6, (
        f"C44 %증폭이 Q 추가딜에 걸리면 안 됨: amp0={q_amp_zero:.3f}, "
        f"amp10%={q_amp_max:.3f}")


def test_c44_does_amplify_basic_aa():
    """(대조군) C44 는 평타 본체(phys_base) 는 실제로 증폭한다 — with_c44 > no_c44."""
    def build(with_c44):
        v = Vayne(level=11)
        v.init_combat_state()
        v.range = 500
        if with_c44:
            v.add_item(create_item_from_key("c44"))
        return v
    target = Target(hp=99999, armor=0, magic_resist=0, bonus_hp=0)
    p_no = _get_dmg(build(False), target)["phys_base"]
    p_yes = _get_dmg(build(True), target)["phys_base"]
    # C44 는 AD 55·크리 25% 추가 → phys_base 는 스탯 + 증폭 둘 다로 상승
    # 증폭만 격리하려면 스탯 차감이 복잡해지므로 여기선 "with 가 더 크다" 만 확인.
    assert p_yes > p_no, (
        f"C44 장착 시 평타 본체 증가 예상: no_c44={p_no:.3f}, with_c44={p_yes:.3f}")
