"""Cast gating + no-spin. Uses synthetic mana to test the MECHANISM.
Run: .venv/bin/python -m tests.test_mana_gating"""
from adc_sim.champion import KaiSa, Target
from adc_sim.engine import run_simulation


def test_oom_blocks_cast_and_never_spins():
    k = KaiSa(level=11, q_level=5, w_level=5, e_level=5, r_level=3)
    # Force a tiny pool + zero regen: once mana is gone, Q/W must not cast,
    # and the sim must still terminate in finite steps (0-dt spin guard).
    k.base_mana = 0.0; k.mana_growth = 0.0; k.base_mp5 = 0.0; k.mp5_growth = 0.0
    k.mana_cost = {"q": 50.0, "w": 50.0, "e": 0.0, "r": 0.0}
    target = Target(hp=3000, armor=80, magic_resist=50, bonus_hp=1500)
    # Must return (finite kill time, positive dps) without hanging.
    history, dps, kill_time = run_simulation(k, target, verbose=False,
        skill_plan={"auto_cast": {"q": True, "w": True, "e": False, "r": False}})
    assert dps > 0 and kill_time < 10_000, (dps, kill_time)
    assert k.current_mana >= -1e-9


def test_affordable_casts_consume_mana():
    k = KaiSa(level=11, q_level=5, w_level=5, e_level=5, r_level=3)
    k.base_mana = 1000.0; k.mana_growth = 0.0; k.base_mp5 = 0.0; k.mp5_growth = 0.0
    k.mana_cost = {"q": 50.0, "w": 50.0, "e": 0.0, "r": 0.0}
    k.init_combat_state({"auto_cast": {"q": True, "w": False, "e": False, "r": False}})
    start = k.current_mana
    assert k._can_cast_skill("q")
    k.pop_due_skill_events(0.0, Target(hp=4000, armor=80, magic_resist=50))
    assert k.current_mana <= start - 50.0 + 1e-9, (start, k.current_mana)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"PASS {name}")
    print("ALL PASS")
