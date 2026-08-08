import pytest

from adc_sim.simulations import ashe, cogmaw, corki, ezreal, jinx, yunara
from adc_sim.settings import (
    RANKING_SCORING, derive_core_weights, CORE_WEIGHTS_RAW, CORE_WEIGHTS_LABEL,
)


RECEDING_MODULES = (ashe, yunara, corki, ezreal, cogmaw, jinx)


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


@pytest.mark.parametrize("module", RECEDING_MODULES)
def test_remaining_champion_cli_defaults_to_receding_horizon(module, monkeypatch):
    """남은 챔피언의 인자 없는 CLI가 보존된 전수 랭킹 대신 새 기본 탐색을 호출한다."""
    called = []
    monkeypatch.setattr(module, "main", lambda gamma=None: called.append(gamma))
    monkeypatch.setattr(
        module,
        "main_legacy_ranking",
        lambda: (_ for _ in ()).throw(AssertionError("legacy ranking called")),
    )

    module.run_cli([])

    assert called == [module.GAMMA]


@pytest.mark.parametrize("module", RECEDING_MODULES)
def test_remaining_champion_cli_preserves_legacy_ranking(module, monkeypatch):
    """명시적 호환 모드는 새 기본 탐색 없이 교체 전 전수 랭킹만 호출한다."""
    called = []
    monkeypatch.setattr(module, "main_legacy_ranking", lambda: called.append("legacy"))
    monkeypatch.setattr(
        module,
        "main",
        lambda gamma=None: (_ for _ in ()).throw(AssertionError("default search called")),
    )

    module.run_cli(["legacy-ranking"])

    assert called == ["legacy"]


@pytest.mark.parametrize("module", RECEDING_MODULES)
def test_remaining_champion_searches_expose_five_slots(module):
    """모든 신규 기본 탐색이 공통 γ와 1~5코어 후보 맵을 노출하는지 검증한다."""
    assert module.GAMMA == RANKING_SCORING["gamma"]
    assert module.HORIZON == 5
    assert set(module.CANDIDATES_BY_SLOT) == {1, 2, 3, 4, 5}
    assert all(module.CANDIDATES_BY_SLOT[slot] for slot in range(1, 6))


@pytest.mark.parametrize("module", RECEDING_MODULES)
def test_remaining_champion_combo_score_matches_vayne_marginal_dpg(module):
    """미래 점수가 현재 상태 대비 코어별 마지널 DPG의 γ 할인합인지 수계산한다."""

    class FakeCache:
        """아이템 개수에 대응하는 합성 DPS·골드를 반환한다."""

        def sim(self, items):
            return {1: (100.0, 1000.0), 2: (300.0, 2000.0)}[len(items)]

    score = module._score_combo(
        FakeCache(), [], ("a", "b"), 1, 0.0, 0.0, gamma=0.5, horizon=2,
    )

    # 1C marginal DPG=100, 2C=150; 100 + 0.5*150 = 175.
    assert score == pytest.approx(175.0)
