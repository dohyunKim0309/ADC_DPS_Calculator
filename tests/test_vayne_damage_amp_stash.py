"""Task 1: 베이스 _last_damage_amp stash 검증(행위보존·값 정확).
증폭 없는 공격이면 1.0, CutDown(고HP 8%) 활성이면 1.08."""
from adc_sim.champion import Ashe, Target
from adc_sim.runes import CutDown


def test_last_damage_amp_defaults_to_one_without_modifiers():
    ashe = Ashe(level=11, q_level=5)
    target = Target(hp=2000, armor=50, magic_resist=30, bonus_hp=500)
    ashe.get_one_hit_damage(target, time=0.0)
    assert abs(ashe._last_damage_amp - 1.0) < 1e-9


def test_last_damage_amp_reflects_cutdown_high_hp():
    # CutDown: 대상 체력 60%+ 에서 8% 증폭 → mod_factor 1.08
    ashe = Ashe(level=11, q_level=5)
    ashe.set_sub_rune(CutDown())
    target = Target(hp=2000, armor=50, magic_resist=30, bonus_hp=500)  # full HP → 60%+
    ashe.get_one_hit_damage(target, time=0.0)
    assert abs(ashe._last_damage_amp - 1.08) < 1e-9


def test_last_damage_amp_exists_before_first_attack():
    ashe = Ashe(level=1)
    assert ashe._last_damage_amp == 1.0
