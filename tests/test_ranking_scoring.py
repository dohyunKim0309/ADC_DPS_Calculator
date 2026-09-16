import pytest

from adc_sim.simulations import ashe, cogmaw, corki, ezreal, jinx, receding, vayne, yunara
from adc_sim.settings import (
    RANKING_SCORING, derive_core_weights, CORE_WEIGHTS_RAW, CORE_WEIGHTS_LABEL,
)


# 앵커 누적 점수식 + legacy-ranking 호환 모드를 그대로 쓰는 챔피언들.
# 유나라는 2026-09-15 에 하프 티어 포함 경로로 교체되면서 이 계약에서 빠졌다
# (기본 CLI 는 그대로 main, legacy-ranking 모드와 _score_combo 는 _to_delete/ 로 이동).
RECEDING_MODULES = (ashe, corki, ezreal, jinx)
# 공통 엔진(receding.py)으로 이관 완료된 챔피언 — 앵커 누적 계약에서 빠지고
# 아래 전용 계약(하프 포함 증분 점수식)을 대신 검증한다.
PORTED_MODULES = (yunara, vayne, cogmaw)
SLOT_MAP_MODULES = RECEDING_MODULES + PORTED_MODULES


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


@pytest.mark.parametrize("module", SLOT_MAP_MODULES)
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


# ── 유나라: 하프 티어 포함 경로 (2026-09-15 교체) ────────────────────────────


def test_yunara_cli_defaults_to_half_receding_horizon(monkeypatch):
    """인자 없는 유나라 CLI 는 하프 포함 기본 스윕을 호출한다(5코어 하프는 꺼짐)."""
    called = []
    monkeypatch.setattr(yunara, "main",
                        lambda gamma=None, include_last_half=None: called.append((gamma, include_last_half)))

    yunara.run_cli([])

    assert called == [(yunara.GAMMA, False)]


def test_yunara_cli_half5_enables_last_slot(monkeypatch):
    """`half5` 인자는 5코어 하프까지 켠다."""
    called = []
    monkeypatch.setattr(yunara, "main",
                        lambda gamma=None, include_last_half=None: called.append((gamma, include_last_half)))

    yunara.run_cli(["half5"])

    assert called == [(yunara.GAMMA, True)]


def test_half_combo_score_is_incremental_and_skips_last_half(monkeypatch):
    """하프+완성 스텝이 γ^(step/2) 할인 **증분** 마지널 DPG 합인지 수계산한다.

    공통 엔진(`simulations/receding.py`) 계약이다. 다른 챔피언의 _score_combo 는 앵커
    (탐색 시작 시점) 대비 누적 마지널이라 첫 아이템 기여가 모든 항에 중복 계상되지만,
    하프 경로는 스텝마다 기준을 직전 상태로 갱신한다. 마지막 슬롯(=horizon)의 하프는
    생략되며, 그때도 step 은 진행해 할인 지수를 유지한다.
    """
    class FakeCache:
        """아이템 개수에 대응하는 합성 DPS·골드를 반환한다."""

        def sim(self, items):
            return {1: (100.0, 1000.0), 2: (300.0, 2000.0)}[len(items)]

        def sim_half(self, done, next_key, comps):
            return (50.0, 500.0)

    spec = receding.RecedingSpec(
        title="Fake", candidates_by_slot={1: ["a"], 2: ["b"]},
        pen_rule_ok=lambda keys: True, half_options=lambda key: ((),),
        gamma=0.5, horizon=2,
    )

    score = receding.score_combo(spec, FakeCache(), [], ("a", "b"), 1, 0.0, 0.0)

    # 1C 하프 (50-0)/0.5 = 100          × γ^0   = 100
    # 1C 완성 (100-50)/0.5 = 100        × γ^0.5 = 70.7107
    # 2C 하프 생략(마지막 슬롯) — step 만 +1
    # 2C 완성 (300-100)/1.0 = 200       × γ^1.5 = 70.7107
    expected = 100.0 + 0.5 ** 0.5 * 100.0 + 0.5 ** 1.5 * 200.0
    assert score == pytest.approx(expected)


def test_yunara_late_yuntal_scenario_moves_yuntal_out_of_first_core():
    """`late-yuntal` 은 1코어 윤탈만 막고 2코어는 그대로 둔다(라인전 난항 케이스)."""
    try:
        assert "yuntal25" in yunara.CANDIDATES_BY_SLOT[1]

        yunara.set_yuntal_min_slot(2)

        assert "yuntal25" not in yunara.CANDIDATES_BY_SLOT[1]
        assert "yuntal25" in yunara.CANDIDATES_BY_SLOT[2]
        assert "yuntal25" not in yunara.CANDIDATES_BY_SLOT[3]
    finally:
        yunara.set_yuntal_min_slot(1)


def test_yunara_cli_late_yuntal_flag_combines_with_half5(monkeypatch):
    """`late-yuntal half5` 처럼 플래그를 겹쳐 써도 둘 다 적용된다."""
    called = []
    monkeypatch.setattr(yunara, "main",
                        lambda gamma=None, include_last_half=None: called.append(include_last_half))
    try:
        yunara.run_cli(["late-yuntal", "half5"])

        assert called == [True]
        assert "yuntal25" not in yunara.CANDIDATES_BY_SLOT[1]
    finally:
        yunara.set_yuntal_min_slot(1)


@pytest.mark.parametrize("module", PORTED_MODULES)
def test_ported_champions_expose_build_spec_and_half_options(module):
    """이관된 챔피언은 공통 엔진 어댑터(build_spec + 하프 후보 열거)를 갖춘다."""
    spec = module.build_spec()

    assert isinstance(spec, receding.RecedingSpec)
    assert spec.horizon == 5
    assert set(spec.candidates_by_slot) == {1, 2, 3, 4, 5}
    assert spec.include_last_half is False, "5코어 하프는 기본 생략"
    # 후보 아무 아이템이나 하나 골라 하프 구성이 나오는지 (조합식 있는 키여야 한다)
    sample = next(k for k in spec.candidates_by_slot[2] if spec.half_options(k))
    assert all(isinstance(names, tuple) for names in spec.half_options(sample))
