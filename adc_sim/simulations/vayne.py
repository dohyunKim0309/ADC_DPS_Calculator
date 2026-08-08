from adc_sim.champion import Vayne, Target
import matplotlib.pyplot as plt
import time
from adc_sim.runes import CoupDeGrace, LethalTempo, PressTheAttack, CutDown
from adc_sim.engine import run_simulation
from adc_sim.data.items_registry import create_item_from_key
from adc_sim.data.items_data import pen_rule_ok
from adc_sim.settings import CORE_WEIGHTS_LABEL, DEFAULT_DISCOUNT_GAMMA
from adc_sim.simulations.ashe import build_ashe_like_core_report_meta
from adc_sim.simulations.ranking_core import rank_builds

# 코어 단계별 고정 타겟 (Ashe/KaiSa/CogMaw 시뮬과 동일; 5코어는 case_ranking 관례 재사용)
CORE_TARGET_STATS = {
    1: {"hp": 1700, "armor": 50, "mr": 25},
    2: {"hp": 1900, "armor": 70, "mr": 30},
    3: {"hp": 2400, "armor": 100, "mr": 50},
    4: {"hp": 2600, "armor": 120, "mr": 70},
    5: {"hp": 3000, "armor": 150, "mr": 90},
}
CORE_VAYNE_LEVELS = {1: {"level": 9}, 2: {"level": 11}, 3: {"level": 13},
                     4: {"level": 15}, 5: {"level": 17}}

# 룬 라벨(파워컴페어/출력용) — CogMaw 미러
RUNE_LABELS = {LethalTempo: "LT", PressTheAttack: "PtA"}
RUNE_LONG_LABELS = {LethalTempo: "치명적 속도 (Lethal Tempo)",
                    PressTheAttack: "집중공격 (Press the Attack)"}


def build_target_for_core(core_tier):
    s = CORE_TARGET_STATS[core_tier]
    return Target(hp=s["hp"], armor=s["armor"], magic_resist=s["mr"],
                  bonus_hp=max(0, s["hp"] - 1500))


def _skill_levels_for_core(core_tier):
    """스킬 선마 Q→W→E, R=lvl 기반. spec §6 포인트정합표. [H-VAYNE-SKILL]
    core1(lvl9): q5/w2/e1/r1 · core2(11): q5/w3/e1/r2 · core3(13): q5/w5/e1/r2 ·
    core4(15): q5/w5/e3/r2 · core5(17): q5/w5/e4/r3.
    각 코어에서 q+w+e+r 합계는 챔피언 레벨과 같다.
    (E 는 DPS 미모델 → e_level 은 배열색인 하한 1 로 floor.)"""
    lvl = CORE_VAYNE_LEVELS[core_tier]["level"]
    q = 5
    w = {1: 2, 2: 3, 3: 5, 4: 5, 5: 5}[core_tier]
    e = {1: 1, 2: 1, 3: 1, 4: 3, 5: 4}[core_tier]
    r = 1 if lvl < 11 else (2 if lvl < 16 else 3)
    assert q + w + e + r == lvl, "Vayne core skill points must match champion level"
    return q, w, e, r


_SUB_RUNE_DEFAULT = CutDown
VAYNE_RESPAWN_TO_FULL_KILLS = 2


