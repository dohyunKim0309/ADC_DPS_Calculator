"""폐기 예정 코드 보관소 — 베인 옛 탐색 경로 (2026-09-16).

`simulations/receding.py` 공통 엔진(하프 코어 포함, 증분 마지널 DPG)으로 교체돼
쓰이지 않는다. **어디서도 import 하지 않는다.**

- solve_greedy / _score_combo: 앵커 누적 점수식 — 각 티어의 마지널을 "직전 코어"가 아니라
  "탐색 시작 시점" 기준으로 재던 방식이라 첫 아이템 기여가 모든 항에 중복 계상됐다.
- _enumerate_future_combos: 슬롯별 후보 맵을 모듈 전역에서 읽던 버전.
  공통 엔진은 RecedingSpec 으로 주입받는다.
- solve_greedy 의 initial_fixed / first_step_horizon / second_step_horizon 은
  receding.solve 의 initial_fixed / slot_lookahead 로 일반화돼 살아 있다.
"""


def _enumerate_future_combos(fixed, from_slot, horizon=HORIZON):
    """확정 코어 뒤의 중복·관통 제약을 만족하는 미래 아이템 조합을 생성한다."""
    remaining = list(range(from_slot, horizon + 1))

    def rec(idx, cur):
        """현재 슬롯부터 가능한 미래 조합을 재귀적으로 생성한다."""
        if idx == len(remaining):
            yield tuple(cur)
            return
        slot = remaining[idx]
        for item_key in CANDIDATES_BY_SLOT[slot]:
            if item_key in cur or item_key in fixed:
                continue
            if not pen_rule_ok(tuple(fixed) + tuple(cur) + (item_key,)):
                continue
            cur.append(item_key)
            yield from rec(idx + 1, cur)
            cur.pop()

    yield from rec(0, [])


def _score_combo(cache, fixed, combo, from_slot, dps_prev, gold_prev,
                 gamma=None, horizon=HORIZON):
    """미래 조합의 코어별 마지널 DPG를 할인해 합산한 점수와 상세값을 반환한다."""
    if gamma is None:
        gamma = GAMMA
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


def solve_greedy(cache, gamma=None, horizon=HORIZON, top_alt=3, initial_fixed=(),
                 first_step_horizon=None, second_step_horizon=None):
    """각 코어에서 미래 할인합을 다시 계산해 1~5코어 궤적과 선택 상세를 반환한다.

    first_step_horizon/second_step_horizon: 각각 1·2코어 선택에만 사용할 lookahead 끝
    코어. None이면 전체 horizon을 사용한다. 이후 코어는 항상 전체 horizon까지 재탐색한다.
    """
    if gamma is None:
        gamma = GAMMA
    if first_step_horizon is None:
        first_step_horizon = horizon
    if second_step_horizon is None:
        second_step_horizon = horizon
    if not 1 <= first_step_horizon <= horizon:
        raise ValueError("first_step_horizon must be within 1..horizon")
    if not 2 <= second_step_horizon <= horizon:
        raise ValueError("second_step_horizon must be within 2..horizon")
    fixed = list(initial_fixed)
    if fixed:
        dps_prev, gold_prev = cache.sim(tuple(fixed))
    else:
        dps_prev, gold_prev = 0.0, 0.0
    steps = []

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
            "slot": index,
            "item": item_key,
            "score": None,
            "dps": dps_now,
            "gold": gold_now,
            "marginal_dpg": marginal_dpg,
            "future_path_winner": tuple(fixed[index - 1:]),
            "alternatives": [],
            "baseline_dps_prev": previous_dps,
            "baseline_gold_prev": previous_gold,
            "fixed_by_user": True,
        })

    for slot in range(len(fixed) + 1, horizon + 1):
        if slot == 1:
            lookahead_horizon = first_step_horizon
        elif slot == 2:
            lookahead_horizon = second_step_horizon
        else:
            lookahead_horizon = horizon
        best_score = None
        best_combo = None
        alternatives_by_item = {}
        alternative_details = {}

        for combo in _enumerate_future_combos(fixed, slot, lookahead_horizon):
            score, per_tier = _score_combo(
                cache, fixed, combo, slot, dps_prev, gold_prev,
                gamma=gamma, horizon=lookahead_horizon,
            )
            pick_item = combo[0]
            if pick_item not in alternatives_by_item or score > alternatives_by_item[pick_item]:
                alternatives_by_item[pick_item] = score
                alternative_details[pick_item] = (combo, per_tier)
            if best_score is None or score > best_score:
                best_score = score
                best_combo = combo

        if best_combo is None:
            break

        picked = best_combo[0]
        fixed.append(picked)
        dps_now, gold_now = cache.sim(tuple(fixed))
        delta_gold = gold_now - gold_prev
        marginal_dpg = (
            (dps_now - dps_prev) / (delta_gold / 1000.0)
            if delta_gold > 0 else 0.0
        )
        ranked_alternatives = sorted(
            alternatives_by_item.items(), key=lambda pair: pair[1], reverse=True,
        )[:top_alt]
        alternatives = []
        for item_key, score in ranked_alternatives:
            future_path, _ = alternative_details[item_key]
            alternatives.append({
                "item": item_key,
                "score": score,
                "future_path": future_path,
            })
        steps.append({
            "slot": slot,
            "item": picked,
            "score": best_score,
            "dps": dps_now,
            "gold": gold_now,
            "marginal_dpg": marginal_dpg,
            "future_path_winner": best_combo,
            "alternatives": alternatives,
            "baseline_dps_prev": dps_prev,
            "baseline_gold_prev": gold_prev,
        })
        dps_prev, gold_prev = dps_now, gold_now

    return {"trajectory": fixed[:horizon], "steps": steps}
