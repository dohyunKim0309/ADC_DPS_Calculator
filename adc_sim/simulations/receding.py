"""하프 코어 포함 receding-horizon 공통 엔진 (챔피언 무관).

2026-09-15 유나라에서 확정한 탐색 규칙을 챔피언 모듈이 복붙하지 않도록 한 곳에 모은 것.
챔피언 쪽은 **어댑터 두 가지**만 제공한다.

1. `RecedingSpec` — 슬롯별 후보, 관통 배타 규칙, 하프 후보 열거 함수, 약칭표, γ/호라이즌.
2. **캐시 객체** — `sim(items_tuple) -> (dps, gold)` 와
   `sim_half(done_tuple, next_key, comp_names) -> (dps, gold)` 두 메서드만 있으면 된다.
   (혼합 지표 캐시처럼 내부에서 여러 시뮬을 합치는 구현도 그대로 끼워진다.)

점수 규약 (유나라 §CLAUDE.md 참조):
- **증분 마지널 DPG**: 스텝마다 기준을 직전 상태로 갱신한다. 앵커(탐색 시작 시점) 누적을
  쓰면 첫 아이템 기여가 모든 항에 중복 계상돼 선택이 근시안이 된다.
- 할인 `γ^(step/2)` — 하프·완성이 각각 한 스텝이라 **풀 코어당 실효 할인은 γ**.
- 마지막 슬롯의 하프는 기본 생략(`include_last_half`). 건너뛰어도 step 은 진행시켜
  뒤따르는 완성 스텝의 할인 지수를 유지한다.
"""
from dataclasses import dataclass, field
from typing import Callable

DEFAULT_HORIZON = 5


@dataclass
class RecedingSpec:
    """챔피언별 탐색 설정. 시뮬 자체는 캐시 객체가 담당한다."""

    title: str                                  # 출력 헤더에 쓰는 챔피언 표기
    candidates_by_slot: dict                    # {슬롯: [아이템 키, ...]}
    pen_rule_ok: Callable                       # tuple(keys) -> bool
    half_options: Callable                      # 아이템 키 -> ((재료명, ...), ...)
    gamma: float
    item_short: dict = field(default_factory=dict)
    horizon: int = DEFAULT_HORIZON
    include_last_half: bool = False

    def short(self, key):
        """표시용 약칭(없으면 키 그대로)."""
        return self.item_short.get(key, key)


def half_enabled_for_slot(spec, slot, horizon=None):
    """해당 슬롯에서 하프 티어를 평가할지 — 마지막 슬롯은 기본 생략."""
    horizon = spec.horizon if horizon is None else horizon
    return slot < horizon or spec.include_last_half


def enumerate_future_combos(spec, fixed, from_slot, horizon=None):
    """확정 코어 뒤에서 중복·관통 제약을 만족하는 미래 조합을 생성한다."""
    horizon = spec.horizon if horizon is None else horizon
    remaining = list(range(from_slot, horizon + 1))

    def rec(index, current):
        """현재 슬롯 이후의 합법적인 아이템 조합을 재귀 생성한다."""
        if index == len(remaining):
            yield tuple(current)
            return
        for item_key in spec.candidates_by_slot[remaining[index]]:
            if item_key in fixed or item_key in current:
                continue
            candidate = tuple(fixed) + tuple(current) + (item_key,)
            if not spec.pen_rule_ok(candidate):
                continue
            current.append(item_key)
            yield from rec(index + 1, current)
            current.pop()

    yield from rec(0, [])