def simulate_vayne_core_path(full_path, core_tier, doran_key="doranblade",
                             boots_key="berserker", rune_as_bonus=0.0,
                             keystone_cls=LethalTempo,
                             sub_rune_cls=_SUB_RUNE_DEFAULT):
    """Vayne DPS + total gold for a core timing. R@t=0, Q 쿨마다(마나 바운드). K=2.

    full_path: 코어 키 리스트. core_tier: 1~5. doran/boots/rune_as: 패키지.
    keystone_cls: 키스톤 룬 클래스(LethalTempo|PressTheAttack). 기본 CutDown 보조룬.
    sub_rune_cls: 보조룬 클래스. None 이면 보조룬 없음(핏빛길·민첩함 등 amp 없는 룬 시나리오용).
    (PtA·CutDown·CoupDeGrace 의 8% 대미지증가는 `_last_damage_amp` 를 통해 은화살 고정딜에도 자동 적용.)
    반환: (dps, total_cost).
    """
    target = build_target_for_core(core_tier)
    lvl = CORE_VAYNE_LEVELS[core_tier]["level"]
    q, w, e, r = _skill_levels_for_core(core_tier)
    vayne = Vayne(
        level=lvl, q_level=q, w_level=w, e_level=e, r_level=r,
        q_first_wall_reset_only=True,
    )
    vayne.set_rune(keystone_cls())
    if sub_rune_cls is not None:
        vayne.set_sub_rune(sub_rune_cls())

    items = ([create_item_from_key(doran_key)] if doran_key else []) + [create_item_from_key(boots_key)]
    for key in full_path[:core_tier]:
        # 윤탈 스택 가정: 구매 코어=0%, 다음 코어부터 25% (사용자 확정 2026-07-20:
        # 실 인게임 윤탈 구매 직후 크리 확률 0%. 이전 10% 가정은 오류).
        if key == "yuntal25":
            idx = full_path.index(key) + 1
            yuntal_crit = 0.0 if idx == core_tier else 0.25
            items.append(create_item_from_key(key, yuntal_crit=yuntal_crit))
        else:
            items.append(create_item_from_key(key))
    total_cost = 0
    for it in items:
        total_cost += it.cost
        vayne.add_item(it)
    vayne.bonus_as_percent += rune_as_bonus

    skill_plan = {
        "manual_casts": [(0.0, "r")],          # R t=0 1회
        "auto_cast": {"q": True, "r": False},  # Q 쿨마다
        "auto_order": ["q"],
    }
    _, dps, _ = run_simulation(
        vayne, target, verbose=False, skill_plan=skill_plan,
        respawn_to_full_kills=VAYNE_RESPAWN_TO_FULL_KILLS,
    )
    return dps, total_cost


# 컨트롤(베이스라인) = 사용자 확정 실전 온힛+크리 빌드. 탐색공간에 반드시 존재해야 함.
CONTROL_PATH = ("botrk", "guinsoo", "terminus", "pd")
_VAYNE_TOP1_CACHE = {}  # (keystone_cls, rank_by) → top1 dict (룬·랭킹기준별 캐시)

# 베인 전용 온힛+크리 풀 (spec §6). pen 배타 {ldr, mortal, terminus}.
CORE1_CANDIDATES = ["botrk", "guinsoo", "kraken", "terminus", "wit", "runaan", "pd",
                    "rfc", "statikk", "yuntal25", "c44", "storm", "collector", "umbral", "essence"]
CORE2_CANDIDATES = ["botrk", "guinsoo", "kraken", "terminus", "wit", "runaan", "pd",
                    "ie", "rfc", "collector", "yuntal25", "statikk", "storm", "umbral", "essence"]
CORE3_CANDIDATES = ["ie", "ldr", "guinsoo", "terminus", "pd", "collector", "wit", "kraken", "storm", "umbral", "essence"]
CORE4_CANDIDATES = ["ie", "ldr", "pd", "runaan", "rfc", "collector", "kraken", "wit", "statikk", "terminus", "c44", "storm", "umbral", "essence"]

ITEM_SHORT = {
    "botrk": "BotRK", "guinsoo": "Gui", "kraken": "Krk", "terminus": "Terminus",
    "wit": "Wit's", "runaan": "Runaan", "pd": "PD", "ie": "IE", "ldr": "LDR",
    "rfc": "RFC", "statikk": "Statikk", "yuntal25": "Yun", "c44": "C44",
    "storm": "Storm", "collector": "Collector",
    "umbral": "Umbral",
    "essence": "ER",
}

