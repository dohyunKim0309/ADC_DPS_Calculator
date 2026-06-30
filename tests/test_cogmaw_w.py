"""CogMaw W = cooldown-managed %maxHP on-hit. Run: .venv/bin/python -m tests.test_cogmaw_w"""
from adc_sim.champion import CogMaw, Target


def test_onhit_zero_when_w_inactive():
    c = CogMaw(level=11, w_level=5); c.init_combat_state()
    c.w_active = False
    assert c.get_champion_onhit(Target(hp=2000, armor=40, magic_resist=30)) == (0, 0)


def test_onhit_pct_maxhp_when_active():
    c = CogMaw(level=11, w_level=5); c.init_combat_state()
    c.w_active = True; c._combat_time = 1.0
    tgt = Target(hp=2000, armor=40, magic_resist=30)
    phys, magic = c.get_champion_onhit(tgt)
    # w5 = 6% maxHP + 0.00015*AP*maxHP. AP=0 here -> 0.06*2000 = 120.
    assert phys == 0 and abs(magic - 0.06 * 2000) < 1e-6, (phys, magic)


def test_w_cast_toggles_buff_and_spends_mana():
    c = CogMaw(level=11, w_level=5); c.init_combat_state()
    start = c.current_mana
    name, p, m, is_hit = c._cast_skill("w", Target(hp=2000, armor=40, magic_resist=30), 0.0)
    assert is_hit is False and p == 0.0 and m == 0.0   # W is a buff, no direct damage
    assert c.w_active is True
    assert c.current_mana <= start - 40.0 + 1e-9


def test_w_expires_after_8s():
    c = CogMaw(level=11, w_level=5); c.init_combat_state()
    c._cast_skill("w", Target(hp=2000, armor=40, magic_resist=30), 0.0)
    c.advance_combat_time(8.0 + 1e-6, 8.0 + 1e-6, Target(hp=2000, armor=40, magic_resist=30))
    assert c.w_active is False


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_") and callable(f):
            f(); print(f"PASS {n}")
    print("ALL PASS")
