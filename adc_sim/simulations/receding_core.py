"""공통 receding-horizon 빌드 탐색 러너 — 마지널 DPG 미래 할인합 최대화.

`vayne.py` 가 쓰는 탐색 방법론(각 코어 시점에서 "지금 사는 아이템 + 상정 미래"의
코어별 마지널 DPG 를 γ-할인해 합산하고, 그 합이 최대인 조합의 첫 아이템만 확정 →
다음 코어에서 전부 재탐색)을 챔피언 비의존 형태로 뽑아낸 것이다.

`vayne.py` 의 기존 구현(`SimCache`/`_enumerate_future_combos`/`_score_combo`/
`solve_greedy`)은 그대로 둔다(AGENTS.md 5-4 Add Before Replace). 동치성은
`tests/test_receding_core.py` 가 축소 후보 풀에서 두 구현의 궤적·점수를 비교해 검증한다.

용어
- 마지널 DPG = (해당 코어 DPS - 직전 코어 DPS) / ((해당 코어 골드 - 직전 코어 골드)/1000)
  → "이번에 추가로 쓴 골드 1000당 늘어난 DPS". 절대 DPG(=총 DPS/총 골드)와 다르다.
- 점수 = Σ_{offset} γ^offset × 마지널DPG(from_slot+offset)
"""
from adc_sim.data.items_data import pen_rule_ok


class SimCache:
    """아이템 집합 단위로 (dps, gold) 를 메모이즈한다.

    DPS 는 장착 '집합'에만 의존하므로 순서가 달라도 같은 결과다. 다만 윤탈처럼
    "구매 코어냐 다음 코어냐"로 스탯이 갈리는 아이템이 있어, 캐시 키에 해당
    아이템이 마지막(=이번에 산) 슬롯인지 여부를 함께 넣는다(vayne.SimCache 와 동일 규약).

    simulate_fn(path_list, tier, **sim_kwargs) -> (dps, total_gold)
    stack_sensitive_keys: 구매 시점에 따라 결과가 갈리는 아이템 키들.
    """

    def __init__(self, simulate_fn, sim_kwargs=None, stack_sensitive_keys=("yuntal25",)):
        self.simulate_fn = simulate_fn
        self.kw = dict(sim_kwargs or {})
        self.stack_sensitive_keys = tuple(stack_sensitive_keys)
        self.cache = {}
        self.hits = 0
        self.misses = 0

    def _key(self, items_tuple):
        """순서 무관 집합 + '구매 코어 민감' 아이템이 이번 슬롯인지 여부."""
        sorted_items = tuple(sorted(items_tuple))
        last_is_sensitive = tuple(
            key for key in self.stack_sensitive_keys
            if key in sorted_items and items_tuple[-1] == key
        )
        return sorted_items, last_is_sensitive

    def sim(self, items_tuple):
        """주어진 순서의 완성 코어들을 장착한 (DPS, 총 골드)를 반환한다."""
        key = self._key(items_tuple)
        if key in self.cache:
            self.hits += 1
            return self.cache[key]
        self.misses += 1
        result = self.simulate_fn(list(items_tuple), len(items_tuple), **self.kw)
        self.cache[key] = result
        return result

    @property
    def stats(self):
        return {"hits": self.hits, "misses": self.misses}


def enumerate_future_combos(fixed, from_slot, candidates_by_slot, horizon,
                            constraint_ok=pen_rule_ok):
    """확정 코어 뒤의 중복·제약(기본 관통 배타)을 만족하는 미래 조합을 생성한다."""
    remaining = list(range(from_slot, horizon + 1))

    def rec(idx, cur):
        """현재 슬롯부터 가능한 미래 조합을 재귀적으로 생성한다."""
        if idx == len(remaining):
            yield tuple(cur)
            return
        slot = remaining[idx]
        for item_key in candidates_by_slot[slot]:
            if item_key in cur or item_key in fixed:
                continue
            if not constraint_ok(tuple(fixed) + tuple(cur) + (item_key,)):
                continue
            cur.append(item_key)
            yield from rec(idx + 1, cur)
            cur.pop()

    yield from rec(0, [])


def score_combo(cache, fixed, combo, from_slot, dps_prev, gold_prev, gamma, horizon):
    """미래 조합의 코어별 마지널 DPG를 γ-할인해 합산한 점수와 코어별 상세를 반환한다."""
    full = list(fixed) + list(combo)
    score = 0.0
    per_tier = []
    for offset, tier in enumerate(range(from_slot, horizon + 1)):
        dps, gold = cache.sim(tuple(full[:tier]))
        delta_dps = dps - dps_prev
        delta_gold = gold - gold_prev
        marginal_dpg = delta_dps / (delta_gold / 1000.0) if delta_gold > 0 else 0.0
        per_tier.append((tier, dps, gold, marginal_dpg))
        score += (gamma ** offset) * marginal_dpg
    return score, per_tier


