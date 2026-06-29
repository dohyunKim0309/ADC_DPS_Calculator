"""Ashe/Yunara Q activation is mana-gated. Run: .venv/bin/python -m tests.test_mana_buff_champs"""
from adc_sim.champion import Ashe, Yunara, Target


def test_ashe_q_blocked_when_oom():
    a = Ashe(level=11, q_level=5)
    a.q_mana_cost = 50.0
    a.init_combat_state()
    a.current_mana = 0.0          # force OOM
    a.hit_count = 4               # activation condition met
    a.get_one_hit_damage(Target(hp=2000, armor=60, magic_resist=40), time=1.0)
    assert a.q_active is False, "Q must not activate while OOM"


def test_ashe_q_activates_and_spends_when_affordable():
    a = Ashe(level=11, q_level=5)
    a.q_mana_cost = 50.0
    a.init_combat_state()
    a.current_mana = 500.0
    a.hit_count = 4
    a.get_one_hit_damage(Target(hp=2000, armor=60, magic_resist=40), time=1.0)
    assert a.q_active is True
    assert a.current_mana <= 500.0 - 50.0 + 1e-9, a.current_mana


def test_yunara_q_blocked_when_oom():
    y = Yunara(level=11, q_level=5)
    y.q_mana_cost = 50.0
    y.init_combat_state()
    y.current_mana = 0.0          # force OOM
    y.q_stacks = 8                # activation condition met
    y.get_one_hit_damage(Target(hp=2000, armor=60, magic_resist=40), time=1.0)
    assert y.q_active is False, "Yunara Q must not activate while OOM"


def test_yunara_q_activates_and_spends_when_affordable():
    y = Yunara(level=11, q_level=5)
    y.q_mana_cost = 50.0
    y.init_combat_state()
    y.current_mana = 500.0
    y.q_stacks = 8
    y.get_one_hit_damage(Target(hp=2000, armor=60, magic_resist=40), time=1.0)
    assert y.q_active is True
    assert y.current_mana <= 500.0 - 50.0 + 1e-9, y.current_mana


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"PASS {name}")
    print("ALL PASS")
