"""아이템 키 → 인스턴스 통합 레지스트리.

기존에 ashe/kaisa/corki 시뮬에 각각 복제돼 있던 create_item_from_key 를 하나로 합친 것.
스탯/가격/이름은 items_data.ITEMS(데이터)에서 주입하므로 데이터가 런타임 출처이고,
동작·상태(stack, spellblade, manaflow 등)는 역할별 item 모듈의 클래스가 담당한다.
"""
from adc_sim import component_items, core_items, utility_items
from adc_sim.item_base import Item
from adc_sim.data.items_data import (
    CATALOG_SOURCE_MODIFIED_AT,
    ITEM_CATALOG,
    ITEMS,
    STAT_KEYS,
)


_BEHAVIOR_MODULES = (core_items, component_items, utility_items)


def _resolve_behavior_class(class_name):
    """클래스 이름을 역할별 동작 모듈에서 찾아 반환한다.

    class_name은 ITEMS의 behavior 문자열이며, 찾지 못하면 설정 오류를 즉시 드러낸다.
    """
    for module in _BEHAVIOR_MODULES:
        if hasattr(module, class_name):
            return getattr(module, class_name)
    raise AttributeError(f"Unknown item behavior class: {class_name}")


# 키 → 동작 클래스 (모듈 로드시 1회 해석)
_BEHAVIOR_CLASS = {
    key: _resolve_behavior_class(spec["behavior"])
    for key, spec in ITEMS.items()
}


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


_CATALOG_BEHAVIOR_CLASS = {
    # 현재 서사급 중 전투 효과까지 검증된 것은 곡궁의 적중 시 물리 피해뿐이다.
    "곡궁": component_items.RecurveBow,
}


def create_catalog_item(item_name, allow_unsupported=False):
    """정규화된 한국어 아이템 이름으로 런타임 인스턴스를 생성한다.

    item_name은 ITEM_CATALOG의 키다. 미구현 효과가 있는 아이템은 기본적으로
    NotImplementedError를 내며, allow_unsupported=True일 때만 정적 스탯 전용 Item을
    반환한다. 반환 인스턴스에는 tier, 조합식, 출처와 effect_status도 보존한다.
    """
    if item_name not in ITEM_CATALOG:
        raise ValueError(f"Unknown catalog item: {item_name}")
    spec = ITEM_CATALOG[item_name]
    if spec["effect_status"] == "unsupported" and not allow_unsupported:
        raise NotImplementedError(f"Unsupported item effect: {item_name}")

    behavior = _CATALOG_BEHAVIOR_CLASS.get(item_name)
    item = behavior() if behavior is not None else Item(item_name)
    item.name = item_name
    item.cost = spec["cost"]
    item.stats.update(spec["stats"])
    item.tier = spec["tier"]
    item.builds_from = spec["builds_from"]
    item.builds_into = spec["builds_into"]
    item.effect_status = spec["effect_status"]
    item.source_file = spec["source_file"]
    item.source_modified_at = CATALOG_SOURCE_MODIFIED_AT[item.source_file]
    return item
