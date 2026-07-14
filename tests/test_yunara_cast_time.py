"""유나라 스킬 시전 시간(auto-attack lockout) [H-YUNARA-CAST-1].

모델: W(심판/파멸의 궤적)는 스킬샷 — 시전 시간 max(0.225, 0.45/(1+추가공속)) 동안
평타 불가(엔진 cast_lockout_until 게이트). 캔슬 가능이라 시전 후 다음 평타 0.33 클립 유지.
Q(정신 수양)/R(초월)=즉발 자가버프 → 시전 0, E(칸메이의 발걸음)=이동기 미모델.

핵심 발견: 유나라 평타 간격(공속캡 3.0 → 바닥 0.333s, 실전 ~0.46s)이 W 시전 시간(≤0.45s,
추가공속 높으면 0.225s)보다 항상 커서 실제 W 는 평타 손실 없이 위빙 → DPS 영향 ≈ 0.
락아웃 기구 자체는 시전 시간이 간격을 초과하면 정상적으로 평타를 지연시킨다.

Run: .venv/bin/python -m pytest tests/test_yunara_cast_time.py
"""
from adc_sim.champion import Yunara, Target
from adc_sim.engine import run_simulation
from adc_sim.runes import LethalTempo, CutDown
from adc_sim.data.items_registry import create_item_from_key


def _yunara(cast_base=None, cast_floor=None):
    y = Yunara(level=15, q_level=5, w_level=5, r_level=3)
    if cast_base is not None:
        y.w_cast_base = cast_base
    if cast_floor is not None:
        y.w_cast_floor = cast_floor
    y.set_rune(LethalTempo())
    y.set_sub_rune(CutDown())
    for k in ["kraken", "pd", "ie", "ldr"]:
        y.add_item(create_item_from_key(k))
    return y


def test_w_cast_time_formula():
    """max(0.225, 0.45/(1+추가공속)) — 추가공속에 비례 감소, 바닥 0.225."""
    y = Yunara(level=1, q_level=1)  # 추가공속 최소
    y.bonus_as_percent = 0.0
    # 추가공속 0 → 0.45 / (1 + level_bonus). level=1 → 성장 0.
    assert abs(y.w_cast_time() - 0.45) < 1e-6
    y.bonus_as_percent = 1.0        # +100% → 0.45/2 = 0.225 (=바닥)
    assert abs(y.w_cast_time() - 0.225) < 1e-6
    y.bonus_as_percent = 3.0        # 매우 높음 → 바닥 클램프
    assert abs(y.w_cast_time() - 0.225) < 1e-6


def test_base_champion_has_no_lockout():
    """시전 시간 미모델 챔피언은 cast_lockout_until=0 → 기존 동작 불변."""
    y = _yunara()
    y.init_combat_state()
    assert y.cast_lockout_until == 0.0


def test_lockout_defers_auto_when_cast_exceeds_interval():
    """시전 시간 > 평타 간격이면 락아웃이 평타를 지연 → DPS 감소(단조)."""
    t = lambda: Target(hp=2500, armor=100, magic_resist=50)
    _, dps_free, _ = run_simulation(_yunara(cast_base=0.0, cast_floor=0.0), t(), verbose=False)
    _, dps_big, _ = run_simulation(_yunara(cast_base=2.0, cast_floor=2.0), t(), verbose=False)
    assert dps_big < dps_free  # 큰 시전 시간은 평타를 지연시켜 DPS 하락


def test_real_w_cast_fits_in_interval_no_dps_loss():
    """실제 W 시전(0.225~0.45s) < 평타 간격(≥0.33s) → 위빙 무손실(DPS 불변)."""
    t = lambda: Target(hp=2500, armor=100, magic_resist=50)
    _, dps_free, _ = run_simulation(_yunara(cast_base=0.0, cast_floor=0.0), t(), verbose=False)
    _, dps_real, _ = run_simulation(_yunara(), t(), verbose=False)  # 기본 0.45/0.225
    assert abs(dps_real - dps_free) < 1e-6


def test_lockout_set_on_w_cast():
    """W 본체 시전 시 cast_lockout_until 이 현재시각+시전시간으로 설정된다."""
    y = _yunara()
    y.init_combat_state()
    y.hit_count = 2                       # W 시전 조건(둘째 평타 이후)
    y.cooldowns_remaining["w"] = 0.0      # 쿨 준비 완료
    tgt = Target(hp=2500, armor=100, magic_resist=50)
    events = y.pop_due_skill_events(1.0, tgt)
    assert any(e[0] == "w" for e in events)
    assert y.cast_lockout_until > 1.0
    assert abs(y.cast_lockout_until - (1.0 + y.w_cast_time())) < 1e-6
