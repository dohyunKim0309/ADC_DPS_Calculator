"""베인 은화살 팬텀히트 픽스([H-VAYNE-W-GUI])의 CTRL DPS 변화 회귀 기록.

**배경**
- 픽스: `Vayne.get_one_hit_damage`에서 `sb_stacks += 1` 단발 → `_last_onhit_applications`
  만큼 루프로 전환. 풀스택 구인수 팬텀히트(apps=2)가 은화살 스택을 가속.
- K=2 두 번째 체력바를 항상 풀피로 시작하는 현행 엔진에서 OLD·NEW를 비교한다.
- 관측(2026-08-08 재캡처, Q 즉시 공격 + 첫 Q 벽캔 1회): T2 -0.12%, T3 +3.35%, T4 +4.24%.

**시나리오 고정 (2026-07-26)**: 기본 베인 DPS 설정과 동일하게 Q 뒤 즉시 공격하고,
첫 Q에서만 0.33초 벽 평캔을 한 번 적용한다.

**엔진 변경 (2026-07-22, 2026-07-25, 2026-07-26)**
- 첫 처치 오버킬을 두 번째 체력바에 이월하던 동작을 제거했다.
- R 중 Q 후 평타를 1초까지 잠가 은신 지속시간을 반영했다.
- 이후 기본 DPS 설정을 Q 즉시 공격 + 첫 Q 벽캔 1회로 교체했다.
- 따라서 이전 스냅샷의 공격 배치와 CutDown 문턱 상호작용은 더 이상 성립하지 않는다.
- 현행 CutDown 설정에서는 T2 NEW<OLD, T3~T4 NEW>OLD가 관측된다. 이 테스트는 원인을 새로
  단정하지 않고 현행 엔진에서의 관측값만 회귀 검증한다.

**본 테스트의 역할**
- 픽스 이후에도 이 상호작용이 그대로임을 회귀 검증(정합성 감시).
- 미래에 BotRK 계수/은화살 배치가 바뀌면 값이 흔들려 즉시 감지.
- 값은 실측 스냅샷(허용오차 1e-2) — 변경 시 원인 규명 후 갱신.
"""
from adc_sim.champion import Vayne, Champion
from adc_sim.simulations.vayne import (
    build_target_for_core, CONTROL_PATH, CORE_VAYNE_LEVELS, _skill_levels_for_core,
)
from adc_sim.runes import LethalTempo, CutDown
from adc_sim.data.items_registry import create_item_from_key
from adc_sim.engine import run_simulation

NEW_METHOD = Vayne.get_one_hit_damage


def _old_silverbolts_get_one_hit_damage(self, target, time=0):
    """은화살 픽스 이전 로직만 재구성(sb_stacks += 1 단발). Q 로직은 **현행(크리·C44 미반영)** 유지 —
    silverbolts 픽스만 격리해 비교."""
    p_base, m_base, p_onhit, m_onhit, pt_base, pt_onhit = Champion.get_one_hit_damage(
        self, target, time)
    if self.q_empowered:
        self.q_empowered = False
        ratio = self.Q_AD_RATIO[self.q_level - 1]
        p_base += self.total_ad * ratio * self._last_damage_amp
    self.sb_stacks += 1
    if self.sb_stacks >= 3:
        self.sb_stacks = 0
        idx = self.w_level - 1
        sb = max(self.W_FLOOR[idx], self.W_PCT[idx] * target.max_hp)
        pt_onhit += sb * self._last_damage_amp
    return p_base, m_base, p_onhit, m_onhit, pt_base, pt_onhit


def _run_ctrl_bow_glut(tier, use_new, with_cutdown=True):
    """CTRL 빌드(botrk-guinsoo-terminus-pd, Bow+Glut 패키지) 를 tier 코어까지 시뮬.
    use_new=False 시 OLD 은화살 로직으로 재시뮬(monkey-patch).
    with_cutdown=False 시 sub_rune 미장착(문턱 상호작용 격리 검증용).
    """
    try:
        Vayne.get_one_hit_damage = NEW_METHOD if use_new else _old_silverbolts_get_one_hit_damage
        target = build_target_for_core(tier)
        lvl = CORE_VAYNE_LEVELS[tier]["level"]
        q, w, e, r_lvl = _skill_levels_for_core(tier)
        v = Vayne(
            level=lvl, q_level=q, w_level=w, e_level=e, r_level=r_lvl,
            q_first_wall_reset_only=True,
        )
        v.set_rune(LethalTempo())
        if with_cutdown:
            v.set_sub_rune(CutDown())
        v.add_item(create_item_from_key("doranbow"))
        v.add_item(create_item_from_key("glutton"))
        for k in CONTROL_PATH[:tier]:
            v.add_item(create_item_from_key(k))
        v.bonus_as_percent += 0.18  # 민첩함 룬(Bow+Glut 패키지)
        plan = {"manual_casts": [(0.0, "r")],
                "auto_cast": {"q": True, "r": False}, "auto_order": ["q"]}
        _, dps, _ = run_simulation(v, target, verbose=False, skill_plan=plan,
                                    respawn_to_full_kills=2)
        return dps
    finally:
        Vayne.get_one_hit_damage = NEW_METHOD


