import pytest

from adc_sim.simulations import kaisa as greedy
from adc_sim.simulations.kaisa import (
    build_kaisa_core_report_meta,
    evaluate_kaisa_evolution_investments,
    format_kaisa_evolution_summary,
)


def test_q_evolution_uses_completed_guinsoo_when_pickaxe_is_not_enough():
    """도란활 경로에서 곡괭이로 Q 100을 못 넘으면 2코어 완성 누적가를 반환한다."""
    result = evaluate_kaisa_evolution_investments(
        ("kraken", "guinsoo", "ie"),
        2,
        doran_key="doranbow",
        boots_key="berserker",
    )["q"]

    assert result["evolved"] is True
    assert result["possible"] is True
    assert result["investment_gold"] == 400 + 1100 + 3000 + 3000
    assert result["milestone_type"] == "core_complete"
    assert result["components"] == ["구인수의 격노검"]


def test_q_evolution_counts_every_purchase_through_on_recipe_pickaxe():
    """2코어(구인수) 완성 시점의 Q 진화 누적가를 반환한다.

    ⚠️ 2026-08-11 성장 곡선 정정(선형 → 실 LoL, adc_sim/growth.py)으로 결과가 바뀌었다.
    선형 근사에선 성장 AD 가 과대평가돼 **곡괭이(5425g)에서 100.8 로 진화**했지만,
    실제 곡선에선 곡괭이 시점에 100 을 못 넘겨 **구인수 완성(7550g)까지 밀린다**(107.815).
    즉 Q 진화 실비용이 2125g 더 비싸다. 함수 이름은 옛 시나리오를 가리키므로 개명 후보.
    """
    result = evaluate_kaisa_evolution_investments(
        ("kraken", "guinsoo", "ie"),
        2,
        doran_key="doranblade",
        boots_key="berserker",
    )["q"]

    assert result["evolution_value"] == 107.815     # 구 100.8 (선형 근사)
    assert result["investment_gold"] == 450 + 1100 + 3000 + 3000   # 구 ... + 875(곡괭이)
    assert result["evolution_core_tier"] == 2
    assert result["milestone_type"] == "core_complete"             # 구 "component"
    assert result["components"] == ["구인수의 격노검"]              # 구 ["곡괭이"]


def test_w_evolution_follows_nested_guinsoo_amp_tome_recipe():
    """내셔 다음 구인수의 증폭의 고서에서 W가 진화하는 누적 가격을 계산한다."""
    result = evaluate_kaisa_evolution_investments(
        ("nashor", "guinsoo", "pd", "ie"),
        1,
        doran_key="doranblade",
        boots_key="berserker",
    )["w"]

    assert result["evolved"] is False
    assert result["possible"] is True
    assert result["investment_gold"] == 450 + 1100 + 2900 + 400
    assert result["components"] == ["증폭의 고서"]


def test_e_evolution_counts_on_path_dagger_after_two_cores():
    """2코어 E 98%가 다음 PD의 단검에서 진화하는 실제 누적 가격을 검증한다."""
    result = evaluate_kaisa_evolution_investments(
        ("guinsoo", "yuntal", "pd", "ie"),
        2,
        doran_key="doranbow",
        boots_key="glutton",
    )["e"]

    assert result["current_value"] == 0.98
    assert result["evolved"] is False
    assert result["possible"] is True
    assert result["investment_gold"] == 400 + 1000 + 3000 + 3100 + 250
    assert result["evolution_core_tier"] == 3
    assert result["components"] == ["단검"]


def test_e_evolution_does_not_buy_dagger_without_future_dagger_recipe():
    """3·4코어 조합식에 단검이 없으면 2코어 후 임의 단검을 추가하지 않는다."""
    result = evaluate_kaisa_evolution_investments(
        ("guinsoo", "yuntal", "ie", "ldr"),
        2,
        doran_key="doranbow",
        boots_key="glutton",
    )["e"]

    assert result["current_value"] == 0.98
    assert result["components"] != ["단검"]
    assert result["milestone_type"] == "core_complete"
    assert result["evolution_core_tier"] == 3
    assert result["investment_gold"] == 400 + 1000 + 3000 + 3100 + 3500