# 기본 빌드 탐색 정책: 1~5코어 receding-horizon 마지널 DPG 할인합 최대화.
GAMMA = DEFAULT_DISCOUNT_GAMMA
HORIZON = 5
CORE5_CANDIDATES = list(CORE4_CANDIDATES)
CANDIDATES_BY_SLOT = {
    1: list(CORE1_CANDIDATES),
    2: list(CORE2_CANDIDATES),
    3: list(CORE3_CANDIDATES),
    4: list(CORE4_CANDIDATES),
    5: CORE5_CANDIDATES,
}

PTA_ALACRITY_SUB_RUNE_SCENARIOS = (
    ("집중공격 + 민첩함 + 체력차 극복 (Bow+Glut)", PressTheAttack, CutDown, 0.18),
    ("집중공격 + 민첩함 + 최후의 일격 (Bow+Glut)", PressTheAttack, CoupDeGrace, 0.18),
)


class SimCache:
    """아이템 집합과 윤탈 구매 시점을 키로 베인 DPS·골드를 메모이즈한다."""

    def __init__(self, keystone_cls, sub_rune_cls, doran_key, boots_key, rune_as_bonus):
        """룬·시작 패키지를 고정한 독립 시뮬레이션 캐시를 초기화한다."""
        self.kw = dict(
            doran_key=doran_key,
            boots_key=boots_key,
            rune_as_bonus=rune_as_bonus,
            keystone_cls=keystone_cls,
            sub_rune_cls=sub_rune_cls,
        )
        self.cache = {}
        self.hits = 0
        self.misses = 0

    def _key(self, items_tuple):
        """순서 무관 아이템 집합과 윤탈이 현재 구매 슬롯인지 여부를 캐시 키로 반환한다."""
        sorted_items = tuple(sorted(items_tuple))
        yun_last = ("yuntal25" in sorted_items) and items_tuple[-1] == "yuntal25"
        return sorted_items, yun_last

    def sim(self, items_tuple):
        """주어진 순서의 완성 코어들을 장착한 DPS와 총 골드를 반환한다."""
        key = self._key(items_tuple)
        if key in self.cache:
            self.hits += 1
            return self.cache[key]
        self.misses += 1
        tier = len(items_tuple)
        result = simulate_vayne_core_path(list(items_tuple), tier, **self.kw)
        self.cache[key] = result
        return result


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


def _fmt_items(seq):
    """내부 아이템 키 시퀀스를 출력용 약칭 문자열로 변환한다."""
    return "-".join(ITEM_SHORT.get(key, key) for key in seq)


