"""LethalTempo/PressTheAttack 적응형 온힛: bonus AP>bonus AD 면 마법, 아니면 물리(동률 물리).
AP 빌드(코그모 등)는 마법 → 마저 경감·마관·Shadowflame 경로를 탄다.
Run: .venv/bin/python -m tests.test_adaptive_runes
"""
from adc_sim.runes import LethalTempo, PressTheAttack, _adaptive_split
from adc_sim.champion import CogMaw, Target
from adc_sim.data.items_registry import create_item_from_key


def test_adaptive_split_direction():
    class S:
        pass
    ap = S(); ap.total_ap = 100; ap.bonus_ad = 30
    assert _adaptive_split(50, ap) == (0, 50)     # AP>AD → 마법
    adc = S(); adc.total_ap = 0; adc.bonus_ad = 60
    assert _adaptive_split(50, adc) == (50, 0)     # AD>AP → 물리
    tie = S(); tie.total_ap = 40; tie.bonus_ad = 40
    assert _adaptive_split(50, tie) == (50, 0)     # 동률 → 물리(LoL 규칙)


def test_lethaltempo_magic_on_ap_build():
    c = CogMaw(level=13, w_level=4, q_level=3, e_level=2, r_level=2); c.init_combat_state()
    c.add_item(create_item_from_key("nashor"))     # AP80/AD0 → AP>AD
    lt = LethalTempo(); lt.stacks = lt.max_stacks; c.set_rune(lt)
    phys, magic = lt.get_on_hit_damage(Target(hp=2000, armor=100, magic_resist=50), c)
    assert phys == 0 and magic > 0


def test_lethaltempo_physical_on_ad_build():
    c = CogMaw(level=13, w_level=4); c.init_combat_state()
    c.add_item(create_item_from_key("kraken"))     # AD45/AP0 → AD>AP
    lt = LethalTempo(); lt.stacks = lt.max_stacks
    phys, magic = lt.get_on_hit_damage(Target(hp=2000, armor=100, magic_resist=50), c)
    assert magic == 0 and phys > 0


def test_presstheattack_adaptive_magic_on_ap_build():
    c = CogMaw(level=13, w_level=4); c.init_combat_state()
    c.add_item(create_item_from_key("nashor"))     # AP>AD
    pta = PressTheAttack(); c.set_rune(pta)
    for _ in range(3):                              # 3타 누적 → active
        pta.on_attack(c)
    phys, magic = pta.get_on_hit_damage(Target(hp=2000, armor=100, magic_resist=50), c)
    assert phys == 0 and magic > 0, (phys, magic)


if __name__ == "__main__":
    for nm, f in sorted(globals().items()):
        if nm.startswith("test_") and callable(f):
            f(); print(f"PASS {nm}")
    print("ALL PASS")
