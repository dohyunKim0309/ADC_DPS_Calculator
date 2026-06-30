"""케이스 기반 코어 빌드 랭킹 엔진 (Phase B).

"4코어=방어템(고정 아님)" 실전 메타를 케이스(sim_settings.build_ranking_cases)로 나눠,
비-방어 전 아이템을 전수조사해 1~5코어 파워커브를 가중 상대-DPG 로 랭킹한다.

성능 구조:
- DPS 는 '구매 순서'가 아니라 '장착 아이템 집합'에만 의존 → 집합(frozenset)+패키지
  단위로 시뮬을 메모이즈(각 고유 셋 1회만 시뮬).
- 채점 루프의 중복 제거: 한 오프닝(1~3코어)의 tier 1~3 은 그 오프닝의 모든 연계에서
  동일하므로 오프닝마다 한 번만 계산하고, 연계는 tier 4·5 집합만 덧붙여 평가한다.
- 스택 아이템(윤탈/마나무네)은 구매코어=약/다음코어=풀을 resolved-key 로 인코딩.
  슬롯 1~2 한정이라 tier 3 시점엔 항상 풀 → prefix(s3) 재사용과 양립.

현재 챔피언 설정은 Ashe 기준(레벨표/타깃/패키지). 일반화 시 파라미터화.
"""
from adc_sim.champion import Ashe
from adc_sim.runes import LethalTempo, CutDown
from adc_sim.engine import run_simulation
from adc_sim.data.items_registry import create_item_from_key
from adc_sim.data.items_data import ITEMS, ADC_PACKAGES
from adc_sim.settings import CASE_RANKING_OUTPUT
from adc_sim.simulations import sim_settings as ss
from adc_sim.simulations.ashe import CORE_ASHE_LEVELS, build_target_for_core


# ── 풀 도출 / 슬롯 제약 ─────────────────────────────────────────────────────
def dps_pool():
    return [k for k in ITEMS if k not in ss.NON_DPS_KEYS]


def allowed_at_slot(key, slot):
    allowed = ss.SLOT_RESTRICTED_ITEMS.get(key)
    return allowed is None or slot in allowed


def slot_pool(slot):
    return [k for k in dps_pool() if allowed_at_slot(k, slot)]


# ── 스택 resolve / 아이템 생성 / 집합 메모이즈 시뮬 ─────────────────────────
def resolve_key(base_key, position, tier):
    """스택 아이템을 tier 시점 상태가 인코딩된 resolved-key 로. 구매코어=weak, 이후=full."""
    if base_key not in ss.STACK_ITEMS:
        return base_key
    return f"{base_key}@{'weak' if position == tier else 'full'}"


def _make_item(resolved_key):
    if resolved_key == "yuntal25@weak":
        return create_item_from_key("yuntal25", yuntal_crit=0.10)
    if resolved_key == "yuntal25@full":
        return create_item_from_key("yuntal25", yuntal_crit=0.25)
    if resolved_key == "manamune@weak":
        item = create_item_from_key("manamune")
        item.mana_stacked = 100.0
        return item
    if resolved_key == "manamune@full":
        return create_item_from_key("muramana")
    return create_item_from_key(resolved_key)


_DPS_MEMO = {}


def core_dps(resolved_keys, package):
    """장착 아이템 집합(resolved-key frozenset)+패키지 → (dps, total_cost). tier=집합 크기."""
    memo_key = (resolved_keys, package["key"])
    cached = _DPS_MEMO.get(memo_key)
    if cached is not None:
        return cached
    tier = len(resolved_keys)
    level_cfg = CORE_ASHE_LEVELS[tier]
    ashe = Ashe(level=level_cfg["level"], q_level=level_cfg["q_level"])
    ashe.set_rune(LethalTempo())
    ashe.set_sub_rune(CutDown())
    items = [create_item_from_key(package["doran"]), create_item_from_key(package["boots"])]
    items += [_make_item(rk) for rk in resolved_keys]
    total_cost = 0
    for item in items:
        total_cost += item.cost
        ashe.add_item(item)
    # 룬: 패키지의 rune_as(민첩함 번들)는 무시하고 선택형 룬 세트(sim_settings)를 적용.
    rune = ss.selected_rune_stats()
    ashe.bonus_ad += rune["ad"]
    ashe.bonus_as_percent += rune["as"]
    ashe.ability_haste += rune["cdr"]
    _, dps, _ = run_simulation(ashe, build_target_for_core(tier), verbose=False, respawn_to_full_kills=2)
    result = (dps, total_cost)
    _DPS_MEMO[memo_key] = result
    return result


def memo_size():
    return len(_DPS_MEMO)


def _dpg(item_set, package):
    dps, cost = core_dps(item_set, package)
    return dps / (cost / 1000.0) if cost > 0 else 0.0