def print_scenario(label, out, cache_stats, gamma=None):
    """한 receding-horizon 시나리오의 궤적·코어별 선택·대안을 표로 출력한다."""
    if gamma is None:
        gamma = GAMMA
    print(f"\n{'=' * 26}  {label}  {'=' * 26}")
    print(f"γ={gamma}, horizon={HORIZON}. 마지널 DPG 할인합 최대화 그리디.")
    lvl_note = " · ".join(
        f"C{tier}=lvl{CORE_VAYNE_LEVELS[tier]['level']}"
        for tier in range(1, HORIZON + 1)
    )
    print(f"레벨: {lvl_note}")
    total_cache = cache_stats["hits"] + cache_stats["misses"]
    hit_rate = cache_stats["hits"] / total_cache * 100.0 if total_cache else 0.0
    print(
        f"시뮬 캐시: {cache_stats['hits']:>7} hits / {cache_stats['misses']:>6} misses "
        f"({hit_rate:.1f}% hit)"
    )
    print(f"\n최종 궤적: {' → '.join(ITEM_SHORT.get(key, key) for key in out['trajectory'])}")
    print()
    print(
        f"{'Slot':>4} | {'Pick':<12} | {'DPS':>9} | {'Gold':>6} | {'ΔDPS':>9} | "
        f"{'ΔGold':>6} | {'MarginalDPG':>11} | {'Score':>8} | 대안(top3)"
    )
    print("-" * 130)
    for step in out["steps"]:
        delta_dps = step["dps"] - step["baseline_dps_prev"]
        delta_gold = step["gold"] - step["baseline_gold_prev"]
        alternatives = " / ".join(
            f"{ITEM_SHORT.get(alt['item'], alt['item'])}:{alt['score']:.1f}"
            for alt in step["alternatives"]
        )
        score_text = "  fixed " if step.get("fixed_by_user") else f"{step['score']:>8.2f}"
        pick_label = ITEM_SHORT.get(step["item"], step["item"])
        if step.get("fixed_by_user"):
            pick_label = f"[{pick_label}]"
        print(
            f"{step['slot']:>4} | {pick_label:<12} | {step['dps']:>9.1f} | "
            f"{step['gold']:>6} | {delta_dps:>9.1f} | {delta_gold:>6} | "
            f"{step['marginal_dpg']:>11.2f} | {score_text} | {alternatives}"
        )
    print("\n[각 슬롯 결정 시 상정한 미래 조합 (winner)]")
    for step in out["steps"]:
        future = step["future_path_winner"]
        rest = future[1:] if len(future) > 1 else ()
        rest_text = "-".join(ITEM_SHORT.get(key, key) for key in rest) if rest else "(none)"
        print(
            f"  Slot {step['slot']} → {ITEM_SHORT.get(step['item'], step['item'])} "
            f"+ 상정 미래: {rest_text}"
        )


def _run_scenarios(scenarios, gamma):
    """룬·패키지 시나리오들을 receding-horizon으로 탐색해 결과 표를 출력한다."""
    for label, keystone, sub_rune, rune_as in scenarios:
        started_at = time.time()
        cache = SimCache(
            keystone, sub_rune, doran_key="doranbow",
            boots_key="glutton", rune_as_bonus=rune_as,
        )
        out = solve_greedy(cache, gamma=gamma)
        elapsed = time.time() - started_at
        print_scenario(
            label, out, {"hits": cache.hits, "misses": cache.misses}, gamma=gamma,
        )
        print(f"[elapsed] {elapsed:.1f}s")


def main(gamma=None):
    """8개 기본 케이스를 지정 순서로 실행한다.

    순서는 치속/집공 → 핏빛길/민첩함 → 체력차 극복/최후의 일격이며,
    모든 케이스에서 도란의 활·탐식의 장화를 고정한다.
    """
    if gamma is None:
        gamma = GAMMA
    scenarios = [
        # 출력 정책: 치속 → 집공, 각 룬에서 핏빛길 → 민첩함,
        # 각 패키지에서 체력차 극복 → 최후의 일격.
        ("치명적속도 + 핏빛길 + 체력차 극복 (Bow+Glut)", LethalTempo, CutDown, 0.0),
        ("치명적속도 + 핏빛길 + 최후의 일격 (Bow+Glut)", LethalTempo, CoupDeGrace, 0.0),
        ("치명적속도 + 민첩함 + 체력차 극복 (Bow+Glut)", LethalTempo, CutDown, 0.18),
        ("치명적속도 + 민첩함 + 최후의 일격 (Bow+Glut)", LethalTempo, CoupDeGrace, 0.18),
        ("집중공격 + 핏빛길 + 체력차 극복 (Bow+Glut)", PressTheAttack, CutDown, 0.0),
        ("집중공격 + 핏빛길 + 최후의 일격 (Bow+Glut)", PressTheAttack, CoupDeGrace, 0.0),
        ("집중공격 + 민첩함 + 체력차 극복 (Bow+Glut)", PressTheAttack, CutDown, 0.18),
        ("집중공격 + 민첩함 + 최후의 일격 (Bow+Glut)", PressTheAttack, CoupDeGrace, 0.18),
    ]
    _run_scenarios(scenarios, gamma)