def select_half(spec, cache, done_tuple, next_key):
    """(done → next) 하프 티어 최적 구성 (dps, gold, comps) 를 메모이즈해 반환한다.

    선택 기준은 앵커(done 완성 상태) 대비 **마지널 DPG** — 점수식에 들어가는 값과 같은
    축이라야 "고른 것"과 "채점되는 것"이 어긋나지 않는다. 후보가 없으면(조합식 미보유)
    하프 없이 앵커 그대로를 돌려준다.
    """
    key = (tuple(sorted(done_tuple)), next_key)
    store = getattr(cache, "_half_cache", None)
    if store is None:
        store = cache._half_cache = {}
    if key in store:
        return store[key]

    # 1코어 하프의 앵커는 "아무 코어도 없는" 상태 — 점수식이 슬롯1에서 (0, 0) 에서
    # 출발하는 것과 같은 규약을 쓴다(시작 아이템 값은 하프 쪽 골드에 포함돼 있다).
    base_dps, base_gold = cache.sim(tuple(done_tuple)) if done_tuple else (0.0, 0.0)
    best, best_marginal = None, None
    for comp_names in spec.half_options(next_key):
        dps, gold = cache.sim_half(done_tuple, next_key, comp_names)
        delta_gold = gold - base_gold
        if delta_gold <= 0:
            continue
        marginal = (dps - base_dps) / (delta_gold / 1000.0)
        if best_marginal is None or marginal > best_marginal:
            best, best_marginal = (dps, gold, comp_names), marginal
    if best is None:
        best = (base_dps, base_gold, ())
    store[key] = best
    return best


def score_combo(spec, cache, fixed, combo, from_slot, dps_prev, gold_prev, horizon=None):
    """하프+완성 스텝을 γ^(step/2) 로 할인한 **증분** 마지널 DPG 합. [H-HALF-DISCOUNT]"""
    horizon = spec.horizon if horizon is None else horizon
    gamma = spec.gamma
    full_path = list(fixed) + list(combo)
    score, step = 0.0, 0
    d_prev, g_prev = dps_prev, gold_prev
    for tier in range(from_slot, horizon + 1):
        done = tuple(full_path[:tier - 1])
        nxt = full_path[tier - 1]
        if half_enabled_for_slot(spec, tier, horizon):
            h_dps, h_gold, _ = select_half(spec, cache, done, nxt)
            dg = h_gold - g_prev
            if dg > 0:
                score += (gamma ** (step / 2.0)) * (h_dps - d_prev) / (dg / 1000.0)
            d_prev, g_prev = max(d_prev, h_dps), max(g_prev, h_gold)
        # 하프를 건너뛰어도 step 은 진행한다 — 구간 자체는 존재하고 채점만 생략하므로
        # 뒤따르는 완성 스텝의 할인 지수가 흔들리지 않는다.
        step += 1
        f_dps, f_gold = cache.sim(tuple(full_path[:tier]))
        dg = f_gold - g_prev
        if dg > 0:
            score += (gamma ** (step / 2.0)) * (f_dps - d_prev) / (dg / 1000.0)
        d_prev, g_prev = f_dps, f_gold
        step += 1
    return score


def _marginal(dps_now, dps_prev, gold_now, gold_prev):
    """직전 완성 상태 대비 마지널 DPG(1000골드당 DPS 증가). 골드 증가가 없으면 0."""
    delta_gold = gold_now - gold_prev
    return (dps_now - dps_prev) / (delta_gold / 1000.0) if delta_gold > 0 else 0.0


