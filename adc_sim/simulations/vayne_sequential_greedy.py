"""베인 순차 그리디 아이템트리 선택 — 각 시점의 마지널 DPG 미래 호라이즌 할인합 최대화.

알고리즘 (사용자 확인 2026-07-20):
- 각 코어 선택 시점 t (1..5):
  · 이전 코어까지 확정된 fixed = (c1..c_{t-1}), 이전 시점 (DPS_{t-1}, Gold_{t-1}) 기준
  · 미래 호라이즌 슬롯 t..5 의 모든 조합 (c_t..c_5) 열거
  · 각 조합의 tier k=t..5 시뮬 → (DPS_k, Gold_k)
  · 마지널: ΔDPS_k = DPS_k - DPS_{t-1}, ΔGold_k = Gold_k - Gold_{t-1}
  · 마지널 DPG: ΔDPG_k = ΔDPS_k / (ΔGold_k / 1000)
  · 점수 = Σ γ^i · ΔDPG_{t+i}  (i=0..(5-t), γ=0.9, 시점 리셋)
  · 최고 점수 조합의 c_t 확정 → 다음 시점 baseline 갱신

시나리오: 4가지 (LT/PtA × 핏빛길(rune_as=0)/민첩함(rune_as=0.18))
패키지 고정: 도란활 + Gluttonous 신발. 5코어 후보 풀 = CORE4_CANDIDATES 재활용.

CLI: `-m adc_sim.simulations.vayne_sequential_greedy`  (표만 출력, 헤드리스 안전)
"""
import time
from adc_sim.runes import LethalTempo, PressTheAttack
from adc_sim.data.items_data import pen_rule_ok
from adc_sim.simulations.vayne import (
    simulate_vayne_core_path, ITEM_SHORT, CORE_VAYNE_LEVELS,
    CORE1_CANDIDATES, CORE2_CANDIDATES, CORE3_CANDIDATES, CORE4_CANDIDATES,
)

GAMMA = 0.9
HORIZON = 5

# 5코어 후보 풀 = CORE4_CANDIDATES 재활용 (사용자 확인)
CORE5_CANDIDATES = list(CORE4_CANDIDATES)
CANDIDATES_BY_SLOT = {
    1: list(CORE1_CANDIDATES), 2: list(CORE2_CANDIDATES),
    3: list(CORE3_CANDIDATES), 4: list(CORE4_CANDIDATES),
    5: CORE5_CANDIDATES,
}


class SimCache:
    """(items 셋, yun_이번슬롯) → (dps, gold) 메모. 시나리오(룬×서브룬) 별 독립.

    윤탈 스택 룰: yuntal25 가 마지막 슬롯이면 crit=10%, 이전 슬롯이면 25% —
    같은 sorted-set 이라도 yun 위치가 다르면 결과 다름. key 에 flag 포함.
    """
    def __init__(self, keystone_cls, sub_rune_cls, doran_key, boots_key, rune_as_bonus):
        self.kw = dict(doran_key=doran_key, boots_key=boots_key,
                       rune_as_bonus=rune_as_bonus, keystone_cls=keystone_cls,
                       sub_rune_cls=sub_rune_cls)
        self.cache = {}
        self.hits = 0
        self.misses = 0

    def _key(self, items_tuple):
        sorted_items = tuple(sorted(items_tuple))
        yun_last = ("yuntal25" in sorted_items) and items_tuple[-1] == "yuntal25"
        return (sorted_items, yun_last)

    def sim(self, items_tuple):
        """items_tuple = full_path[:tier] 순서 있는 리스트. tier = len(items_tuple).
        반환 (dps, gold). doran/boots 골드 포함(도란+신발+아이템들)."""
        key = self._key(items_tuple)
        if key in self.cache:
            self.hits += 1
            return self.cache[key]
        self.misses += 1
        tier = len(items_tuple)
        # simulate_vayne_core_path 는 full_path[:tier] 를 장착. 여기서는 items_tuple 자체가 이미 [:tier].
        dps, gold = simulate_vayne_core_path(list(items_tuple), tier, **self.kw)
        self.cache[key] = (dps, gold)
        return dps, gold