def main_pta_alacrity_sub_runes(gamma=None):
    """집공·민첩함 고정 후 최후의 일격과 체력차 극복 시나리오를 각각 탐색한다."""
    if gamma is None:
        gamma = GAMMA
    _run_scenarios(PTA_ALACRITY_SUB_RUNE_SCENARIOS, gamma)


def _build_all_paths():
    all_paths, seen = [], set()
    for c1 in CORE1_CANDIDATES:
        for c2 in CORE2_CANDIDATES:
            if len({c1, c2}) < 2:
                continue
            for c3 in CORE3_CANDIDATES:
                for c4 in CORE4_CANDIDATES:
                    if len({c1, c2, c3, c4}) < 4:
                        continue
                    if not pen_rule_ok((c1, c2, c3, c4)):
                        continue
                    path = (c1, c2, c3, c4)
                    if path in seen:
                        continue
                    seen.add(path)
                    all_paths.append(path)
    # 컨트롤이 풀에서 안 나오면 강제 삽입(순서 고정)
    if CONTROL_PATH not in seen:
        all_paths.append(CONTROL_PATH)
    return all_paths


def _rank_rows(all_paths, weights_raw=None, keystone_cls=LethalTempo, packages=None):
    """전 (경로×패키지) 시뮬 → dedup → 컨트롤 정규화 RelDPG. (ranking_core 위임)
    keystone_cls: 키스톤 룬 클래스. LT 가 기본(기존 골든값 보존).
    packages: None 이면 기본 ADC_PACKAGES (Bld+Zerk / Bow+Glut+민첩함) 사용."""
    def _sim(path, tier, doran_key, boots_key, rune_as_bonus):
        return simulate_vayne_core_path(path, tier, doran_key=doran_key,
                                        boots_key=boots_key, rune_as_bonus=rune_as_bonus,
                                        keystone_cls=keystone_cls)
    return rank_builds(_sim, all_paths, CONTROL_PATH, weights_raw=weights_raw,
                       packages=packages)


def get_vayne_4core_top1_build(rank_by="dpg", keystone_cls=LethalTempo):
    """랭킹된 4코어 top1 빌드 + 컨트롤 메타 반환.
    rank_by: "dpg"(RelDPG) | "dps"(절대 가중DPS). keystone_cls: LT|PtA."""
    cache_key = (keystone_cls, rank_by)
    if cache_key in _VAYNE_TOP1_CACHE:
        return _VAYNE_TOP1_CACHE[cache_key]
    rows_dedup, best_control = _rank_rows(_build_all_paths(), keystone_cls=keystone_cls)
    sort_key = (lambda r: r["weighted_dps"]) if rank_by == "dps" else (lambda r: r["rel_dpg_score"])
    ranked = sorted(rows_dedup, key=sort_key, reverse=True)
    top1 = ranked[0]
    result = {
        "path": top1["path"], "doran": top1["doran"], "boots": top1["boots"],
        "rune_as": top1["rune_as"], "pkg_label": top1["pkg_label"],
        "score": top1["rel_dpg_score"], "weighted_dpg": top1["weighted_dpg"],
        "weighted_dps": top1["weighted_dps"],
        "keystone_cls": keystone_cls,
        "control_path": best_control["path"], "control_doran": best_control["doran"],
        "control_boots": best_control["boots"], "control_rune_as": best_control["rune_as"],
        "control_pkg": best_control["pkg_label"], "control_weighted_dpg": best_control["weighted_dpg"],
    }
    _VAYNE_TOP1_CACHE[cache_key] = result
    return result


def build_vayne_core_report_meta(full_path, core_tier):
    """직렬화용 리포트 메타(Ashe-like 공용 헬퍼 재사용)."""
    return build_ashe_like_core_report_meta("Vayne", full_path, core_tier)