# ── 케이스 구조 / 제약 ──────────────────────────────────────────────────────
_PEN = set(ss.PEN_EXCLUSIVE_KEYS)
_HEAL = ss.HEAL_CUT_ITEM
_ZEAL = set(ss.ZEAL_ITEMS)


def pen_count(keys):
    return sum(1 for k in keys if k in _PEN)


def dps_positions(defensive_slot):
    """케이스의 DPS 코어 위치. def@4→[1,2,3,5], def@5→[1,2,3,4], None→[1..5]."""
    return [p for p in range(1, 6) if p != defensive_slot]


def opening_prefix_sets(open_pos, opening):
    """오프닝(1~3코어)의 tier 1·2·3 장착 집합(스택 상태 반영). 오프닝당 1회만 계산."""
    obp = {open_pos[i]: opening[i] for i in range(3)}
    return [frozenset(resolve_key(obp[p], p, t) for p in range(1, t + 1)) for t in (1, 2, 3)]


def _full_positions(opening, open_pos, cont, cont_pos, def_item, def_slot):
    """위치 4·5 의 키(연계 DPS 또는 방어템)와 전체 위치맵을 만든다."""
    dbp = {open_pos[i]: opening[i] for i in range(3)}
    for p, k in zip(cont_pos, cont):
        dbp[p] = k
    if def_slot is not None:
        dbp[def_slot] = def_item
    return dbp, dbp[4], dbp[5]


def _rel(dpgs, weights, ctrl_dpg, total_w):
    s = sum(weights[i] * (dpgs[i] / ctrl_dpg[i] if ctrl_dpg[i] > 0 else 0.0) for i in range(5))
    return s / total_w * 100.0 if total_w > 0 else 0.0


def _raw(dpgs, weights):
    return sum(weights[i] * dpgs[i] for i in range(5))


def _iter_continuations(opening, cont_pos, pools, heal_cut):
    """오프닝에 이어 붙일 연계(DPS) 키 튜플 생성(중복/펜≤1/hc→mortal 제약)."""
    used = set(opening)
    if len(cont_pos) == 1:
        for c in pools[cont_pos[0]]:
            if c in used:
                continue
            full = opening + (c,)
            if pen_count(full) > 1 or (heal_cut and _HEAL not in full):
                continue
            yield (c,)
    else:
        p4, p5 = cont_pos
        for c4 in pools[p4]:
            if c4 in used:
                continue
            for c5 in pools[p5]:
                if c5 in used or c5 == c4:
                    continue
                full = opening + (c4, c5)
                if pen_count(full) > 1 or (heal_cut and _HEAL not in full):
                    continue
                yield (c4, c5)


def _curve3(item_set, package):
    dps, cost = core_dps(item_set, package)
    return dps, (dps / (cost / 1000.0) if cost > 0 else 0.0)


def _eval_builds(opening, open_pos, cont_pos, pools, case, weights, prefix_sets, objective, ctrl_dpg=None):
    """오프닝의 모든 연계×패키지를 평가해 (목적함수 최대) 빌드를 반환.

    prefix(1~3코어) 지표를 패키지별 1회 계산해 재사용하고, 연계는 tier 4·5 집합만 덧붙인다.
    점수는 DPG 기반(objective='raw'=Σw·dpg 컨트롤용, 'rel'=컨트롤 대비 가중상대 후보용),
    표시용으로 코어별 DPS·DPG·5C총골드도 함께 보관.
    반환: best dict {value, dpgs, dpss, gold5, dps_by_pos, pkg, dps_keys} 또는 None.
    """
    s1, s2, s3 = prefix_sets
    pref = {}  # pkg_key -> (dps[3], dpg[3])
    for p in ADC_PACKAGES:
        triples = [_curve3(s, p) for s in (s1, s2, s3)]
        pref[p["key"]] = ([t[0] for t in triples], [t[1] for t in triples])
    total_w = sum(weights)
    best = None
    for cont in _iter_continuations(opening, cont_pos, pools, case["heal_cut"]):
        dbp, k4, k5 = _full_positions(opening, open_pos, cont, cont_pos,
                                      case["defensive_item"], case["defensive_slot"])
        s4 = s3 | {k4}
        s5 = s4 | {k5}
        for p in ADC_PACKAGES:
            dps4, dpg4 = _curve3(s4, p)
            dps5, cost5 = core_dps(s5, p)
            dpg5 = dps5 / (cost5 / 1000.0) if cost5 > 0 else 0.0
            dps3, dpg3 = pref[p["key"]]
            dpgs = dpg3 + [dpg4, dpg5]
            value = _raw(dpgs, weights) if objective == "raw" else _rel(dpgs, weights, ctrl_dpg, total_w)
            if best is None or value > best["value"]:
                best = {"value": value, "dpgs": dpgs, "dpss": dps3 + [dps4, dps5],
                        "gold5": cost5, "dps_by_pos": dbp, "pkg": p, "dps_keys": opening + cont}
    return best


