"""receding_core(공통 러너) == vayne.py 기존 receding-horizon 구현 동치성 검증.

축소 후보 풀 + 짧은 호라이즌에서 두 구현의 궤적·슬롯 점수·마지널 DPG 가 같아야 한다.
(AGENTS.md 5-4 Add Before Replace: vayne.py 원본은 그대로 두고 공통 러너를 추가했으므로,
"같은 방법론"이라는 주장을 이 테스트가 뒷받침한다.)

Run: .venv/bin/python -m pytest tests/test_receding_core.py -q
"""
from adc_sim.simulations import receding_core, vayne

SMALL_CANDIDATES = {
    1: ["botrk", "guinsoo", "kraken"],
    2: ["guinsoo", "terminus", "pd"],
    3: ["ie", "ldr", "pd"],
}
HORIZON = 3
GAMMA = 0.8
SIM_KWARGS = dict(doran_key="doranbow", boots_key="glutton", rune_as_bonus=0.0)


def _run_reference():
    """vayne.py 원본 solve_greedy 를 축소 풀로 실행한다(전역 후보표만 임시 교체)."""
    original = vayne.CANDIDATES_BY_SLOT
    vayne.CANDIDATES_BY_SLOT = SMALL_CANDIDATES
    try:
        cache = vayne.SimCache(
            vayne.LethalTempo, vayne.CutDown,
            doran_key=SIM_KWARGS["doran_key"], boots_key=SIM_KWARGS["boots_key"],
            rune_as_bonus=SIM_KWARGS["rune_as_bonus"],
        )
        return vayne.solve_greedy(cache, gamma=GAMMA, horizon=HORIZON)
    finally:
        vayne.CANDIDATES_BY_SLOT = original


def _run_generic():
    """공통 러너를 같은 시뮬 함수·후보 풀로 실행한다."""
    def simulate(path, tier, **kwargs):
        return vayne.simulate_vayne_core_path(path, tier, **kwargs)

    cache = receding_core.SimCache(simulate, sim_kwargs=SIM_KWARGS)
    return receding_core.solve_greedy(cache, SMALL_CANDIDATES, GAMMA, HORIZON)


def test_generic_runner_matches_vayne_implementation():
    ref = _run_reference()
    got = _run_generic()

    assert got["trajectory"] == ref["trajectory"]
    assert len(got["steps"]) == len(ref["steps"]) == HORIZON

    for step_got, step_ref in zip(got["steps"], ref["steps"]):
        assert step_got["slot"] == step_ref["slot"]
        assert step_got["item"] == step_ref["item"]
        assert abs(step_got["score"] - step_ref["score"]) < 1e-9
        assert abs(step_got["dps"] - step_ref["dps"]) < 1e-9
        assert step_got["gold"] == step_ref["gold"]
        assert abs(step_got["marginal_dpg"] - step_ref["marginal_dpg"]) < 1e-9
        assert step_got["future_path_winner"] == step_ref["future_path_winner"]
        assert ([a["item"] for a in step_got["alternatives"]]
                == [a["item"] for a in step_ref["alternatives"]])


def test_evaluate_fixed_path_matches_slot1_score_of_same_path():
    """고정 경로 채점 = 그 경로를 slot1부터 그대로 따라갔을 때의 할인합."""
    def simulate(path, tier, **kwargs):
        return vayne.simulate_vayne_core_path(path, tier, **kwargs)

    cache = receding_core.SimCache(simulate, sim_kwargs=SIM_KWARGS)
    path = ("botrk", "guinsoo", "ie")
    score, per_tier = receding_core.evaluate_fixed_path(cache, path, GAMMA, HORIZON)
    manual, _ = receding_core.score_combo(cache, (), path, 1, 0.0, 0.0, GAMMA, HORIZON)
    assert abs(score - manual) < 1e-12
    assert [row[0] for row in per_tier] == [1, 2, 3]