def get_vayne_powercompare_builds():
    """power_compare 연동용 (best, meta).
    - best: 룬 무관 최강(LT·PtA top1 중 절대 weighted-DPG 우위) — CogMaw 방식과 동일.
    - meta: 컨트롤(botrk-guinsoo-terminus-pd, 최적 패키지) under 치속(LethalTempo) — 실전 기준.
    각 dict: path/doran/boots/rune_as/pkg_label/keystone_cls/rune_label/weighted_dpg.
    (LT·PtA 두 룬 전수 랭킹을 돌리므로 느리다 — 룬별 캐시됨.)
    """
    lt = get_vayne_4core_top1_build(rank_by="dpg", keystone_cls=LethalTempo)
    pta = get_vayne_4core_top1_build(rank_by="dpg", keystone_cls=PressTheAttack)
    src = lt if lt["weighted_dpg"] >= pta["weighted_dpg"] else pta
    best = {
        "path": src["path"], "doran": src["doran"], "boots": src["boots"],
        "rune_as": src["rune_as"], "pkg_label": src["pkg_label"],
        "keystone_cls": src["keystone_cls"],
        "rune_label": RUNE_LABELS[src["keystone_cls"]],
        "weighted_dpg": src["weighted_dpg"],
    }
    meta = {  # LT 결과의 control = 컨트롤(최적 패키지) — CogMaw meta 관례와 동일
        "path": lt["control_path"], "doran": lt["control_doran"],
        "boots": lt["control_boots"], "rune_as": lt["control_rune_as"],
        "pkg_label": lt["control_pkg"],
        "keystone_cls": LethalTempo, "rune_label": RUNE_LABELS[LethalTempo],
        "weighted_dpg": lt["control_weighted_dpg"],
    }
    return best, meta


def _run_vayne_ranking(keystone_cls, keystone_label, all_paths):
    """주어진 keystone(룬)으로 랭킹 표 1장 출력. 반환: (ranked, best_control)."""
    rows_dedup, best_control = _rank_rows(all_paths, keystone_cls=keystone_cls)
    ranked = sorted(rows_dedup, key=lambda r: r["rel_dpg_score"], reverse=True)

    print(f"\n{'=' * 28}  RUNE: {keystone_label}  {'=' * 28}")
    print(f"Control: {'-'.join(best_control['path'])} [{best_control['pkg_label']}] "
          f"| Weighted DPG {best_control['weighted_dpg']:.2f}")
    col_build, col_core, col_rep = 34, 18, 9
    header = (f"{'RK':>3} | {'BUILD(4C)':<{col_build}} | {'CTRL':>6} | "
              f"{'1C DPS/ΔDPG%':>{col_core}} | {'2C DPS/ΔDPG%':>{col_core}} | "
              f"{'3C DPS/ΔDPG%':>{col_core}} | {'4C DPS/ΔDPG%':>{col_core}} | {'RelDPG':>{col_rep}}")
    print(f"\nTop 30 + Control (RelDPG = control-normalised weighted DPG ×100, {CORE_WEIGHTS_LABEL})")
    print(header); print("-" * len(header))

    def _fmt_build(r):
        p = r["path"]
        return f"{'-'.join(ITEM_SHORT.get(k, k) for k in p)} [{r['pkg_label']}]"

    top_rows = ranked[:30]
    ctrl_rows = [r for r in ranked if r["is_control"]]
    out_rows = top_rows + [r for r in ctrl_rows if r not in top_rows]
    for rank, r in enumerate(out_rows, start=1):
        y = r["y"]; d = r["core_rel_delta_pct_4"]
        tag = "[CTRL]" if r["is_control"] else ""
        label = _fmt_build(r)
        label = label if len(label) <= col_build else label[:col_build - 3] + "..."
        cells = " | ".join(f"{y[i]:.1f}/{d[i]:+.1f}%".rjust(col_core) for i in range(4))
        print(f"{rank:>3} | {label:<{col_build}} | {tag:>6} | {cells} | {r['rel_dpg_score']:>{col_rep}.2f}")

    return ranked, best_control


