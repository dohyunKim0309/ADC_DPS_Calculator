"""유나라 스킬 시전 시간(cast time) [H-YUNARA-CAST-1].

모델: W(심판/파멸의 궤적)는 스킬샷, 시전 시간 max(0.225, 0.45/(1+추가공속)).
**W 는 평타캔슬 불가(사용자 확정)** → 시전 시간이 평타 간격에 그대로 가산(두 시간의 합
= 평타간격 + 시전). 엔진 `cast_delay_pending`(가산형) 사용, 회복 클립(0.33) 없음.
비교로, 캔슬 가능 스킬은 `cast_lockout_until`(흡수형) — 간격 안에 들면 무손실.
Q(정신 수양)/R(초월)=즉발 자가버프 → 시전 0, E(칸메이의 발걸음)=이동기 미모델.

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


def test_base_champion_has_no_cast_delay():
    """시전 시간 미모델 챔피언은 두 채널 모두 0 → 기존 동작 불변."""
    y = _yunara()
    y.init_combat_state()
    assert y.cast_lockout_until == 0.0
    assert y.cast_delay_pending == 0.0


def test_noncancel_cast_reduces_dps_monotonically():
    """비캔슬(가산형) 시전 시간이 커질수록 DPS 단조 감소(간격에 가산)."""
    t = lambda: Target(hp=2500, armor=100, magic_resist=50)
    _, dps0, _ = run_simulation(_yunara(cast_base=0.0, cast_floor=0.0), t(), verbose=False)
    _, dps_small, _ = run_simulation(_yunara(cast_base=0.45, cast_floor=0.225), t(), verbose=False)
    _, dps_big, _ = run_simulation(_yunara(cast_base=2.0, cast_floor=2.0), t(), verbose=False)
    assert dps0 > dps_small > dps_big  # 가산형: 아무리 작아도 손실(흡수 안 됨)


def test_real_w_cast_costs_dps():
    """실제 W 시전(비캔슬)은 간격에 가산 → DPS 손실 발생(무비용 아님)."""
    t = lambda: Target(hp=2500, armor=100, magic_resist=50)
    _, dps_free, _ = run_simulation(_yunara(cast_base=0.0, cast_floor=0.0), t(), verbose=False)
    _, dps_real, _ = run_simulation(_yunara(), t(), verbose=False)  # 기본 0.45/0.225
    assert dps_real < dps_free


def test_cast_delay_set_on_w_cast():
    """W 본체 시전(비캔슬) 시 cast_delay_pending 에 시전 시간이 가산된다."""
    y = _yunara()
    y.init_combat_state()
    y.hit_count = 2                       # W 시전 조건(둘째 평타 이후)
    y.cooldowns_remaining["w"] = 0.0      # 쿨 준비 완료
    tgt = Target(hp=2500, armor=100, magic_resist=50)
    events = y.pop_due_skill_events(1.0, tgt)
    assert any(e[0] == "w" for e in events)
    assert abs(y.cast_delay_pending - y.w_cast_time()) < 1e-6
    assert y.cast_lockout_until == 0.0    # 비캔슬 → 흡수형 미사용


def test_cancelable_path_absorbs_within_interval():
    """(회귀 방지) 캔슬 가능(흡수형) 경로는 시전<간격이면 무손실.
    같은 흡수형에서 실제 시전(0.225) vs 시전 0 을 비교(둘 다 0.33 클립 동일)."""
    t = lambda: Target(hp=2500, armor=100, magic_resist=50)
    y0 = _yunara(cast_base=0.0, cast_floor=0.0); y0.w_cancelable = True
    _, dps0, _ = run_simulation(y0, t(), verbose=False)
    yr = _yunara(); yr.w_cancelable = True     # 실제 0.45/0.225, 흡수형
    _, dpsr, _ = run_simulation(yr, t(), verbose=False)
    assert abs(dpsr - dps0) < 1e-6             # 0.225s < 간격(≥0.33) → 흡수, 무손실
