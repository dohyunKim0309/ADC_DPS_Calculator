"""vayne.py에 통합된 기본 receding-horizon 탐색의 시나리오 전달 테스트."""

from adc_sim.runes import CoupDeGrace, CutDown, PressTheAttack
from adc_sim.simulations import receding, vayne as greedy


def test_pta_alacrity_sub_rune_mode_wires_both_scenarios(monkeypatch):
    """전용 모드가 동일 패키지·민첩함에서 두 보조룬을 각각 한 번 실행하는지 검증한다."""
    created = []
    solved_gamma = []

    class FakeCache:
        """실제 전수 시뮬 없이 SimCache 생성 인자만 기록한다."""

        def __init__(self, keystone_cls, sub_rune_cls, doran_key, boots_key, rune_as_bonus):
            created.append((keystone_cls, sub_rune_cls, doran_key, boots_key, rune_as_bonus))
            self.hits = 1
            self.misses = 1

    def fake_solve(spec, cache):
        """전용 모드가 spec 에 실어 보낸 할인율을 기록하고 최소 결과를 반환한다."""
        solved_gamma.append(spec.gamma)
        return {"trajectory": [], "steps": []}

    monkeypatch.setattr(greedy, "SimCache", FakeCache)
    monkeypatch.setattr(receding, "solve", fake_solve)
    monkeypatch.setattr(greedy, "print_scenario", lambda *args, **kwargs: None)

    greedy.main_pta_alacrity_sub_runes(gamma=0.8)

    assert created == [
        (PressTheAttack, CutDown, "doranbow", "glutton", 0.18),
        (PressTheAttack, CoupDeGrace, "doranbow", "glutton", 0.18),
    ]
    assert solved_gamma == [0.8, 0.8]


def test_vayne_cli_defaults_to_receding_horizon(monkeypatch):
    """인자 없는 vayne CLI가 기존 전수 랭킹이 아니라 통합된 기본 탐색을 호출한다."""
    called = []
    monkeypatch.setattr(greedy, "main", lambda gamma=None: called.append(gamma))
    monkeypatch.setattr(
        greedy,
        "main_legacy_ranking",
        lambda: (_ for _ in ()).throw(AssertionError("legacy ranking called")),
    )

    greedy.run_cli([])

    assert called == [greedy.GAMMA]


def test_default_scenarios_are_ordered_and_include_both_sub_runes(monkeypatch):
    """기본 탐색이 8개 케이스를 요청된 룬·보조룬 순서로 전달하는지 검증한다."""
    captured = []
    monkeypatch.setattr(greedy, "_run_scenarios", lambda scenarios, gamma: captured.extend(scenarios))

    greedy.main(gamma=0.8)

    assert len(captured) == 8
    assert [row[1] for row in captured] == [
        greedy.LethalTempo, greedy.LethalTempo, greedy.LethalTempo, greedy.LethalTempo,
        greedy.PressTheAttack, greedy.PressTheAttack, greedy.PressTheAttack, greedy.PressTheAttack,
    ]
    assert [row[3] for row in captured] == [0.0, 0.0, 0.18, 0.18, 0.0, 0.0, 0.18, 0.18]
    assert [row[2] for row in captured] == [
        greedy.CutDown, greedy.CoupDeGrace, greedy.CutDown, greedy.CoupDeGrace,
        greedy.CutDown, greedy.CoupDeGrace, greedy.CutDown, greedy.CoupDeGrace,
    ]


def test_slot_lookahead_only_truncates_requested_core_lookahead(monkeypatch):
    """1·2코어 3코어 lookahead 뒤에는 전체 horizon 재탐색을 유지한다.

    옛 vayne.solve_greedy 의 first/second_step_horizon 이 공통 엔진에서
    receding.solve(slot_lookahead={슬롯: 끝코어}) 로 일반화됐다.
    """
    observed_horizons = []

    class FakeCache:
        """아이템 개수에 비례한 단순 DPS·골드만 반환하는 탐색용 캐시."""

        def sim(self, items):
            return len(items) * 100.0, len(items) * 1000.0

        def sim_half(self, done, next_key, comps):
            return len(done) * 100.0 + 50.0, len(done) * 1000.0 + 500.0

    def fake_enumerate(spec, fixed, from_slot, horizon):
        """호출 lookahead를 기록하고 각 슬롯에 하나의 유효 미래 조합을 제공한다."""
        observed_horizons.append((from_slot, horizon))
        yield tuple(f"slot{from_slot}_{offset}" for offset in range(horizon - from_slot + 1))

    monkeypatch.setattr(receding, "enumerate_future_combos", fake_enumerate)

    spec = receding.RecedingSpec(
        title="Fake", candidates_by_slot={slot: [] for slot in range(1, 6)},
        pen_rule_ok=lambda keys: True, half_options=lambda key: ((),),
        gamma=0.8, horizon=5,
    )
    receding.solve(spec, FakeCache(), horizon=5, slot_lookahead={1: 3, 2: 3})

    assert observed_horizons == [(1, 3), (2, 3), (3, 5), (4, 5), (5, 5)]