def test_evolution_is_impossible_without_required_stat_by_four_cores():
    """실제 4코어 경로 어디에도 AP가 없으면 W 진화를 불가능으로 반환한다."""
    result = evaluate_kaisa_evolution_investments(
        ("kraken", "yuntal", "pd", "ie"),
        2,
        doran_key="doranblade",
        boots_key="berserker",
    )["w"]

    assert result["evolved"] is False
    assert result["possible"] is False
    assert result["investment_gold"] is None
    assert result["components"] == []


def test_kaisa_report_meta_flattens_cumulative_evolution_gold_values():
    """power_compare에 현재 진화 여부와 4코어 내 누적 진화 가격을 함께 제공한다."""
    meta = build_kaisa_core_report_meta(
        ("guinsoo", "yuntal", "pd", "ie"),
        2,
        doran_key="doranbow",
        boots_key="glutton",
    )

    assert set(meta["evolutions"]) == {"q", "w", "e"}
    assert meta["q_evolution_gold"] == 6050
    assert meta["w_evolution_gold"] is None
    assert meta["e_evolution_gold"] == 7750
    assert meta["q_evolved"] is True
    assert meta["e_evolved"] is False
    assert meta["e_evolution_possible"] is True
    assert not any(key.endswith("_evolution_grade") for key in meta)


def test_evolution_investment_rejects_unknown_core_tier():
    """지원하지 않는 코어 시점이 조용히 잘못 계산되지 않도록 차단한다."""
    with pytest.raises(ValueError):
        evaluate_kaisa_evolution_investments(("kraken",), 0)


def test_evolution_summary_prints_timing_value_and_cumulative_gold():
    """순위 두 번째 줄에 진화 타이밍·판정값·누적 골드와 불가 상태를 모두 표시한다."""
    summary = format_kaisa_evolution_summary(
        ("kraken", "guinsoo", "ie"),
        doran_key="doranbow",
        boots_key="berserker",
    )

    # AD 값은 2026-08-11 성장 곡선 정정(선형 → 실 LoL)으로 109.0 → 105.8.
    assert "Q: 2C 완성 · AD 105.8 · 7500g" in summary
    assert "W: 불가" in summary
    # AS 값은 광전사 공속(items_data)이 더해진 수치 — 2026-08-11 신발 버프(25%→30%)로 104.4→109.4.
    assert "E: 2C 재료(단검) · AS 107.1% · 4750g" in summary   # 성장 곡선 정정: 109.4 → 107.1


def test_kaisa_receding_horizon_keeps_two_core_stat_filters(monkeypatch):
    """베인식 미래 조합 생성에서도 카이사 기존 2코어 AD·공속 하한을 유지한다."""
    monkeypatch.setattr(greedy, "CANDIDATES_BY_SLOT", {
        1: ["ie", "kraken"],
        2: ["pd", "terminus"],
    })

    combos = list(greedy._enumerate_future_combos([], 1, horizon=2))

    assert combos == [("ie", "pd"), ("kraken", "terminus")]


def test_kaisa_receding_horizon_output_preserves_evolution_display(capsys):
    """새 기본 선택 표가 최종 궤적의 Q/W/E 진화 조건 한 줄을 계속 출력한다."""
    out = {
        "trajectory": ("kraken", "guinsoo", "nashor", "terminus", "shadowflame"),
        "steps": [],
    }

    greedy.print_scenario(
        "test",
        out,
        {"hits": 0, "misses": 0},
        doran_key="doranblade",
        boots_key="berserker",
        gamma=0.8,
    )

    printed = capsys.readouterr().out
    assert "EVO | Q:" in printed
    assert "| W:" in printed
    assert "| E:" in printed


def test_kaisa_cli_defaults_to_receding_horizon(monkeypatch):
    """인자 없는 카이사 CLI가 보존된 전수 랭킹 대신 새 기본 탐색을 호출한다."""
    called = []
    monkeypatch.setattr(greedy, "main", lambda gamma=None: called.append(gamma))
    monkeypatch.setattr(
        greedy,
        "main_legacy_ranking",
        lambda: (_ for _ in ()).throw(AssertionError("legacy ranking called")),
    )

    greedy.run_cli([])

    assert called == [greedy.GAMMA]
