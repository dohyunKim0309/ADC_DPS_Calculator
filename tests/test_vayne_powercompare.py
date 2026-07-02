"""Task 6: power_compare 에 Vayne 통합 확인(컴파일·데이터 산출)."""
from adc_sim.simulations import power_compare as pc


def test_simulate_compare_stat_supports_vayne():
    from adc_sim.simulations.vayne import CONTROL_PATH
    cfg = {"path": list(CONTROL_PATH), "doran": "doranblade", "boots": "berserker", "rune_as": 0.0}
    result = pc._simulate_compare_stat("Vayne", cfg, core_tier=2)
    assert result["champion"] == "Vayne"
    assert result["dps"] > 0 and result["gold"] > 0


def test_vayne_in_plot_color_map():
    import inspect
    src = inspect.getsource(pc._plot_combined_compare)
    assert "Vayne" in src