def test_ctrl_new_vs_old_snapshot_bow_glut_with_cutdown():
    """OLD vs NEW CTRL DPS 델타 스냅샷 (Bow+Glut, LT+CutDown).

    실측(2026-08-08 재캡처 — 베인 Q 첫 벽리셋 + 카이사 시전 지연 반영 확정, 사용자 확인):
      T2: OLD=526.500, NEW=525.862, Δ=-0.12%
      T3: OLD=780.001, NEW=806.137, Δ=+3.35%
      T4: OLD=979.101, NEW=1020.574, Δ=+4.24%
    T2 만 NEW<OLD(BotRK 6%현재HP 스케일과 은화살 프론트로드의 반작용), T3~T4 는 프론트로드된
    은화살의 절대 이득이 그 손실을 넘어 NEW>OLD — 모듈 docstring "엔진 변경" 항의 서술과 일치한다.
    (직전 스냅샷 774.144/1017.045/1269.681 은 Q 벽리셋 도입 이전 값이라 폐기.)
    (OLD 는 은화살 픽스만 되돌리고 Q 픽스는 유지 — silverbolts 영향만 격리.)
    """
    EXPECT = {
        2: (526.500, 525.862),
        3: (780.001, 806.137),
        4: (979.101, 1020.574),
    }
    for tier, (exp_old, exp_new) in EXPECT.items():
        old_dps = _run_ctrl_bow_glut(tier=tier, use_new=False)
        new_dps = _run_ctrl_bow_glut(tier=tier, use_new=True)
        assert abs(old_dps - exp_old) < 1e-2, (
            f"T{tier} OLD snapshot drift: expected {exp_old}, got {old_dps:.3f}")
        assert abs(new_dps - exp_new) < 1e-2, (
            f"T{tier} NEW snapshot drift: expected {exp_new}, got {new_dps:.3f}")
        if tier == 2:
            assert new_dps < old_dps
        else:
            assert new_dps > old_dps


def test_t3_no_cutdown_snapshot():
    """보조룬 없는 T3 스냅샷 — 은화살 프론트로드의 순이득을 %증폭 없이 격리 관측.

    실측(2026-08-08 재캡처): T3 sub_rune=None: OLD=759.888, NEW=780.704, Δ=+2.74%

    ⚠️ 옛 이름(`test_cutdown_removal_flips_t3_delta_sign`)과 "CutDown 제거 시 부호 반전"
    주장은 폐기했다. Q 벽리셋 도입 이후 T3 는 **CutDown 유무와 무관하게** NEW>OLD 이고
    (CutDown +3.35% vs 미장착 +2.74%), 오히려 CutDown 이 있을 때 NEW 우위가 더 크다.
    "%증폭이 BotRK 손실을 확대한다"는 기존 해석은 현행 엔진에서 관측되지 않으므로
    여기서는 기전을 단정하지 않고 실측 스냅샷만 회귀 검증한다(AGENTS.md 4).
    """
    old_dps = _run_ctrl_bow_glut(tier=3, use_new=False, with_cutdown=False)
    new_dps = _run_ctrl_bow_glut(tier=3, use_new=True, with_cutdown=False)
    assert abs(old_dps - 759.888) < 1e-2, f"T3 no-CutDown OLD drift: {old_dps:.3f}"
    assert abs(new_dps - 780.704) < 1e-2, f"T3 no-CutDown NEW drift: {new_dps:.3f}"
    assert new_dps > old_dps * 1.02, (
        f"T3 CutDown 제거 시에도 NEW>OLD +2%+ 예상: OLD={old_dps:.3f} NEW={new_dps:.3f}")
