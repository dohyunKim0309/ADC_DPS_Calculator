"""베인 은화살 팬텀히트 픽스([H-VAYNE-W-GUI])의 CTRL DPS 소폭 감소 원인 기록.

**배경**
- 픽스: `Vayne.get_one_hit_damage`에서 `sb_stacks += 1` 단발 → `_last_onhit_applications`
  만큼 루프로 전환. 풀스택 구인수 팬텀히트(apps=2)가 은화살 스택을 가속.
- 기대: CTRL(botrk-guinsoo-terminus-pd, Bow+Glut) DPS 는 픽스 전보다 상승할 것.
- 관측: T2 -1.03%, T3 -0.52%, T4 -0.47% — 모두 소폭 하락(반대 방향).

**시나리오 고정 (2026-07-20)**: q_wall_reset=True 로 벽 상황 재현 —
이 반작용은 Q 평타 리셋이 있는 상황에서 프론트로드된 은화살의 BotRK 상호작용을
관찰하는 것이 목적. 기본(오픈 필드, q_wall_reset=False)에서는 반작용 특성이 다르므로
이 테스트는 벽 시나리오 회귀 감시용.

**원인 규명 (2026-07-14 진단)**
1. 은화살 **총 버스트 회수는 OLD·NEW 동일**(T3 예: 둘 다 12평타 4버스트, 처치 4.764s).
   버스트 타이밍만 어긋남 — OLD 2번바 버스트=A9·A12, NEW=A8·A10.
2. 총 true 대미지 998.4 완전 일치. 차이는 **물리 대미지 총합에서 -25.2**.
3. 범인은 **BotRK 온힛 = `target.current_hp × 6%`** (`items.py:260`).
   NEW 가 A8 에 조기 버스트(259.2 true) → 타깃 HP 조기 하락 → 이후 A9·A11·A12 의 BotRK
   %현재HP 딜이 비례적으로 감소.
4. CutDown 60% 문턱은 부차적. `sub_rune=None` 으로 CutDown 을 빼면 T3 는 오히려
   **+4.19% 로 반전** — BotRK 손실을 %증폭이 확대하지 않으므로.

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
        v = Vayne(level=lvl, q_level=q, w_level=w, e_level=e, r_level=r_lvl, q_wall_reset=True)
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

    실측(2026-07-26 패치 재캡처 — Terminus 온힛 30 → 30+10%bAD+10%AP 로 T3/T4 상승):
      T2: OLD=774.144, NEW=766.195, Δ=-1.03%   (Terminus 미포함 → 미변화)
      T3: OLD=1055.021, NEW=1045.604, Δ=-0.89%
      T4: OLD=1310.811, NEW=1304.663, Δ=-0.47%
    셋 모두 NEW<OLD — BotRK 6%현재HP 스케일과 은화살 프론트로드의 반작용을 검증.
    (OLD 는 은화살 픽스만 되돌리고 Q 픽스는 유지 — silverbolts 영향만 격리.)
    """
    EXPECT = {
        2: (774.144, 766.195),
        3: (1055.021, 1045.604),
        4: (1310.811, 1304.663),
    }
    for tier, (exp_old, exp_new) in EXPECT.items():
        old_dps = _run_ctrl_bow_glut(tier=tier, use_new=False)
        new_dps = _run_ctrl_bow_glut(tier=tier, use_new=True)
        assert abs(old_dps - exp_old) < 1e-2, (
            f"T{tier} OLD snapshot drift: expected {exp_old}, got {old_dps:.3f}")
        assert abs(new_dps - exp_new) < 1e-2, (
            f"T{tier} NEW snapshot drift: expected {exp_new}, got {new_dps:.3f}")
        assert new_dps < old_dps, (
            f"T{tier} CTRL 은 NEW<OLD 유지 예상 (BotRK×silverbolts 반작용): "
            f"OLD={old_dps:.3f} NEW={new_dps:.3f}")


def test_cutdown_removal_reduces_t3_delta_magnitude():
    """CutDown 제거 시 T3 델타의 |크기| 감소 → %증폭이 BotRK 손실을 확대함을 증명.

    실측(2026-07-26 패치 재캡처 — Terminus 버프로 baseline 상승):
      T3 sub_rune=None: OLD=1030.686, NEW=1025.655, Δ=-0.49% (WITH CutDown 은 -0.89%)
    직전 스냅샷(2026-07-20)까지는 sign flip(+4.19%) 관측 — Terminus 버프로 은화살 프론트로드
    이득 여유가 감소해 부호는 안 뒤집혀도 magnitude 감소로 CutDown 증폭 상호작용은 여전.
    """
    old_dps = _run_ctrl_bow_glut(tier=3, use_new=False, with_cutdown=False)
    new_dps = _run_ctrl_bow_glut(tier=3, use_new=True, with_cutdown=False)
    assert abs(old_dps - 1030.686) < 1e-2, f"T3 no-CutDown OLD drift: {old_dps:.3f}"
    assert abs(new_dps - 1025.655) < 1e-2, f"T3 no-CutDown NEW drift: {new_dps:.3f}"
    # CutDown 제거 시 델타 크기 감소 검증 (WITH: -0.89% / WITHOUT: -0.49%)
    ctrl_new_with = _run_ctrl_bow_glut(tier=3, use_new=True, with_cutdown=True)
    ctrl_old_with = _run_ctrl_bow_glut(tier=3, use_new=False, with_cutdown=True)
    delta_no_cd = abs(new_dps - old_dps)
    delta_with_cd = abs(ctrl_new_with - ctrl_old_with)
    assert delta_no_cd < delta_with_cd, (
        f"CutDown 증폭 상호작용 예상: |Δ_noCD|={delta_no_cd:.3f} < |Δ_withCD|={delta_with_cd:.3f}")
