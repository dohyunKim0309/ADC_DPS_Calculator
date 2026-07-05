"""C44(Hextech Scope C44) 확대 증폭 — 26.13 버프: 500 거리일 때 최대 10%."""
from adc_sim.items import HextechScopeC44, Item
from adc_sim.champion import Champion
from adc_sim.data.items_registry import create_item_from_key


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


class _FakeMagicOnhit(Item):
    """온힛 마법 100 고정 — C44 온힛 증폭 검증용."""
    def __init__(self):
        super().__init__("FakeMagicOnhit")

    def on_hit(self, target, champion):
        return 0.0, 100.0, 0.0, 0.0


class _Dummy:
    armor = 0.0
    mr = 0.0
    max_hp = 1000.0
    current_hp = 1000.0


def _make_champ_with_c44():
    champ = Champion(name="T", base_ad=100, base_as=1.0, as_ratio=1.0,
                     as_growth=0.0, base_range=550, level=1)
    champ.add_item(create_item_from_key("c44"))
    champ.add_item(_FakeMagicOnhit())
    return champ


def test_c44_amps_magic_onhit_channel():
    champ = _make_champ_with_c44()
    result = champ.get_one_hit_damage(_Dummy())
    magic_onhit = result[3]
    assert abs(magic_onhit - 100.0 * 1.10) < 1e-6


def test_c44_multiplies_last_damage_amp_for_true_onhit():
    champ = _make_champ_with_c44()
    champ.get_one_hit_damage(_Dummy())
    assert abs(champ._last_damage_amp - 1.10) < 1e-9
