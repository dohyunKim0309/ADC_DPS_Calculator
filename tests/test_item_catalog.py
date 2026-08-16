from collections import Counter

import pytest

from adc_sim.data.items_data import (
    CATALOG_SOURCE_MODIFIED_AT,
    CATALOG_STAT_KEYS,
    ITEM_CATALOG,
)
from adc_sim.data.items_registry import create_catalog_item, create_item_from_key


def test_four_namuwiki_sources_are_normalized():
    """네 원문에서 추출한 항목 수와 문서 시각을 고정해 누락을 감지한다."""
    assert Counter(item["tier"] for item in ITEM_CATALOG.values()) == {
        "basic": 15,
        "epic": 44,
        "starter": 13,
        "consumable": 9,
    }
    assert CATALOG_SOURCE_MODIFIED_AT == {
        "item_basic": "2026-06-19 18:37:42",
        "item_epic": "2026-07-03 21:19:13",
        "item_start": "2026-07-03 21:16:14",
        "item_consumable": "2026-07-10 18:21:51",
    }


def test_kaisa_evolution_and_lifesteal_components_are_preserved():
    """카이사 진화 투자와 피흡 등급에 필요한 핵심 재료 수치를 검증한다."""
    assert ITEM_CATALOG["단검"]["cost"] == 250
    assert ITEM_CATALOG["단검"]["stats"] == {"as": 0.10}
    assert ITEM_CATALOG["흡혈의 낫"]["stats"]["lifesteal"] == 0.07
    assert ITEM_CATALOG["흡혈의 낫"]["builds_from"] == ("롱소드",)
    assert "몰락한 왕의 검" in ITEM_CATALOG["흡혈의 낫"]["builds_into"]


def test_catalog_stats_use_declared_keys_and_recipes_do_not_exceed_cost():
    """오탈자 스탯과 기본 재료 가격보다 싼 서사급 조합을 차단한다."""
    used_keys = {
        stat
        for item in ITEM_CATALOG.values()
        for stat in item["stats"]
    }
    assert used_keys <= CATALOG_STAT_KEYS

    for name, item in ITEM_CATALOG.items():
        if item["tier"] != "epic" or not item["builds_from"]:
            continue
        component_cost = sum(ITEM_CATALOG[part]["cost"] for part in item["builds_from"])
        assert component_cost <= item["cost"], name


def test_registry_uses_split_modules_and_preserves_sustain_stats():
    """기존 영문 키 생성 경로가 새 모듈과 피흡 스탯을 사용하는지 검증한다."""
    botrk = create_item_from_key("botrk")
    glutton = create_item_from_key("glutton")
    doran_bow = create_item_from_key("doranbow")

    assert type(botrk).__module__ == "adc_sim.core_items"
    assert type(glutton).__module__ == "adc_sim.utility_items"
    assert botrk.stats["lifesteal"] == 0.10
    assert glutton.stats["omnivamp"] == 0.04
    assert doran_bow.stats["omnivamp"] == 0.015


def test_umbral_glaive_runtime_stats_are_registered():
    """그림자 검 영문 키가 원문 가격·공격 스탯과 전용 동작 클래스를 사용한다."""
    umbral = create_item_from_key("umbral")

    assert type(umbral).__module__ == "adc_sim.core_items"
    assert umbral.cost == 2800
    assert umbral.stats["ad"] == 60
    assert umbral.stats["lethality"] == 18
    assert umbral.stats["cdr"] == 15


def test_catalog_interface_rejects_unimplemented_effects_by_default():
    """미구현 패시브가 정적 스탯만으로 조용히 시뮬레이션되는 것을 막는다."""
    recurve = create_catalog_item("곡궁")
    assert type(recurve).__module__ == "adc_sim.component_items"
    assert recurve.on_hit(None, None) == (15, 0, 0, 0)

    with pytest.raises(NotImplementedError):
        create_catalog_item("정찰병의 새총")

    static_only = create_catalog_item("정찰병의 새총", allow_unsupported=True)
    assert static_only.effect_status == "unsupported"
    assert static_only.stats["as"] == 0.20
