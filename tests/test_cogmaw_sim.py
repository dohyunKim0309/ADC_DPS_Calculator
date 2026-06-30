"""CogMaw core sim. Run: .venv/bin/python -m tests.test_cogmaw_sim"""
from adc_sim.simulations.cogmaw import simulate_cogmaw_core_path


def test_simulate_returns_positive_dps_and_cost():
    dps, cost = simulate_cogmaw_core_path(("guinsoo", "kraken", "nashor", "terminus"), 4)
    assert dps > 0 and cost > 0


def test_dps_monotonic_across_cores():
    path = ("guinsoo", "kraken", "nashor", "terminus")
    d1, _ = simulate_cogmaw_core_path(path, 1)
    d4, _ = simulate_cogmaw_core_path(path, 4)
    assert d4 > d1   # more items + higher level + tankier target, but net DPS up


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_") and callable(f):
            f(); print(f"PASS {n}")
    print("ALL PASS")
