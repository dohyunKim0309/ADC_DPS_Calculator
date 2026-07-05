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


def test_c44_does_not_amp_generic_onhit():
    champ = _make_champ_with_c44()
    result = champ.get_one_hit_damage(_Dummy())
    assert abs(result[3] - 100.0) < 1e-6


def test_c44_does_not_touch_last_damage_amp():
    champ = _make_champ_with_c44()
    champ.get_one_hit_damage(_Dummy())
    assert abs(champ._last_damage_amp - 1.0) < 1e-9


def test_c44_amps_cogmaw_w_onhit_bug():
    from adc_sim.champion import CogMaw

    def w_magic(with_c44):
        cog = CogMaw(level=15, q_level=4, w_level=5, e_level=3, r_level=2)
        cog.init_combat_state()
        cog.w_active = True
        if with_c44:
            cog.add_item(create_item_from_key("c44"))
        return cog.get_champion_onhit(_Dummy())[1]

    base = w_magic(False)
    amped = w_magic(True)
    assert base > 0
    # c44 는 AP 0 → W pct 불변, 코그모 사거리 500 → modifier 0.10 → 정확히 ×1.10
    assert abs(amped / base - 1.10) < 1e-9