def _compute_control(case, weights, open_pos, cont_pos, pools):
    """컨트롤 baseline: 컨트롤 오프닝 + 최적연계(raw 가중DPG)×패키지 중 최고 → 코어별 DPG."""
    opening = tuple(ss.CONTROL_OPENING)
    prefix = opening_prefix_sets(open_pos, opening)
    best = _eval_builds(opening, open_pos, cont_pos, pools, case, weights, prefix, objective="raw")
    if best is None:
        raise RuntimeError(f"케이스 {case['name']}: 컨트롤 연계를 못 만듦(제약 충돌).")
    return best["dpgs"], best


def rank_case(case, top_n, prune_k=None):
    """케이스 1개 랭킹. 반환 (ranked[:top_n], (ctrl_dpg, ctrl), stats)."""
    slot = case["defensive_slot"]
    weights = ss.get_weights(case["weight_profile"], case["n_cores"])
    dpos = dps_positions(slot)
    open_pos, cont_pos = dpos[:3], dpos[3:]
    pools = {p: slot_pool(p) for p in dpos}

    ctrl_dpg, ctrl = _compute_control(case, weights, open_pos, cont_pos, pools)

    # 오프닝 전수 (1~3코어). 제약: pen≤1, (zealreq 케이스면) zeal≥1. hc/mortal 은 연계에서 최종 판정.
    p1, p2, p3 = open_pos
    need_zeal = case["zeal_required"]
    openings = [(o1, o2, o3)
                for o1 in pools[p1]
                for o2 in pools[p2] if o2 != o1
                for o3 in pools[p3] if o3 not in (o1, o2)
                if pen_count((o1, o2, o3)) <= 1
                and (not need_zeal or any(o in _ZEAL for o in (o1, o2, o3)))]

    pruned = 0
    if prune_k is not None and len(openings) > prune_k:
        pkg0 = ADC_PACKAGES[0]

        def partial(op):
            s = opening_prefix_sets(open_pos, op)
            return sum(weights[t] * (_dpg(s[t], pkg0) / ctrl_dpg[t] if ctrl_dpg[t] > 0 else 0.0)
                       for t in range(3))
        openings.sort(key=partial, reverse=True)
        pruned = len(openings) - prune_k
        openings = openings[:prune_k]

    results = {}  # frozenset(full dps keys) -> best build
    for op in openings:
        prefix = opening_prefix_sets(open_pos, op)
        best = _eval_builds(op, open_pos, cont_pos, pools, case, weights, prefix,
                            objective="rel", ctrl_dpg=ctrl_dpg)
        if best is None:
            continue
        key = frozenset(best["dps_keys"])
        prev = results.get(key)
        if prev is None or best["value"] > prev["value"]:
            results[key] = best

    # 표시용 DPS 기반 가중 상대점수(컨트롤의 코어별 DPS 대비). 랭킹은 DPG 기준 유지.
    ctrl_dps = ctrl["dpss"]
    tw = sum(weights)
    for r in results.values():
        r["score_dps"] = _rel(r["dpss"], weights, ctrl_dps, tw)

    ranked = sorted(results.values(), key=lambda r: r["value"], reverse=True)
    stats = {"openings": len(openings), "pruned": pruned, "builds": len(results)}
    return ranked[:top_n], (ctrl_dpg, ctrl), stats


# ── 출력 ────────────────────────────────────────────────────────────────────
SHORT = {
    "kraken": "Krk", "storm": "Storm", "statikk": "Statikk", "c44": "C44", "bot": "Bot",
    "pd": "PD", "runaan": "Runaan", "terminus": "Term", "guinsoo": "Gui", "ie": "IE",
    "ldr": "LDR", "mortal": "Mortal", "bt": "BT", "nashor": "Nashor", "rabadon": "Raba",
    "shadowflame": "SF", "shieldbow": "SB", "trinity": "Trin", "essence": "ER",
    "collector": "Col", "rfc": "RFC", "manamune": "Mana", "yuntal25": "Yun",
    "maw": "Maw", "ga": "GA", "mercurial": "Merc",
}


def _short(k):
    return SHORT.get(k, k)


def build_label(dps_by_pos, def_item, def_slot, pkg):
    parts = []
    for p in range(1, 6):
        if def_slot is not None and p == def_slot:
            parts.append(f"[{_short(def_item)}]")
        else:
            parts.append(_short(dps_by_pos[p]))
    return "-".join(parts) + f" [{pkg['label']}]"


