"""관통 배타 게임 규칙: 방관 ≤1 AND 마관 ≤1 (terminus 양쪽 겸비)."""
from adc_sim.data.items_data import (
    ARMOR_PEN_EXCLUSIVE, MAGIC_PEN_EXCLUSIVE, pen_rule_ok,
)


def test_exclusive_sets():
    assert ARMOR_PEN_EXCLUSIVE == frozenset({"ldr", "mortal", "terminus"})
    assert MAGIC_PEN_EXCLUSIVE == frozenset({"void", "terminus"})


def test_pen_rule_ok_cases():
    assert pen_rule_ok(("guinsoo", "nashor", "pd", "ie"))
    assert pen_rule_ok(("ldr", "void", "pd", "ie"))          # 방관1+마관1(다른 아이템) 합법
    assert pen_rule_ok(("terminus", "guinsoo", "pd", "ie"))
    assert not pen_rule_ok(("terminus", "void", "pd", "ie"))  # terminus 는 마관 겸비 → void 와 불법
    assert not pen_rule_ok(("terminus", "ldr", "pd", "ie"))
    assert not pen_rule_ok(("ldr", "mortal", "pd", "ie"))
    assert pen_rule_ok(("void", "pd"))                        # 부분 빌드도 판정 가능
