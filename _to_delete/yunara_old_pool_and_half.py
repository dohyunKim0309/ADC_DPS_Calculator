"""폐기 예정 코드 보관소 — 유나라 하프/풀 구버전 규칙 (2026-09-15).

교체된 것들이라 **어디서도 import 하지 않는다.** 되돌리려면 그대로 복사하면 된다.

1) 슬롯별 손코딩 후보 리스트(CORE1~5_CANDIDATES)
   → CORE_POOL 합집합 + 슬롯 규칙(윤탈 1~2코어, 1코어 제외 5종)으로 교체.
     옛 리스트의 "몰락 1~2코어 한정", "3코어 공속템 전면 제외"는 근거가 없었다.
2) 하프 티어 전역 골드 캡 1600 + 조합식 폴백(FALLBACK_RECIPES)
   → 아이템별 예산창 [ceil100(가격/2), +100] (recipe_states) 로 교체.
     폴백은 items_data 에 진짜 조합식이 들어오면서 필요 없어졌다
     (루난·고연포·공허의 하위템이 실제 조합식과 달랐다).
3) 하프 후보 열거 _component_subsets / 선택 _half_cache_sim·_mixed_half_sim
   → recipe_states.half_core_candidates + 마지널 DPG 기준 선택(sim_half)으로 교체.
     옛 선택 기준은 절대 DPS 라 점수에 들어가는 축(마지널 DPG)과 어긋나 있었다.
"""


CORE1_CANDIDATES = [
    "kraken", "yuntal25", "storm", "c44", "bot", "guinsoo", "terminus", "nashor", "statikk",
]
CORE2_CANDIDATES = [
    "kraken", "yuntal25", "storm", "c44", "bot", "pd", "runaan", "terminus",
    "guinsoo", "nashor", "statikk", "shadowflame",
]
CORE3_CANDIDATES = [
    "ie", "ldr", "guinsoo", "terminus", "shadowflame", "nashor", "rabadon", "mortal", "void",
]
CORE4_CANDIDATES = [
    "ie", "ldr", "storm", "c44", "pd", "runaan", "kraken", "statikk", "guinsoo",
    "terminus", "nashor", "shadowflame", "rabadon", "mortal", "void",
]
# [Hypothesis] 유나라 전용 5코어 풀이 없으므로 베인 마이그레이션 관례대로 4코어 풀을 재사용한다.
CORE5_CANDIDATES = list(CORE4_CANDIDATES)
CANDIDATES_BY_SLOT = {
    1: CORE1_CANDIDATES,
    2: CORE2_CANDIDATES,
    3: CORE3_CANDIDATES,
    4: CORE4_CANDIDATES,
    5: CORE5_CANDIDATES,
}


HALF_TIER_GOLD_CAP = 1600
HALF_TIER_LEVELS = {1: 8, 2: 10, 3: 12, 4: 14, 5: 16}
# 조합식이 데이터에 없는 아이템의 대체 하위템 (루난=열정의 검 계열, 공허=지팡이 계열)
FALLBACK_RECIPES = {
    "runaan": ("열정의 검", "민첩성의 망토"),
    "rfc": ("열정의 검", "민첩성의 망토"),
    "void": ("쓸데없이 큰 지팡이", "망각의 구"),
}


def _recipe_component_names(next_key):
    """다음 코어의 조합식 하위템 이름 튜플(데이터 recipe → 없으면 FALLBACK_RECIPES → 빈 튜플)."""
    from adc_sim.data.items_data import ITEMS as _ITEMS
    recipe = _ITEMS.get(next_key, {}).get("recipe") or FALLBACK_RECIPES.get(next_key)
    return tuple(recipe) if recipe else ()


def _component_subsets(next_key, cap=HALF_TIER_GOLD_CAP):
    """조합식 슬롯별 {안 삼 | 완제 하위템 | 그 재료(builds_from) 부분집합} 택1의 곱 중 합계 ≤ cap.

    이미 든 하위템의 재료를 중복 보유하는 조합(완성 시 잉여 환불 효과)은 금지 —
    예: 윤탈 = B.F.+단검(1550G) 가능(새총 재료 단검만 선구매), 새총+단검×2 는 불가.
    사용자 지적 2026-08-31.
    """
    from itertools import combinations, product
    from adc_sim.data.items_data import ITEM_CATALOG

    def slot_options(name):
        if name not in ITEM_CATALOG:
            return [()]
        opts = [(), (name,)]
        if ITEM_CATALOG[name]["tier"] == "epic":
            mats = [b for b in ITEM_CATALOG[name].get("builds_from", ()) if b in ITEM_CATALOG]
            for r in range(1, len(mats) + 1):
                for c in combinations(mats, r):
                    opts.append(tuple(c))
        # 슬롯 내 중복 옵션 제거
        seen, uniq = set(), []
        for o in opts:
            k = tuple(sorted(o))
            if k not in seen:
                seen.add(k)
                uniq.append(o)
        return uniq

    slots = [slot_options(n) for n in _recipe_component_names(next_key)]
    subsets, seen = [()], {()}
    for pick in product(*slots) if slots else []:
        combo = tuple(n for part in pick for n in part)
        key = tuple(sorted(combo))
        if key in seen:
            continue
        cost = sum(ITEM_CATALOG[n]["cost"] for n in combo)
        if cost <= cap:
            seen.add(key)
            subsets.append(combo)
    return subsets


def _half_cache_sim(cache, done_tuple, next_key):
    """SimCache 하나에 대해 (done, next) 하프 티어 최적 하위템 구성을 메모이즈해 반환."""
    key = (tuple(sorted(done_tuple)), next_key)
    store = getattr(cache, "_half_cache", None)
    if store is None:
        store = cache._half_cache = {}
    if key in store:
        return store[key]
    best = None
    for comps in _component_subsets(next_key):
        d, g = simulate_yunara_half_tier(list(done_tuple), next_key, comps, **cache.kw)
        if best is None or d > best[0]:
            best = (d, g, comps)
    store[key] = best
    return best


def _mixed_half_sim(mixed_cache, done_tuple, next_key):
    """MixedSimCache 용 하프 티어: 부분집합을 '혼합 DPS' 기준으로 최적화."""
    key = (tuple(sorted(done_tuple)), next_key)
    store = getattr(mixed_cache, "_half_cache", None)
    if store is None:
        store = mixed_cache._half_cache = {}
    if key in store:
        return store[key]
    best = None
    for comps in _component_subsets(next_key):
        dps, gold = 0.0, 0
        for tc, w in mixed_cache.mix:
            d, g = simulate_yunara_half_tier(list(done_tuple), next_key, comps,
                                             **mixed_cache.caches[tc].kw)
            dps += w * d
            gold = g
        if best is None or dps > best[0]:
            best = (dps, gold, comps)
    store[key] = best
    return best
