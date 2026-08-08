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


def test_kaisa_w_cast_time_extends_pending_attack_delay():
    """Opening W is free, while a later W adds 0.4s to the next attack delay."""
    k = KaiSa(level=1, q_level=1, w_level=1, e_level=1, r_level=1)
    k.w_cd = [0.1] * 5
    base_interval = k.get_attack_interval()
    target = Target(hp=5000, armor=0, magic_resist=0)
    history, _, _ = run_simulation(
        k,
        target,
        verbose=False,
        skill_plan={
            "manual_casts": [(0.0, "w"), (0.1, "w")],
            "auto_cast": {"q": False, "w": False, "e": False, "r": False},
        },
        respawn_to_full_kills=1,
    )
    assert history[1][0] == 0.0
    assert history[2][0] == round(base_interval + 0.4, 2)


def test_kaisa_e_cast_time_extends_pending_attack_delay():
    """Opening E is free, while a later E adds its bonus-AS-scaled cast time."""
    k = KaiSa(level=1, q_level=1, w_level=1, e_level=1, r_level=1)
    k.e_cd = [0.1] * 5
    target = Target(hp=5000, armor=0, magic_resist=0)
    k.init_combat_state({"auto_cast": {"q": False, "w": False, "e": False, "r": False}})
    k._cast_skill("e", target, 0.0)
    assert k.get_attack_delay_extension("e") == 0.0
    k.advance_combat_time(4.0, 4.0, target)
    k._cast_skill("e", target, 4.0)
    assert abs(k.get_attack_delay_extension("e") - 1.2) < 1e-9

    k = KaiSa(level=1, q_level=1, w_level=1, e_level=1, r_level=1)
    k.e_cd = [0.1] * 5
    base_interval = k.get_attack_interval()
    target = Target(hp=5000, armor=0, magic_resist=0)
    history, _, _ = run_simulation(
        k,
        target,
        verbose=False,
        skill_plan={
            "manual_casts": [(0.0, "e"), (4.0, "e")],
            "auto_cast": {"q": False, "w": False, "e": False, "r": False},
        },
        respawn_to_full_kills=1,
    )
    assert history[1][0] == 0.0
    assert history[2][0] < round(base_interval + 0.01, 2)
    assert 5.5 < history[5][0] < 5.8


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"PASS {name}")
    print("ALL PASS")