def _enumerate_future_combos(fixed, from_slot, horizon=HORIZON):
    """fixed = 확정된 (c1..c_{from_slot-1}). from_slot 부터 horizon 까지 남은 슬롯 조합 열거.
    각 슬롯의 CANDIDATES_BY_SLOT[s] 에서 fixed 및 이미 뽑힌 것과 중복 제거,
    pen_rule_ok 만족만 반환. 반환: yields tuple(items) 길이 = horizon - from_slot + 1.
    """
    remaining = list(range(from_slot, horizon + 1))
    def rec(idx, cur):
        if idx == len(remaining):
            yield tuple(cur)
            return
        slot = remaining[idx]
        for x in CANDIDATES_BY_SLOT[slot]:
            if x in cur or x in fixed:
                continue
            # pen 배타는 최종 5셋으로 판정하지 않고 부분 셋에도 미리 컷 가능
            if not pen_rule_ok(tuple(fixed) + tuple(cur) + (x,)):
                continue
            cur.append(x)
            yield from rec(idx + 1, cur)
            cur.pop()
    yield from rec(0, [])


def _score_combo(cache, fixed, combo, from_slot, dps_prev, gold_prev,
                 gamma=GAMMA, horizon=HORIZON):
    """조합의 마지널 DPG 할인합 점수."""
    full = list(fixed) + list(combo)
    score = 0.0
    per_tier = []  # (tier, dps, gold, ddpg) — 디버그/출력용
    for k, tier in enumerate(range(from_slot, horizon + 1)):
        dps, gold = cache.sim(tuple(full[:tier]))
        dd = dps - dps_prev
        dg = gold - gold_prev
        ddpg = (dd / (dg / 1000.0)) if dg > 0 else 0.0
        per_tier.append((tier, dps, gold, ddpg))
        score += (gamma ** k) * ddpg
    return score, per_tier


def solve_greedy(cache, gamma=GAMMA, horizon=HORIZON, top_alt=3):
    """순차 그리디 5코어 확정. 반환: {'trajectory': [c1..c5], 'steps': [...], 'baseline': [...]}
    steps[i] = {slot, item, best_score, top_alternatives, per_tier_of_winner, dps, gold, marginal_dpg}
    """
    fixed = []
    # baseline: 이전 시점 (dps, gold). 0코어 = 도란+신발 만 (첫 시뮬은 tier=1 부터).
    # 마지널 계산에서 (DPS_1, Gold_1) - (0, doran+boots_gold) 로 처리하려면
    # dps_prev, gold_prev 초기값 필요. 사용자 요구는 1코어 결정 시 뺄 게 없음 → dps_prev=0, gold_prev=0
    # 이면 1코어의 마지널 DPG = DPS_1 / (Gold_1 / 1000) = 절대 DPG (도란+신발 골드 포함).
    # 이게 사용자 의도(1코어 선택 시엔 뺄 게 없음)와 정합.
    dps_prev, gold_prev = 0.0, 0.0
    steps = []

    for slot in range(1, horizon + 1):
        best_score = None
        best_combo = None
        alt_by_item = {}  # item(=combo[0]) → best score with this item as slot pick
        alt_details = {}  # item → best combo + per_tier

        for combo in _enumerate_future_combos(fixed, slot, horizon):
            score, per_tier = _score_combo(cache, fixed, combo, slot,
                                           dps_prev, gold_prev)
            # per-item best (for top-N 대안)
            pick_item = combo[0]
            if pick_item not in alt_by_item or score > alt_by_item[pick_item]:
                alt_by_item[pick_item] = score
                alt_details[pick_item] = (combo, per_tier)
            if best_score is None or score > best_score:
                best_score = score
                best_combo = combo

        if best_combo is None:
            break

        picked = best_combo[0]
        fixed.append(picked)
        # 새 baseline: 이번 슬롯까지 시뮬한 (dps, gold)
        dps_now, gold_now = cache.sim(tuple(fixed))
        marginal_dpg_this = ((dps_now - dps_prev) / ((gold_now - gold_prev) / 1000.0)
                             if (gold_now - gold_prev) > 0 else 0.0)

        # top-N 대안 정렬 (이 슬롯에 다른 아이템 고정 시 최선 점수)
        alt_sorted = sorted(alt_by_item.items(), key=lambda kv: kv[1], reverse=True)[:top_alt]
        alt_out = []
        for item, sc in alt_sorted:
            alt_combo, alt_per_tier = alt_details[item]
            alt_out.append({"item": item, "score": sc, "future_path": alt_combo})

        steps.append({
            "slot": slot, "item": picked, "score": best_score,
            "dps": dps_now, "gold": gold_now,
            "marginal_dpg": marginal_dpg_this,
            "future_path_winner": best_combo,
            "alternatives": alt_out,
            "baseline_dps_prev": dps_prev, "baseline_gold_prev": gold_prev,
        })

        dps_prev, gold_prev = dps_now, gold_now

    return {"trajectory": fixed[:horizon], "steps": steps}


