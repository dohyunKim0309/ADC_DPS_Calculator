"""Dusk and Dawn (황혼과 새벽) — 주문검 + 온힛 1회 추가(가산). [H-DAWN-1]
Run: .venv/bin/python -m tests.test_dusk_dawn
"""
from adc_sim.champion import CogMaw, Target
from adc_sim.data.items_registry import create_item_from_key


def test_data_injection():
    d = create_item_from_key("dawn")
    assert d.name == "Dusk and Dawn"
    assert d.cost == 3100
    assert d.stats["ap"] == 60 and abs(d.stats["as"] - 0.20) < 1e-9 and d.stats["cdr"] == 20


def test_spellblade_arm_consume_and_cooldown():
    d = create_item_from_key("dawn")

    class C:  # on_hit/get_extra_onhit_applications 가 읽는 속성만 가진 스텁
        pass
    c = C(); c.base_attack_ad = 100.0; c.total_ap = 200.0

    # 초기: 비활성
    assert d.is_spellblade_active is False
    assert d.get_extra_onhit_applications(c) == 0
    assert d.on_hit(None, c) == (0, 0, 0, 0)

    # 스킬 시전 → arm
    d.on_spell_cast(c, 1.0)
    assert d.is_spellblade_active is True
    assert d.get_extra_onhit_applications(c) == 1

    # 강화 평타 → 버스트 1회 소비. 마법 = 100*0.75 + 200*0.10 = 95
    p, m, tb, to = d.on_hit(None, c)
    assert (p, tb, to) == (0, 0, 0) and abs(m - 95.0) < 1e-9
    assert d.is_spellblade_active is False
    assert d.get_extra_onhit_applications(c) == 0

    # 2초 내부쿨: 1.5초 재시전은 재장전 안 됨, 3.0초(>=1.0+2.0)는 재장전
    d.on_spell_cast(c, 1.5)
    assert d.is_spellblade_active is False
    d.on_spell_cast(c, 3.0)
    assert d.is_spellblade_active is True


def test_extra_onhit_is_additive():
    """강화 평타 = 기본 온힛 1회 + 주문검 추가 1회 → W 온힛이 2회 적용 + 버스트 1회.
    구인수 없이 proc_count=1 로 가산을 격리 검증(구인수와의 합산도 +1 의미 동일)."""
    tgt = Target(hp=2000, armor=40, magic_resist=30)

    def run(armed):
        c = CogMaw(level=11, w_level=5); c.init_combat_state()
        c.add_item(create_item_from_key("dawn"))
        c.w_active = True; c.w_end_time = 999.0   # W 온힛을 결정적 '1회분' 단위로 사용
        if armed:
            c.cast_spell(1.0)                      # 주문검 arm
        # 증폭/그림자불꽃 없음 → 반환 마법온힛(4번째) == 내부 합산
        _, _, _, m_onhit, _, _ = c.get_one_hit_damage(tgt, 1.0)
        return c, m_onhit

    c0, m_not = run(armed=False)
    W = (c0.W_PCT[c0.w_level - 1] + 0.00015 * c0.total_ap) * tgt.max_hp
    burst = 0.75 * c0.base_attack_ad + 0.10 * c0.total_ap

    # 비활성: 적용 1회 → W 1회분
    assert abs(m_not - W) < 1e-6, (m_not, W)
    # 활성: 적용 2회(가산 +1) → W 2회분 + 버스트 1회
    _, m_armed = run(armed=True)
    assert abs(m_armed - (2 * W + burst)) < 1e-6, (m_armed, 2 * W + burst)
    # 차이 = 정확히 온힛 1회분(W) + 버스트
    assert abs((m_armed - m_not) - (W + burst)) < 1e-6


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_") and callable(f):
            f(); print(f"PASS {n}")
    print("ALL PASS")