def solve_greedy(cache, candidates_by_slot, gamma, horizon, top_alt=3,
                 initial_fixed=(), constraint_ok=pen_rule_ok):
    """각 코어에서 미래 할인합을 다시 계산해 1~horizon 궤적과 선택 상세를 반환한다.

    반환 dict:
      trajectory: 확정된 코어 순서(list)
      steps: 슬롯별 {slot, item, score, dps, gold, marginal_dpg, future_path_winner,
                     alternatives(top_alt), baseline_dps_prev, baseline_gold_prev}
    각 슬롯의 마지널 DPG 기준선(baseline_*_prev)은 "직전 코어까지 확정된 상태"다.
    """
    fixed = list(initial_fixed)
    if fixed:
        dps_prev, gold_prev = cache.sim(tuple(fixed))
    else:
        dps_prev, gold_prev = 0.0, 0.0
    steps = []

    # 사용자가 미리 고정한 코어들은 탐색 없이 실측값만 기록한다.
    for index, item_key in enumerate(fixed, start=1):
        dps_now, gold_now = cache.sim(tuple(fixed[:index]))
        if index == 1:
            previous_dps, previous_gold = 0.0, 0.0
        else:
            previous_dps, previous_gold = cache.sim(tuple(fixed[:index - 1]))
        delta_gold = gold_now - previous_gold
        marginal_dpg = (
            (dps_now - previous_dps) / (delta_gold / 1000.0)
            if delta_gold > 0 else 0.0
        )
        steps.append({
            "slot": index, "item": item_key, "score": None,
            "dps": dps_now, "gold": gold_now, "marginal_dpg": marginal_dpg,
            "future_path_winner": tuple(fixed[index - 1:]), "alternatives": [],
            "baseline_dps_prev": previous_dps, "baseline_gold_prev": previous_gold,
            "fixed_by_user": True,
        })

    for slot in range(len(fixed) + 1, horizon + 1):
        best_score = None
        best_combo = None
        alternatives_by_item = {}
        alternative_details = {}

        for combo in enumerate_future_combos(fixed, slot, candidates_by_slot, horizon,
                                             constraint_ok=constraint_ok):
            score, per_tier = score_combo(cache, fixed, combo, slot, dps_prev, gold_prev,
                                          gamma, horizon)
            pick_item = combo[0]
            if pick_item not in alternatives_by_item or score > alternatives_by_item[pick_item]:
                alternatives_by_item[pick_item] = score
                alternative_details[pick_item] = (combo, per_tier)
            if best_score is None or score > best_score:
                best_score = score
                best_combo = combo

        if best_combo is None:  # 후보 소진(관통 배타 등) — 조기 종단
            break

        picked = best_combo[0]
        fixed.append(picked)
        dps_now, gold_now = cache.sim(tuple(fixed))
        delta_gold = gold_now - gold_prev
        marginal_dpg = (
            (dps_now - dps_prev) / (delta_gold / 1000.0) if delta_gold > 0 else 0.0
        )
        ranked_alternatives = sorted(
            alternatives_by_item.items(), key=lambda pair: pair[1], reverse=True,
        )[:top_alt]
        alternatives = [
            {"item": item_key, "score": score,
             "future_path": alternative_details[item_key][0]}
            for item_key, score in ranked_alternatives
        ]
        steps.append({
            "slot": slot, "item": picked, "score": best_score,
            "dps": dps_now, "gold": gold_now, "marginal_dpg": marginal_dpg,
            "future_path_winner": best_combo, "alternatives": alternatives,
            "baseline_dps_prev": dps_prev, "baseline_gold_prev": gold_prev,
        })
        dps_prev, gold_prev = dps_now, gold_now

    return {"trajectory": fixed[:horizon], "steps": steps}


def evaluate_fixed_path(cache, path, gamma, horizon):
    """고정 구매 순서(컨트롤 등)를 같은 척도(마지널 DPG γ-할인합)로 채점한다.

    solve_greedy 의 slot1 점수와 직접 비교 가능하도록 0코어 기준(dps_prev=gold_prev=0)
    에서 시작해 path 를 그대로 따라간다. path 가 horizon 보다 짧으면 있는 만큼만 채점한다.
    반환: (score, per_tier)
    """
    limit = min(len(path), horizon)
    score, per_tier = score_combo(cache, (), tuple(path[:limit]), 1, 0.0, 0.0,
                                  gamma, limit)
    return score, per_tier
