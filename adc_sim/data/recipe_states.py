"""조합 트리의 '부분 보유' 상태(하프 코어) 열거·선정.

receding-horizon 탐색에서 한 코어 아이템 x 를 고를 때, 그 아이템으로 가는 중간 시점
(대략 절반 가격을 쓴 시점)의 파워를 같이 평가하기 위한 데이터 계층이다.

규칙 (사용자 확정 2026-09-15):
- 후보는 **목표 아이템 x 의 하위템만**. 조합 트리를 재귀적으로 내려가며 하위템의
  하위템도 개별 구매 대상으로 본다(예: 경계 = 곡궁 + 롱소드 2개).
- 예산 창 `[lo, hi]`, `lo = ceil100(cost_x / 2)`, `hi = lo + 100`.
- 창이 비면 `lo` 를 100씩 내려 처음 비지 않는 구간을 쓴다. **상단 완화는 없다**
  (hi 를 넘는 상태는 어떤 경우에도 후보가 아니다).
- 창 안에서 고르는 기준(마지널 DPG)은 시뮬이 필요하므로 여기서 정하지 않는다.
  이 모듈은 '합법 후보 목록'까지만 만든다.

컴포넌트 스탯은 ITEM_CATALOG(나무위키 정규화 데이터)에서 오고, STAT_KEYS 에 없는
항목(ms_percent, gold_per_10 등)과 컴포넌트 고유 패시브는 미모델이다. [Hypothesis]
"""
from functools import lru_cache
from itertools import product

from adc_sim.data.items_data import ITEM_CATALOG, ITEMS, STAT_KEYS

# 하위 재료 중 완성품과 같은 관통 배타 규칙을 받는 것들.
# 역병의 보석은 인게임에서 공허의 지팡이·경계 등과 동시 보유가 불가능하다(나무위키 명시).
COMPONENT_MAGIC_PEN_EXCLUSIVE = frozenset({"역병의 보석"})
COMPONENT_ARMOR_PEN_EXCLUSIVE = frozenset({"최후의 속삭임"})

WINDOW_STEP = 100


@lru_cache(maxsize=None)
def _node_states(name):
    """재료 노드 하나의 (비용, 보유 재료 튜플) 상태 목록.

    미보유(0)·부분 보유(하위 재료 일부)·완전 보유(노드 자신) 전부를 포함한다.
    """
    entry = ITEM_CATALOG.get(name)
    if entry is None:
        raise KeyError(f"ITEM_CATALOG 에 없는 재료: {name}")
    states = {(0, ()), (entry["cost"], (name,))}
    if entry["builds_from"]:
        for combo in product(*(_node_states(child) for child in entry["builds_from"])):
            cost = sum(state[0] for state in combo)
            if 0 < cost < entry["cost"]:
                owned = tuple(sorted(sum((list(state[1]) for state in combo), [])))
                states.add((cost, owned))
    return tuple(sorted(states))


@lru_cache(maxsize=None)
def partial_states(item_key):
    """아이템 키의 모든 부분 보유 상태 (비용 오름차순, 완성·미보유 제외)."""
    recipe = ITEMS[item_key].get("recipe")
    if not recipe:
        return ()
    full_cost = ITEMS[item_key]["cost"]
    states = set()
    for combo in product(*(_node_states(name) for name in recipe)):
        cost = sum(state[0] for state in combo)
        if not 0 < cost < full_cost:
            continue
        owned = tuple(sorted(sum((list(state[1]) for state in combo), [])))
        states.add((cost, owned))
    return tuple(sorted(states))


def half_core_window(item_key):
    """하프 코어 예산 창 (lo, hi) — lo = 절반 가격 100단위 올림, hi = lo + 100."""
    cost = ITEMS[item_key]["cost"]
    lo = -(-(cost / 2.0) // WINDOW_STEP) * WINDOW_STEP
    lo = int(lo)
    return lo, lo + WINDOW_STEP


@lru_cache(maxsize=None)
def half_core_candidates(item_key):
    """창 규칙(하단 완화만)을 적용한 하프 코어 후보 목록.

    창 `[lo, hi]` 안에 상태가 없으면 lo 를 WINDOW_STEP 씩 내려 처음 비지 않는 구간을
    쓴다. hi 는 절대 올리지 않는다. 후보가 아예 없으면 빈 튜플(= 하프 상태 없음).
    """
    states = partial_states(item_key)
    if not states:
        return ()
    lo, hi = half_core_window(item_key)
    while lo > 0:
        found = tuple(state for state in states if lo <= state[0] <= hi)
        if found:
            return found
        lo -= WINDOW_STEP
    return ()


def component_stats(owned_names):
    """보유 재료 이름들의 스탯 합 (STAT_KEYS 에 있는 항목만)."""
    total = {}
    for name in owned_names:
        for stat_key, value in ITEM_CATALOG[name]["stats"].items():
            if stat_key in STAT_KEYS:
                total[stat_key] = total.get(stat_key, 0) + value
    return total


def component_pen_flags(owned_names):
    """보유 재료가 방관/마관 배타 슬롯을 차지하는지 (armor, magic) 여부."""
    armor = any(name in COMPONENT_ARMOR_PEN_EXCLUSIVE for name in owned_names)
    magic = any(name in COMPONENT_MAGIC_PEN_EXCLUSIVE for name in owned_names)
    return armor, magic
