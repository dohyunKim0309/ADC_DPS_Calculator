"""Per-champion mana data is present & correct. Run: .venv/bin/python -m tests.test_mana_data"""
from adc_sim.champion import Ashe, Jinx, Yunara, KaiSa, Corki, Ezreal

# (base_mana, mana_growth, base_mp5, mp5_growth) — confirmed 2026-06-29, spec §3.5
EXPECTED = {
    "Ashe":   (280.0, 35.0, 7.0,  0.65),
    "Jinx":   (260.0, 50.0, 6.7,  1.0),
    "Yunara": (275.0, 45.0, 7.5,  0.75),
    "KaiSa":  (345.0, 40.0, 8.2,  0.7),
    "Corki":  (350.0, 40.0, 7.4,  0.7),
    "Ezreal": (375.0, 70.0, 8.5,  1.0),
}


def test_pools_and_regen_present():
    for cls in (Ashe, Jinx, Yunara, KaiSa, Corki, Ezreal):
        c = cls(level=11)
        key = c.name.replace("'", "")  # "Kai'Sa" → "KaiSa"
        bm, mg, mp5, mp5g = EXPECTED[key]
        assert abs(c.base_mana - bm) < 1e-9, (c.name, "base_mana", c.base_mana)
        assert abs(c.mana_growth - mg) < 1e-9, (c.name, "mana_growth", c.mana_growth)
        assert abs(c.base_mp5 - mp5) < 1e-9, (c.name, "base_mp5", c.base_mp5)
        assert abs(c.mp5_growth - mp5g) < 1e-9, (c.name, "mp5_growth", c.mp5_growth)
        assert c.total_mana > 0, (c.name, "total_mana", c.total_mana)
        assert c.mana_regen_per_sec > 0, (c.name, "mana_regen_per_sec", c.mana_regen_per_sec)


def test_cast_champs_have_real_costs():
    for cls in (KaiSa, Corki, Ezreal):
        c = cls(level=11)
        assert any(v > 0 for v in c.mana_cost.values()), (c.name, c.mana_cost)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"PASS {name}")
    print("ALL PASS")
