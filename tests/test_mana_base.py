"""Base-class mana mechanics. Run: .venv/bin/python -m tests.test_mana_base"""
from adc_sim.champion import Champion


def _make():
    c = Champion(name="T", base_ad=60, base_as=0.65, as_ratio=0.65,
                 as_growth=2.0, base_range=500, level=11)
    c.base_mana = 400.0
    c.mana_growth = 40.0      # total_mana = 400 + 40*10 = 800
    c.base_mp5 = 10.0
    c.mp5_growth = 0.5        # mp5 = 10 + 0.5*10 = 15 -> 3.0/sec
    return c


def test_init_fills_to_full():
    c = _make()
    c.init_combat_state()
    assert abs(c.current_mana - 800.0) < 1e-9, c.current_mana


def test_regen_per_sec_and_clamp():
    c = _make(); c.init_combat_state()
    assert abs(c.mana_regen_per_sec - 3.0) < 1e-9, c.mana_regen_per_sec
    c.spend_mana(100.0)                 # 700
    c.regen_mana(10.0)                  # +30 -> 730
    assert abs(c.current_mana - 730.0) < 1e-9, c.current_mana
    c.regen_mana(10_000.0)              # clamp at 800
    assert abs(c.current_mana - 800.0) < 1e-9, c.current_mana


def test_afford_and_spend():
    c = _make(); c.init_combat_state(); c.spend_mana(750.0)   # 50 left
    assert c.can_afford(50.0) and not c.can_afford(50.1)
    assert abs(c._afford_in(50.0) - 0.0) < 1e-9
    # need 110 -> short 60 -> at 3/sec -> 20s
    assert abs(c._afford_in(110.0) - 20.0) < 1e-9, c._afford_in(110.0)
    c.spend_mana(999.0)                 # clamps to 0, never negative
    assert c.current_mana == 0.0


def test_no_regen_means_infinite_afford():
    c = _make(); c.base_mp5 = 0.0; c.mp5_growth = 0.0
    c.init_combat_state(); c.spend_mana(800.0)
    assert c._afford_in(10.0) == float("inf")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"PASS {name}")
    print("ALL PASS")
