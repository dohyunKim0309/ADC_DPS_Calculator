"""Compare post-change DPS to the pre-change baseline.
Run: .venv/bin/python -m tests.test_regression_diff"""
import json
from tests.regression_snapshot import compute_snapshot, BASELINE_PATH

TOL = 1e-4   # relative tolerance


def test_no_unexpected_dps_change():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    now = compute_snapshot()
    changed = []
    for key, base in baseline.items():
        cur = now.get(key)
        assert cur is not None, f"missing case {key}"
        denom = base if abs(base) > 1e-9 else 1.0
        if abs(cur - base) / abs(denom) > TOL:
            changed.append((key, base, cur, f"{(cur-base)/denom*100:+.2f}%"))
    if changed:
        print("CHANGED CASES (confirm intended — mana-item builds / OOM):")
        for row in changed:
            print("  ", row)
    # The representative builds in Task 1 are non-mana-item, short-ish fights:
    # expectation is ZERO changed. If any appear, STOP and explain before proceeding.
    assert not changed, f"{len(changed)} cases changed unexpectedly — investigate"


if __name__ == "__main__":
    test_no_unexpected_dps_change()
    print("PASS test_no_unexpected_dps_change")
    print("ALL PASS")