def main_legacy_ranking():
    """보존된 기존 1~4코어 전수 랭킹 표와 치속 기준 그래프를 실행한다."""
    print("\n=== Vayne Build Path Power Spike (W/Q auto + R@0, 1->4 Core) ===")
    all_paths = _build_all_paths()
    print(f"Total unique paths in search space: {len(all_paths)}")

    # 두 키스톤(치속·집공) 각각 랭킹 표 — CogMaw 미러. 보조룬 CutDown 은 simulate 내부 고정.
    # (PtA 8%·CutDown 8%·CoupDeGrace 8% 대미지증가는 은화살 고정딜에도 자동 적용 — _last_damage_amp 경유.)
    keystones = [(LethalTempo, RUNE_LONG_LABELS[LethalTempo]),
                 (PressTheAttack, RUNE_LONG_LABELS[PressTheAttack])]
    ranked_by_rune = []
    for _ks, _klabel in keystones:
        ranked, _ = _run_vayne_ranking(_ks, _klabel, all_paths)
        ranked_by_rune.append((ranked, _ks))

    # 그래프는 첫 룬(치속) 기준 1장 — CogMaw 관례와 동일.
    ranked, first_ks = ranked_by_rune[0]
    ctrl_rows = [r for r in ranked if r["is_control"]]

    def _fmt_build(r):
        p = r["path"]
        return f"{'-'.join(ITEM_SHORT.get(k, k) for k in p)} [{r['pkg_label']}]"

    top5 = [r for r in ranked if not r["is_control"]][:5]
    plt.figure(figsize=(12, 8))
    colors = ["#E4572E", "#F3A712", "#54A24B", "#4C78A8", "#B279A2"]
    for i, r in enumerate(top5):
        lbl = f"Top{i+1} {_fmt_build(r)} (RelDPG {r['rel_dpg_score']:.2f})"
        plt.plot(r["x"], r["y"], color=colors[i % len(colors)], linewidth=2.4, marker="D", markersize=6, label=lbl)
    for r in ctrl_rows:
        lbl = f"[CTRL] {_fmt_build(r)} (RelDPG {r['rel_dpg_score']:.2f})"
        plt.plot(r["x"], r["y"], color="#111111", linewidth=2.8, marker="o", markersize=7, linestyle="--", label=lbl)
    plt.title(f"Vayne Power Spike: 4-Core Ranked Top5 + Control ({RUNE_LABELS[first_ks]})")
    plt.xlabel("Total Gold at Core Timing"); plt.ylabel("DPS (AA + W silverbolts + Q, R@0)")
    plt.grid(True, alpha=0.3); plt.legend(loc="best", fontsize=8); plt.tight_layout()
    plt.show()


def run_cli(args=None):
    """베인 CLI를 실행한다.

    기본은 1~5코어 receding-horizon이며, `legacy-ranking`은 기존 1~4코어 전수 랭킹,
    `pta-alacrity-subs`는 집공·민첩함 보조룬 비교를 실행한다.
    """
    import sys

    cli_args = list(sys.argv[1:] if args is None else args)
    mode = "default"
    if cli_args and cli_args[0] in {"legacy-ranking", "pta-alacrity-subs"}:
        mode = cli_args.pop(0)
    if mode == "legacy-ranking":
        main_legacy_ranking()
        return

    gamma = GAMMA
    if cli_args:
        try:
            gamma = float(cli_args[0])
            if not (0.0 < gamma <= 1.0):
                raise ValueError
        except ValueError:
            print(f"[warn] gamma 인자 파싱 실패({cli_args[0]!r}) — 기본 {GAMMA} 사용")
            gamma = GAMMA
    if mode == "pta-alacrity-subs":
        main_pta_alacrity_sub_runes(gamma=gamma)
    else:
        main(gamma=gamma)


if __name__ == "__main__":
    run_cli()
