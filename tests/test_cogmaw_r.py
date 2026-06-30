"""CogMaw R = missing-HP scaling + mana ramp. Run: .venv/bin/python -m tests.test_cogmaw_r"""
from adc_sim.champion import CogMaw, Target


def _bonus_ad(c):
    return max(0.0, c.total_ad - c.base_attack_ad)


def test_r_full_hp_base_damage():
    c = CogMaw(level=16, r_level=3); c.init_combat_state()
    tgt = Target(hp=2000, armor=80, magic_resist=60)   # full hp -> mult 1.0
    name, p, m, is_hit = c._cast_skill("r", tgt, 0.0)
    expected = (180 + 0.75 * _bonus_ad(c) + 0.45 * c.total_ap) * 1.0   # r3 base 180, ap 0.45
    assert is_hit is True and abs(m - expected) < 1e-6, (m, expected)


def test_r_execute_below_40pct_doubles():
    c = CogMaw(level=16, r_level=3); c.init_combat_state()
    tgt = Target(hp=2000, armor=80, magic_resist=60); tgt.current_hp = 0.39 * 2000
    name, p, m, is_hit = c._cast_skill("r", tgt, 0.0)
    expected = (180 + 0.75 * _bonus_ad(c) + 0.45 * c.total_ap) * 2.0
    assert abs(m - expected) < 1e-6, (m, expected)


def test_r_mana_ramps_per_consecutive_cast():
    c = CogMaw(level=16, r_level=3); c.init_combat_state()
    tgt = Target(hp=9_000_000, armor=0, magic_resist=0)   # never dies; mana is huge
    c.base_mana = 100000; c.init_combat_state()            # ensure affordable
    assert c._cost("r") == 40.0                            # first cast: 40
    c._cast_skill("r", tgt, 0.0)
    assert c._cost("r") == 80.0                            # next: +40
    c._cast_skill("r", tgt, 0.1)
    assert c._cost("r") == 120.0


def test_r_stack_decays_after_8s():
    c = CogMaw(level=16, r_level=3); c.base_mana = 100000; c.init_combat_state()
    tgt = Target(hp=9_000_000, armor=0, magic_resist=0)
    c._cast_skill("r", tgt, 0.0)
    assert c._cost("r") == 80.0
    c.advance_combat_time(8.0 + 1e-6, 8.0 + 1e-6, tgt)
    assert c._cost("r") == 40.0                            # decayed back to base


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_") and callable(f):
            f(); print(f"PASS {n}")
    print("ALL PASS")