def _fmt_items(seq):
    return "-".join(ITEM_SHORT.get(k, k) for k in seq)


def print_scenario(label, out, cache_stats):
    print(f"\n{'=' * 26}  {label}  {'=' * 26}")
    print(f"γ={GAMMA}, horizon={HORIZON}. 마지널 DPG 할인합 최대화 그리디.")
    lvl_note = " · ".join(f"C{t}=lvl{CORE_VAYNE_LEVELS[t]['level']}" for t in range(1, HORIZON + 1))
    print(f"레벨: {lvl_note}")
    print(f"시뮬 캐시: {cache_stats['hits']:>7} hits / {cache_stats['misses']:>6} misses "
          f"({cache_stats['hits']/(cache_stats['hits']+cache_stats['misses'])*100:.1f}% hit)")
    print(f"\n최종 궤적: {' → '.join(ITEM_SHORT.get(k, k) for k in out['trajectory'])}")
    print()
    print(f"{'Slot':>4} | {'Pick':<12} | {'DPS':>9} | {'Gold':>6} | {'ΔDPS':>9} | "
          f"{'ΔGold':>6} | {'MarginalDPG':>11} | {'Score':>8} | 대안(top3)")
    print("-" * 130)
    for s in out["steps"]:
        d_dps = s["dps"] - s["baseline_dps_prev"]
        d_gold = s["gold"] - s["baseline_gold_prev"]
        alt_txt = " / ".join(f"{ITEM_SHORT.get(a['item'], a['item'])}:{a['score']:.1f}"
                             for a in s["alternatives"])
        print(f"{s['slot']:>4} | {ITEM_SHORT.get(s['item'], s['item']):<12} | "
              f"{s['dps']:>9.1f} | {s['gold']:>6} | {d_dps:>9.1f} | "
              f"{d_gold:>6} | {s['marginal_dpg']:>11.2f} | {s['score']:>8.2f} | {alt_txt}")
    # 승리 조합의 future 궤적 (각 슬롯 결정 시 상정한 미래 아이템들)
    print("\n[각 슬롯 결정 시 상정한 미래 조합 (winner)]")
    for s in out["steps"]:
        future = s["future_path_winner"]
        rest = future[1:] if len(future) > 1 else ()
        rest_str = "-".join(ITEM_SHORT.get(k, k) for k in rest) if rest else "(none)"
        print(f"  Slot {s['slot']} → {ITEM_SHORT.get(s['item'], s['item'])} "
              f"+ 상정 미래: {rest_str}")


def main():
    scenarios = [
        # (label, keystone, sub_rune_cls, rune_as_bonus)
        ("치명적속도 + 핏빛길 (Bow+Glut)", LethalTempo, None, 0.0),
        ("치명적속도 + 민첩함 (Bow+Glut)", LethalTempo, None, 0.18),
        ("집중공격 + 핏빛길 (Bow+Glut)", PressTheAttack, None, 0.0),
        ("집중공격 + 민첩함 (Bow+Glut)", PressTheAttack, None, 0.18),
    ]
    for label, keystone, sub, rune_as in scenarios:
        t0 = time.time()
        cache = SimCache(keystone, sub, doran_key="doranbow",
                         boots_key="glutton", rune_as_bonus=rune_as)
        out = solve_greedy(cache)
        elapsed = time.time() - t0
        print_scenario(label, out, {"hits": cache.hits, "misses": cache.misses})
        print(f"[elapsed] {elapsed:.1f}s")


if __name__ == "__main__":
    main()