def solve(spec, cache, horizon=None, top_alt=3, initial_fixed=(), slot_lookahead=None):
    """매 슬롯에서 미래(하프+완성) 할인 마지널 DPG 를 재탐색해 궤적과 상세를 반환한다.

    initial_fixed: 앞쪽 코어를 강제로 고정한 뒤 나머지만 탐색한다("1코어 X 강제" 분석용).
        고정 구간도 steps 에 실려 나오며 `fixed_by_user=True` 로 표시된다.
    slot_lookahead: {슬롯: 그 슬롯 선택에만 쓸 lookahead 끝 코어}. 지정 안 한 슬롯은
        전체 horizon 까지 본다. 초반 선택의 근시안 정도를 재는 실험용이다.
    """
    horizon = spec.horizon if horizon is None else horizon
    slot_lookahead = dict(slot_lookahead or {})
    for slot, end in slot_lookahead.items():
        if not slot <= end <= horizon:
            raise ValueError(f"slot_lookahead[{slot}]={end} must be within {slot}..{horizon}")
    fixed, steps = list(initial_fixed), []
    dps_prev, gold_prev = 0.0, 0.0

    for index, item_key in enumerate(fixed, start=1):
        dps_now, gold_now = cache.sim(tuple(fixed[:index]))
        if half_enabled_for_slot(spec, index, horizon):
            h_dps, h_gold, h_comps = select_half(spec, cache, tuple(fixed[:index - 1]), item_key)
        else:
            h_dps, h_gold, h_comps = None, None, ()
        steps.append({
            "slot": index, "item": item_key, "score": None,
            "half_dps": h_dps, "half_gold": h_gold, "half_comps": h_comps,
            "dps": dps_now, "gold": gold_now, "alternatives": [],
            "future_path_winner": tuple(fixed[index - 1:]),
            "marginal_dpg": _marginal(dps_now, dps_prev, gold_now, gold_prev),
            "baseline_dps_prev": dps_prev, "baseline_gold_prev": gold_prev,
            "fixed_by_user": True,
        })
        dps_prev, gold_prev = dps_now, gold_now

    for slot in range(len(fixed) + 1, horizon + 1):
        lookahead = slot_lookahead.get(slot, horizon)
        best_score, best_combo = None, None
        alternatives_by_item, alternatives_path = {}, {}
        for combo in enumerate_future_combos(spec, fixed, slot, lookahead):
            value = score_combo(spec, cache, fixed, combo, slot, dps_prev, gold_prev, lookahead)
            item_key = combo[0]
            if item_key not in alternatives_by_item or value > alternatives_by_item[item_key]:
                alternatives_by_item[item_key], alternatives_path[item_key] = value, combo
            if best_score is None or value > best_score:
                best_score, best_combo = value, combo
        if best_combo is None:
            break
        nxt = best_combo[0]
        if half_enabled_for_slot(spec, slot, horizon):
            h_dps, h_gold, h_comps = select_half(spec, cache, tuple(fixed), nxt)
        else:
            h_dps, h_gold, h_comps = None, None, ()
        fixed.append(nxt)
        dps_now, gold_now = cache.sim(tuple(fixed))
        ranked = sorted(alternatives_by_item.items(), key=lambda kv: kv[1], reverse=True)[:top_alt]
        steps.append({
            "slot": slot, "item": nxt, "score": best_score,
            "half_dps": h_dps, "half_gold": h_gold, "half_comps": h_comps,
            "dps": dps_now, "gold": gold_now,
            "future_path_winner": best_combo,
            "marginal_dpg": _marginal(dps_now, dps_prev, gold_now, gold_prev),
            "baseline_dps_prev": dps_prev, "baseline_gold_prev": gold_prev,
            "alternatives": [{"item": k, "score": v, "future_path": alternatives_path[k]}
                             for k, v in ranked],
        })
        dps_prev, gold_prev = dps_now, gold_now
    return {"trajectory": fixed, "steps": steps}


def print_scenario(spec, label, out):
    """한 시나리오의 궤적·슬롯별 하프/완성·대안을 표로 출력한다."""
    print(f"\n{'=' * 18}  {spec.title} · {label}  {'=' * 18}")
    print(f"γ={spec.gamma}(하프 스텝 √γ), horizon={spec.horizon} | 최종 궤적: "
          f"{' → '.join(spec.short(k) for k in out['trajectory'])}")
    for step in out["steps"]:
        alts = " / ".join(f"{spec.short(a['item'])}:{a['score']:.1f}"
                          for a in step["alternatives"])
        if step["half_dps"] is None:
            half_text = "하프[생략]".ljust(34)
        else:
            comps = "+".join(c[:6] for c in step["half_comps"]) if step["half_comps"] else "(없음)"
            half_text = f"하프[{comps}] DPS {step['half_dps']:6.1f}/G{step['half_gold']:<5.0f}"
        print(f"  {step['slot']}C {spec.short(step['item']):<9} "
              f"| {half_text} "
              f"→ 완성 DPS {step['dps']:7.1f}/G{step['gold']:<5.0f} | {alts}")
