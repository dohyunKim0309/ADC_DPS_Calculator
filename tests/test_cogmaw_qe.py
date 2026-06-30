"""CogMaw Q-active (nuke+shred) and E (nuke). Run: .venv/bin/python -m tests.test_cogmaw_qe"""
from adc_sim.champion import CogMaw, Target


def test_q_active_damage_and_shred():
    c = CogMaw(level=11, q_level=5); c.init_combat_state()
    tgt = Target(hp=3000, armor=100, magic_resist=80)
    name, p, m, is_hit = c._cast_skill("q", tgt, 0.0)
    assert is_hit is True and p == 0.0
    assert abs(m - (260 + 0.9 * c.total_ap)) < 1e-6, m         # q5 = 260 (+0.9AP)
    # q5 shred = 32% of armor AND mr
    assert abs(tgt.armor - 100 * (1 - 0.32)) < 1e-6, tgt.armor
    assert abs(tgt.magic_resist - 80 * (1 - 0.32)) < 1e-6, tgt.magic_resist


def test_shred_restores_after_4s():
    c = CogMaw(level=11, q_level=5); c.init_combat_state()
    tgt = Target(hp=3000, armor=100, magic_resist=80)
    c._cast_skill("q", tgt, 0.0)
    c.advance_combat_time(4.0 + 1e-6, 4.0 + 1e-6, tgt)
    assert abs(tgt.armor - 100) < 1e-6 and abs(tgt.magic_resist - 80) < 1e-6


def test_e_damage():
    c = CogMaw(level=11, e_level=5); c.init_combat_state()
    name, p, m, is_hit = c._cast_skill("e", Target(hp=3000, armor=100, magic_resist=80), 0.0)
    assert is_hit is True and p == 0.0
    assert abs(m - (230 + 0.65 * c.total_ap)) < 1e-6, m        # e5 = 230 (+0.65AP)


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_") and callable(f):
            f(); print(f"PASS {n}")
    print("ALL PASS")
