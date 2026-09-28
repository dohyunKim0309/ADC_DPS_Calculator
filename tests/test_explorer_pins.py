# -*- coding: utf-8 -*-
"""탐색기 JSON 불변식 — 고정 전개(PINNED_BY_SLOT)가 모든 노드에서 지켜지는지.

사용자 지정(2026-09-28): **1코어 C44, 3코어부터 루난·경계·도미닉은 순위와 무관하게
항상 전개**한다. 전개 규칙(`_main_items`)을 건드리거나 데이터를 다시 뽑을 때 이 규칙이
조용히 깨지지 않게 배포 JSON 자체를 검사한다.

"그 칸에 합법이면" 이 조건이다 — 이미 산 아이템이나 관통 배타(도미닉 ↔ 경계·징수)로
후보 목록에 아예 없는 경우는 전개할 것도 없으므로 통과.
"""
import json
from pathlib import Path

import pytest

from tools import kaisa_explorer_data as K
from tools import yunara_explorer_data as Y

REPORTS = Path(__file__).resolve().parent.parent / "docs" / "reports"
CASES = [
    ("yunara", REPORTS / "yunara_explorer.json", Y.PINNED_BY_SLOT),
    ("kaisa", REPORTS / "kaisa_explorer.json", K.PINNED_BY_SLOT),
]


def _load(path):
    if not path.exists():
        pytest.skip(f"{path.name} 없음 — 생성기를 먼저 돌릴 것")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("champ,path,pinned", CASES)
def test_pinned_items_are_always_expanded(champ, path, pinned):
    """고정 항목이 후보에 있으면 반드시 tier='main'(= 자식 노드가 열린다)."""
    data = _load(path)
    misses = []
    for situation, nodes in data["nodes"].items():
        for prefix, cands in nodes.items():
            slot = 1 if prefix == "" else len(prefix.split("-")) + 1
            for item in pinned.get(slot, ()):  # 슬롯에 고정이 없으면 빈 튜플
                row = cands.get(item)
                if row is not None and row["tier"] != "main":
                    misses.append(f"{champ} {situation} [{prefix}] {item}")
    assert not misses, "고정 전개 누락: " + ", ".join(misses[:10])


@pytest.mark.parametrize("champ,path,pinned", CASES)
def test_expanded_pinned_items_have_child_nodes(champ, path, pinned):
    """5코어 전이라면 고정 항목을 고른 뒤의 노드가 실제로 존재한다."""
    data = _load(path)
    horizon = data["meta"]["horizon"]
    misses = []
    for situation, nodes in data["nodes"].items():
        for prefix, cands in nodes.items():
            slot = 1 if prefix == "" else len(prefix.split("-")) + 1
            if slot >= horizon:          # 마지막 칸은 자식이 없다
                continue
            for item in pinned.get(slot, ()):
                if item not in cands:
                    continue
                child = item if prefix == "" else prefix + "-" + item
                if child not in nodes:
                    misses.append(f"{champ} {situation} [{child}]")
    assert not misses, "고정 항목의 자식 노드 없음: " + ", ".join(misses[:10])
