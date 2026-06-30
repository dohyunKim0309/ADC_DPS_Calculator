"""Pre/post mana-change DPS snapshot. No plotting — safe headless.

Run (capture baseline BEFORE mana changes):
    .venv/bin/python -m tests.regression_snapshot --write
Run (diff AFTER changes): see tests/test_regression_diff.py
"""
import json
from pathlib import Path

from adc_sim.simulations.ashe import simulate_ashe_core_path
from adc_sim.simulations.yunara import simulate_yunara_core_path
from adc_sim.simulations.kaisa import simulate_kaisa_core_path
from adc_sim.simulations.corki import simulate_corki_core_path
from adc_sim.simulations.ezreal import simulate_ezreal_core_path

BASELINE_PATH = Path(__file__).with_name("_baseline_dps.json")

# Control/representative builds per champion (must exist in each sim's pool).
# Corki: actual control_path from corki.py is ("trinity", "muramana", "collector", "ldr").
#   The brief used ("trinity", "muramana", "collector", "ie") but the real control uses "ldr"
#   at core4, which is the canonical reference build for Corki.
REPRESENTATIVE_CASES = [
    {"champion": "Ashe",   "fn": simulate_ashe_core_path,   "path": ("kraken", "pd", "ie", "ldr")},
    {"champion": "Yunara", "fn": simulate_yunara_core_path, "path": ("kraken", "pd", "ie", "ldr")},
    {"champion": "KaiSa",  "fn": simulate_kaisa_core_path,  "path": ("kraken", "guinsoo", "nashor", "terminus")},
    {"champion": "Corki",  "fn": simulate_corki_core_path,  "path": ("trinity", "muramana", "collector", "ldr")},
    {"champion": "Ezreal", "fn": simulate_ezreal_core_path, "path": ("trinity", "muramana", "ie", "ldr")},
]


def _dps_for_case(case, tier):
    """Call a champion's simulate_*_core_path with whatever signature it has.

    Ashe: fn(path[:tier], tier)  — no internal slicing, must pass slice.
    Yunara/KaiSa: fn(path, tier) — do internal slicing, full path is fine.
    Corki/Ezreal: fn(path, shoe_key, rune_key, tier) — do internal slicing.
    Returns dps (first element of the returned tuple)."""
    fn, path = case["fn"], case["path"]
    name = case["champion"]
    if name in ("Corki", "Ezreal"):
        result = fn(path, "berserker", "conq", tier)
    elif name == "Ashe":
        result = fn(path[:tier], tier)
    else:
        result = fn(path, tier)
    return float(result[0])


def compute_snapshot():
    snap = {}
    for case in REPRESENTATIVE_CASES:
        for tier in (1, 2, 3, 4):
            key = f"{case['champion']}|{'-'.join(case['path'])}|T{tier}"
            snap[key] = round(_dps_for_case(case, tier), 6)
    return snap


if __name__ == "__main__":
    import sys
    snap = compute_snapshot()
    if "--write" in sys.argv:
        BASELINE_PATH.write_text(json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[baseline] wrote {len(snap)} cases -> {BASELINE_PATH}")
    else:
        print(json.dumps(snap, indent=2, ensure_ascii=False))
