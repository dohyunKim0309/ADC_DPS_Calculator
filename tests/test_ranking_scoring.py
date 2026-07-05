from adc_sim.settings import (
    RANKING_SCORING, derive_core_weights, CORE_WEIGHTS_RAW, CORE_WEIGHTS_LABEL,
)


def test_weighted_mode_derivation():
    w = derive_core_weights({"mode": "weighted", "fixed_raw": [4, 4, 3, 3], "gamma": 0.9})
    assert w == [4, 4, 3, 3]


def test_discounted_mode_derivation():
    w = derive_core_weights({"mode": "discounted", "fixed_raw": [4, 4, 3, 3], "gamma": 0.9})
    assert all(abs(a - b) < 1e-12 for a, b in zip(w, [0.9, 0.81, 0.729, 0.6561]))


def test_n_cores_slicing():
    w3 = derive_core_weights({"mode": "discounted", "fixed_raw": [4, 4, 3, 3], "gamma": 0.5}, n=3)
    assert all(abs(a - b) < 1e-12 for a, b in zip(w3, [0.5, 0.25, 0.125]))


def test_globals_are_derived_and_consistent():
    assert CORE_WEIGHTS_RAW == derive_core_weights(RANKING_SCORING)
    assert isinstance(CORE_WEIGHTS_LABEL, str) and len(CORE_WEIGHTS_LABEL) > 0
