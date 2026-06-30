"""CogMaw stats/mana/Q-passive AS + basic attack. Run: .venv/bin/python -m tests.test_cogmaw_basic"""
from adc_sim.champion import CogMaw, Target
from adc_sim.engine import run_simulation


def test_stats_and_mana():
    c = CogMaw(level=11, q_level=5)
    assert c.name == "Kog'Maw"
    assert abs(c.base_ad - 61) < 1e-9 and abs(c.ad_growth - 3.11) < 1e-9
    assert abs(c.base_as - 0.665) < 1e-9 and abs(c.as_ratio - 0.665) < 1e-9
    assert c.base_range == 500
    assert abs(c.base_mana - 325) < 1e-9 and abs(c.mana_growth - 40) < 1e-9
    assert abs(c.base_mp5 - 8.75) < 1e-9 and abs(c.mp5_growth - 0.7) < 1e-9
    assert c.total_mana > 0 and c.mana_regen_per_sec > 0


def test_q_passive_as_applied():
    # q5 passive = +25% AS folded into bonus_as_percent at construction.
    c5 = CogMaw(level=11, q_level=5)
    c1 = CogMaw(level=11, q_level=1)
    assert abs(c5.bonus_as_percent - 0.25) < 1e-9, c5.bonus_as_percent
    assert abs(c1.bonus_as_percent - 0.05) < 1e-9, c1.bonus_as_percent
    assert c5.current_attack_speed > c1.current_attack_speed


def test_basic_attack_kills_dummy():
    c = CogMaw(level=11, q_level=5)
    hist, dps, t = run_simulation(c, Target(hp=1500, armor=40, magic_resist=30), verbose=False)
    assert dps > 0 and t > 0


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_") and callable(f):
            f(); print(f"PASS {n}")
    print("ALL PASS")
