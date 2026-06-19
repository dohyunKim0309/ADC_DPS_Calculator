"""아이템 키 → 인스턴스 통합 레지스트리.

기존에 ashe/kaisa/corki 시뮬에 각각 복제돼 있던 create_item_from_key 를 하나로 합친 것.
스탯/가격/이름은 items_data.ITEMS(데이터)에서 주입하므로 데이터가 런타임 출처이고,
동작·상태(stack, spellblade, manaflow 등)는 adc_sim/items.py 의 클래스가 그대로 담당한다.

(다음 단계 예정: items.py 클래스의 하드코딩 스탯 제거 → 데이터를 유일 출처로.)
"""
from adc_sim import items as _items
from adc_sim.data.items_data import ITEMS, STAT_KEYS

# 키 → 동작 클래스 (모듈 로드시 1회 해석)
_BEHAVIOR_CLASS = {key: getattr(_items, spec["behavior"]) for key, spec in ITEMS.items()}


def _apply_data(item, key):
    """데이터(ITEMS[key])의 이름/가격/스탯을 인스턴스에 주입(상태는 건드리지 않음)."""
    spec = ITEMS[key]
    item.name = spec["name"]
    item.cost = spec["cost"]
    stats = spec["stats"]
    for stat_key in STAT_KEYS:
        item.stats[stat_key] = stats.get(stat_key, 0)
    return item


def create_item_from_key(item_key, yuntal_crit=None):
    """아이템 키로 인스턴스 생성.

    yuntal_crit: 윤탈 치명타(구매 코어 타이밍별). None이면 데이터의 yuntal_default_crit.
    """
    if item_key not in ITEMS:
        raise ValueError(f"Unknown item key: {item_key}")
    cls = _BEHAVIOR_CLASS[item_key]

    if item_key in ("yuntal", "yuntal25"):
        default_crit = ITEMS[item_key].get("yuntal_default_crit", 0.25)
        crit = default_crit if yuntal_crit is None else yuntal_crit
        item = cls(crit=crit)
        _apply_data(item, item_key)
        item.stats["crit"] = crit  # 데이터 주입이 crit 을 0으로 덮으므로 런타임 값 복원
        return item

    item = cls()
    _apply_data(item, item_key)

    if item_key == "muramana":
        # 1코어부터 무라마나(마나 풀스택) 상태로 비교 — corki 기존 동작 보존
        item.is_muramana = True
        item.name = "Muramana"
        item.mana_stacked = item.max_mana_stack

    return item


def get_item_ad_from_key(item_key):
    """키의 AD 값(라벨/정렬용)."""
    return create_item_from_key(item_key).stats.get("ad", 0)
