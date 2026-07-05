"""C44(Hextech Scope C44) 확대 증폭 — 26.13 버프: 500 거리일 때 최대 10%."""
from adc_sim.items import HextechScopeC44


class _StubChampion:
    def __init__(self, range_):
        self.range = range_


def test_c44_max_amp_at_500_range():
    item = HextechScopeC44()
    assert abs(item.get_damage_modifier(None, _StubChampion(500)) - 0.10) < 1e-9


def test_c44_scales_below_500():
    item = HextechScopeC44()
    assert abs(item.get_damage_modifier(None, _StubChampion(250)) - 0.05) < 1e-9


def test_c44_clamped_above_500():
    item = HextechScopeC44()
    assert abs(item.get_damage_modifier(None, _StubChampion(600)) - 0.10) < 1e-9


def test_c44_vision_focus_buff_adds_range():
    item = HextechScopeC44()
    item.is_buff_active = True
    assert abs(item.get_damage_modifier(None, _StubChampion(400)) - 0.10) < 1e-9
