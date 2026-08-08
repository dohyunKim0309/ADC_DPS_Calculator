"""LethalTempo/PressTheAttack 적응형 온힛: bonus AP>bonus AD 면 마법, 아니면 물리(동률 물리).
AP 빌드(코그모 등)는 마법 → 마저 경감·마관·Shadowflame 경로를 탄다.
Run: .venv/bin/python -m tests.test_adaptive_runes
"""
from adc_sim.runes import LethalTempo, PressTheAttack, _adaptive_split
from adc_sim.champion import CogMaw, KaiSa, Target
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


def test_kaisa_alacrity_attack_speed_does_not_count_for_e_evolution():
    """Alacrity raises combat AS but must not contribute to Kai'Sa E evolution.

    불변식: 민첩함(룬 공속 18%)을 얹어도 `_get_evolution_bonus_as()`(아이템+레벨 성장)는
    그대로여야 한다. 룬 공속이 새면 0.85+0.18(레벨)+0.18(룬)=1.21 로 튄다.

    [2026-08-08 갱신] 기대값 0.98 → 1.03. 윤탈 공속 40→45% 버프(items_data, 커밋 eed5894)가
    아이템 합을 0.80 → 0.85 로 올린 결과다. 그 여파로 이 빌드는 lvl11 에서 이미 진화
    문턱 1.0 을 넘어(1.03) `has_e_evolved()` 가 True 가 되므로, 옛 `is False` 단정은
    폐기하고 "룬이 진화 공속에 안 잡힌다"는 본래 의도를 불변식으로 직접 검증한다.
    """
    kaisa = KaiSa(level=11, q_level=5, w_level=5, e_level=3, r_level=2)
    for key in ("doranbow", "glutton", "guinsoo", "yuntal"):
        kaisa.add_item(create_item_from_key(key))

    combat_as_without_rune = kaisa.current_attack_speed
    evolution_as_without_rune = kaisa._get_evolution_bonus_as()
    kaisa.bonus_as_percent += 0.18

    assert kaisa.current_attack_speed > combat_as_without_rune       # 전투 공속은 오른다
    assert kaisa._get_evolution_bonus_as() == evolution_as_without_rune  # 진화 공속은 불변
    assert abs(evolution_as_without_rune - 1.03) < 1e-9              # 0.85 아이템 + 0.18 레벨


def test_kaisa_item_attack_speed_still_counts_for_e_evolution():
    """Replacing lifesteal boots with AS boots must make the same build E-evolved.

    [2026-08-08 갱신] 기대값 1.23 → 1.28 (윤탈 공속 40→45% 버프 반영).
    """
    kaisa = KaiSa(level=11, q_level=5, w_level=5, e_level=3, r_level=2)
    for key in ("doranbow", "berserker", "guinsoo", "yuntal"):
        kaisa.add_item(create_item_from_key(key))
    kaisa.bonus_as_percent += 0.18

    assert abs(kaisa._get_evolution_bonus_as() - 1.28) < 1e-9
    assert kaisa.has_e_evolved() is True


if __name__ == "__main__":
    for nm, f in sorted(globals().items()):
        if nm.startswith("test_") and callable(f):
            f(); print(f"PASS {nm}")
    print("ALL PASS")