def print_case_table(case, ranked, control, stats, top_n):
    ctrl_dpg, ctrl = control
    print(f"\n{'='*150}")
    print(f"[CASE] {case['name']}  (slot={case['defensive_slot']} item={case['defensive_item']} "
          f"hc={case['heal_cut']} weight={case['weight_profile']})")
    cons = [(f"오프닝 zeal≥1개({'/'.join(ss.ZEAL_ITEMS)})" if case["zeal_required"]
             else "zeal 제약 없음"),
            f"pen-exclusive≤1({'/'.join(ss.PEN_EXCLUSIVE_KEYS)})",
            "슬롯제한[" + ", ".join(f"{k}={'·'.join(map(str, v))}코어"
                                    for k, v in ss.SLOT_RESTRICTED_ITEMS.items()) + "]"]
    if case["heal_cut"]:
        cons.append(f"치감→{ss.HEAL_CUT_ITEM} 강제")
    if case["defensive_slot"] is not None:
        cons.append(f"{case['defensive_item']}를 {case['defensive_slot']}코어 고정")
    print("  제약: " + " | ".join(cons))
    note = (f"오프닝 {stats['openings']}개 → 빌드 {stats['builds']}개  |  "
            f"좌 5열=DPS(코어1~5), 우 5열=DPG(코어1~5), GOLD=5코어 총골드 | "
            f"SCORE=컨트롤 대비 가중 상대(DPG=골드효율, DPS=절대파워), vs=±%")
    if stats["pruned"]:
        note += f"  (⚠ prune 오프닝 {stats['pruned']}개 제외)"
    print(note)
    print(f"{'':>2} | {'':<40} | {'----- DPS (core 1->5) -----':^34} | "
          f"{'----- DPG (core 1->5) -----':^34} | {'':>6} | {'DPG (rank metric)':^16} | {'DPS':^16}")
    header = (f"{'RK':>2} | {'BUILD':<40} | "
              f"{'1C':>6} {'2C':>6} {'3C':>6} {'4C':>6} {'5C':>6} | "
              f"{'1C':>6} {'2C':>6} {'3C':>6} {'4C':>6} {'5C':>6} | "
              f"{'GOLD':>6} | {'SCORE':>8} {'vs':>7} | {'SCORE':>8} {'vs':>7}")
    print(header)
    print("-" * len(header))

    def _row(tag, label, dpss, dpgs, gold5, score_dpg, score_dps):
        dps_s = " ".join(f"{dpss[i]:>6.0f}" for i in range(5))
        dpg_s = " ".join(f"{dpgs[i]:>6.1f}" for i in range(5))
        print(f"{tag:>2} | {label:<40} | {dps_s} | {dpg_s} | {gold5:>6} | "
              f"{score_dpg:>8.2f} {score_dpg-100.0:>+7.2f} | {score_dps:>8.2f} {score_dps-100.0:>+7.2f}")

    cl = build_label(ctrl["dps_by_pos"], case["defensive_item"], case["defensive_slot"], ctrl["pkg"])
    _row("C", cl + " [CTRL]", ctrl["dpss"], ctrl_dpg, ctrl["gold5"], 100.0, 100.0)
    for rank, r in enumerate(ranked[:top_n], start=1):
        lbl = build_label(r["dps_by_pos"], case["defensive_item"], case["defensive_slot"], r["pkg"])
        _row(str(rank), lbl, r["dpss"], r["dpgs"], r["gold5"], r["value"], r["score_dps"])


def run(case_filter=None):
    import time
    cfg = CASE_RANKING_OUTPUT
    top_n = cfg.get("top_n", 10)
    prune_k = cfg.get("opening_prune_top_k")
    cases = ss.build_ranking_cases()
    want = cfg.get("cases", "all")
    if isinstance(want, (list, tuple)):
        cases = [c for c in cases if c["name"] in want]
    for ex in cfg.get("exclude", []):       # 출력만 비활성화(엔진/케이스 정의는 유지)
        cases = [c for c in cases if ex not in c["name"]]
    if case_filter:
        cases = [c for c in cases if case_filter in c["name"]]

    rsel = ss.SELECTED_RUNES
    print(f"케이스 {len(cases)}개 | top_n={top_n} | prune={prune_k} | DPS풀 {len(dps_pool())}종")
    print(f"룬: 전설={rsel['legend']}/공격={rsel['offense']}/유연={rsel['flex']}/방어={rsel['defense']} "
          f"→ DPS스탯 {ss.selected_rune_stats()}")
    t_all = time.perf_counter()
    for case in cases:
        t0 = time.perf_counter()
        ranked, control, stats = rank_case(case, top_n, prune_k)
        print_case_table(case, ranked, control, stats, top_n)
        print(f"  …{time.perf_counter()-t0:.1f}s | memo {memo_size():,}")
    print(f"\n총 {time.perf_counter()-t_all:.1f}s | memo {memo_size():,}")


if __name__ == "__main__":
    import sys
    run(case_filter=sys.argv[1] if len(sys.argv) > 1 else None)
