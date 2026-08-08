from adc_sim.champion import KaiSa, Target
from dataclasses import dataclass
from functools import lru_cache

import matplotlib.pyplot as plt
from adc_sim.runes import LethalTempo, CutDown
from adc_sim.settings import CORE_WEIGHTS_RAW, CORE_WEIGHTS_LABEL, DEFAULT_DISCOUNT_GAMMA
from adc_sim.engine import run_simulation


# 코어 단계별 고정 타겟 스탯 (Ashe 시뮬레이션과 동일)
CORE_TARGET_STATS = {
    1: {"hp": 1700, "armor": 50, "mr": 25},
    2: {"hp": 1900, "armor": 70, "mr": 30},
    3: {"hp": 2400, "armor": 100, "mr": 50},
    4: {"hp": 2600, "armor": 120, "mr": 70},
    5: {"hp": 3000, "armor": 150, "mr": 90},
}

# 코어 타이밍별 레벨 (Ashe 시뮬레이션과 동일)
CORE_LEVELS = {
    1: {"level": 9},
    2: {"level": 11},
    3: {"level": 13},
    4: {"level": 15},
    5: {"level": 17},
}


def get_e_level_for_core(core_tier):
    # 요청 가정:
    # 1코어=E 2레벨, 2코어=E 3레벨, 3코어=E 4레벨, 4코어 이상=E 5레벨
    return min(5, core_tier + 1)


def build_target_for_core(core_tier):
    stats = CORE_TARGET_STATS[core_tier]
    return Target(
        hp=stats["hp"],
        armor=stats["armor"],
        magic_resist=stats["mr"],
        bonus_hp=max(0, stats["hp"] - 1500),
    )


# 아이템 키 → 인스턴스 생성은 통합 레지스트리 사용 (스탯/가격은 adc_sim/data/items_data.py)
from adc_sim.data.items_registry import create_item_from_key, get_item_ad_from_key
from adc_sim.data.items_data import (
    ADC_PACKAGES,
    DORAN_OPTIONS,
    DORAN_SHORT,
    ITEM_CATALOG,
    ITEM_CATALOG_NAMES,
    ITEMS,
    pen_rule_ok,
)


def get_yuntal_crit_for_tier(purchase_tier, current_tier):
    # 요청 규칙:
    # - 1코어 구매 시: 1코어 타이밍 10%, 이후 25%
    # - 2코어 구매 시: 2코어 타이밍 10%, 이후 25%
    if purchase_tier == 1:
        return 0.10 if current_tier == 1 else 0.25
    if purchase_tier == 2:
        return 0.10 if current_tier == 2 else 0.25
    return 0.25


def simulate_kaisa_core_path(
    full_path,
    core_tier,
    doran_key=None,
    boots_key="berserker",
    rune_as_bonus=0.0,
    bloodline_lifesteal=0.0,
    return_sustain=False,
):
    """Simulate Kai'Sa DPS, total gold, and W cast count for a core timing.

    doran_key: 시작 도란 아이템(검/활). None이면 미포함.
    boots_key: 신발(기본 광전사). rune_as_bonus: 공속 룬(민첩함 등)의 평타 공속 가산(골드 무료, E 진화 제외).
    bloodline_lifesteal: 핏빛길 생명력 흡수율. return_sustain=True면 4번째 값으로 피흡 집계를 반환한다.
    """
    target = build_target_for_core(core_tier)
    level_cfg = CORE_LEVELS[core_tier]
    e_level_for_tier = get_e_level_for_core(core_tier)

    # 요청 조건:
    # - 시뮬레이션 시작 전 E 선사용
    # - 0초에 Q/W 동시 시전 + 평타 시작, 이후 쿨마다 즉시 Q/W 사용
    kaisa = KaiSa(level=level_cfg["level"], q_level=5, w_level=5, e_level=e_level_for_tier, r_level=3)

    # 기본 룬: 치명적 속도 + 체력차 극복
    kaisa.set_rune(LethalTempo())
    kaisa.set_sub_rune(CutDown())

    current_keys = list(full_path[:core_tier])

    doran_items = [create_item_from_key(doran_key)] if doran_key else []
    items = doran_items + [create_item_from_key(boots_key)]
    for idx, key in enumerate(current_keys, start=1):
        if key == "yuntal":
            crit = get_yuntal_crit_for_tier(idx, core_tier)
            items.append(create_item_from_key(key, yuntal_crit=crit))
        else:
            items.append(create_item_from_key(key))

    total_cost = 0
    for item in items:
        total_cost += item.cost
        kaisa.add_item(item)
    kaisa.bonus_as_percent += rune_as_bonus  # 민첩함: 전투 공속에만 반영, E 진화 판정에서는 제외
    kaisa.rune_lifesteal = bloodline_lifesteal

    # 진화 조건은 카이사 기본 규칙 사용:
    # Q: 보너스 AD >= 100, W: AP >= 100
    kaisa.q_evolved_override = None
    kaisa.w_evolved_override = None

    # 스킬 시나리오를 simulation에서 정의하고 engine가 처리
    skill_plan = {
        "manual_casts": [(0.0, "e"), (0.0, "q"), (0.0, "w")],
        "auto_cast": {"q": True, "w": True, "e": True, "r": False},
        "auto_order": ["q", "w", "e", "r"],
    }

    _, dps, _ = run_simulation(kaisa, target, verbose=False, skill_plan=skill_plan, respawn_to_full_kills=2)
    sustain = dict(kaisa.sustain_metrics)
    sustain["tier"] = int(boots_key == "glutton") + int(bloodline_lifesteal > 0)
    sustain["has_lifesteal_boots"] = boots_key == "glutton"
    sustain["has_bloodline"] = bloodline_lifesteal > 0
    if return_sustain:
        return dps, total_cost, kaisa.w_cast_count, sustain
    return dps, total_cost, kaisa.w_cast_count


_EVOLUTION_RULES = {
    "q": {"stat": "ad", "threshold": 100.0},
    "w": {"stat": "ap", "threshold": 100.0},
    "e": {"stat": "as", "threshold": 1.0},
}

@dataclass(frozen=True)
class _RecipeState:
    """한 조합식 안에서 현재 보유할 수 있는 재료 묶음과 진화 관련 스탯을 보관한다."""

    cost: int = 0
    ad: float = 0.0
    ap: float = 0.0
    attack_speed: float = 0.0
    items: tuple = ()


def _merge_recipe_states(left, right):
    """서로 다른 조합식 가지의 구매 상태를 합쳐 한 인벤토리 상태로 반환한다."""
    return _RecipeState(
        cost=left.cost + right.cost,
        ad=left.ad + right.ad,
        ap=left.ap + right.ap,
        attack_speed=left.attack_speed + right.attack_speed,
        items=left.items + right.items,
    )


def _deduplicate_recipe_states(states):
    """가격·스탯·보유 재료가 같은 조합 상태를 제거해 탐색량을 제한한다."""
    unique = {}
    for state in states:
        key = (
            state.cost,
            round(state.ad, 9),
            round(state.ap, 9),
            round(state.attack_speed, 9),
            state.items,
        )
        unique[key] = state
    return tuple(sorted(unique.values(), key=lambda state: (state.cost, len(state.items), state.items)))


@lru_cache(maxsize=None)
def _catalog_recipe_branch_states(item_name):
    """기본/서사 아이템 한 가지에서 '미구매~완성'까지 가능한 실제 구매 상태를 반환한다."""
    spec = ITEM_CATALOG[item_name]
    stats = spec.get("stats", {})
    completed = _RecipeState(
        cost=int(spec["cost"]),
        ad=float(stats.get("ad", 0.0)),
        ap=float(stats.get("ap", 0.0)),
        attack_speed=float(stats.get("as", 0.0)),
        items=(item_name,),
    )
    recipe = tuple(spec.get("builds_from", ()))
    if not recipe:
        return (_RecipeState(), completed)

    states = (_RecipeState(),)
    for child_name in recipe:
        combined = []
        for left in states:
            for right in _catalog_recipe_branch_states(child_name):
                combined.append(_merge_recipe_states(left, right))
        states = _deduplicate_recipe_states(combined)
    return _deduplicate_recipe_states((*states, completed))


@lru_cache(maxsize=None)
def _core_partial_recipe_states(core_key):
    """전설 아이템을 완성하기 전 실제 하위 조합식에서 가능한 보유 상태를 반환한다."""
    recipe = tuple(ITEMS[core_key].get("recipe", ()))
    if not recipe:
        return ()

    states = (_RecipeState(),)
    for child_name in recipe:
        combined = []
        for left in states:
            for right in _catalog_recipe_branch_states(child_name):
                combined.append(_merge_recipe_states(left, right))
        states = _deduplicate_recipe_states(combined)
    return tuple(state for state in states if state.cost > 0)


def _inventory_cost_and_stats(item_keys):
    """시작 아이템·신발·완성 코어 키들의 총 가격과 Q/W/E 관련 스탯을 반환한다."""
    cost = 0
    stats = {"ad": 0.0, "ap": 0.0, "as": 0.0}
    for item_key in item_keys:
        if not item_key:
            continue
        spec = ITEMS[item_key]
        cost += int(spec["cost"])
        for stat_key in stats:
            stats[stat_key] += float(spec.get("stats", {}).get(stat_key, 0.0))
    return cost, stats


@lru_cache(maxsize=None)
def _kaisa_level_growth(level):
    """해당 레벨에서 Q와 E 진화에 포함되는 성장 AD/AS를 반환한다."""
    kaisa = KaiSa(level=level)
    return {
        "ad": kaisa.ad_growth * (level - 1),
        "as": kaisa.as_growth * (level - 1) / 100.0,
    }


def _evolution_value(skill_name, item_stats, level):
    """아이템 스탯과 레벨 성장만으로 지정 스킬의 진화 판정값을 계산한다."""
    stat_key = _EVOLUTION_RULES[skill_name]["stat"]
    value = float(item_stats[stat_key])
    if stat_key in ("ad", "as"):
        value += _kaisa_level_growth(level)[stat_key]
    return value


def _candidate_if_evolved(skill_name, item_stats, level, gold, core_tier, milestone_type, components):
    """해당 구매 시점에 진화 조건을 만족하면 비교 가능한 후보 레코드를 반환한다."""
    value = _evolution_value(skill_name, item_stats, level)
    if value + 1e-9 < _EVOLUTION_RULES[skill_name]["threshold"]:
        return None
    return {
        "gold": int(gold),
        "value": round(value, 6),
        "core_tier": core_tier,
        "milestone_type": milestone_type,
        "components": list(components),
    }


def _find_first_evolution_purchase(full_path, doran_key, boots_key, skill_name):
    """실제 4코어 조합 경로에서 진화가 처음 가능한 최소 누적 골드 시점을 찾는다."""
    path = tuple(full_path[:4])
    base_keys = tuple(key for key in (doran_key, boots_key) if key)
    base_gold, base_stats = _inventory_cost_and_stats(base_keys)
    candidates = []

    starting = _candidate_if_evolved(
        skill_name, base_stats, 1, base_gold, 0, "starting", (),
    )
    if starting:
        candidates.append(starting)

    completed_keys = []
    for purchase_tier, core_key in enumerate(path, start=1):
        previous_level = 1 if purchase_tier == 1 else CORE_LEVELS[purchase_tier - 1]["level"]
        completed_gold, completed_stats = _inventory_cost_and_stats((*base_keys, *completed_keys))

        # 사용자가 확정한 코어 타이밍 규칙: N코어 하위템은 N-1코어 레벨에서,
        # N코어 완성품은 N코어 레벨에서 판정한다. 1코어 이전만 레벨 1로 둔다.
        for state in _core_partial_recipe_states(core_key):
            partial_stats = {
                "ad": completed_stats["ad"] + state.ad,
                "ap": completed_stats["ap"] + state.ap,
                "as": completed_stats["as"] + state.attack_speed,
            }
            candidate = _candidate_if_evolved(
                skill_name,
                partial_stats,
                previous_level,
                completed_gold + state.cost,
                purchase_tier,
                "component",
                state.items,
            )
            if candidate:
                candidates.append(candidate)

        completed_keys.append(core_key)
        full_gold, full_stats = _inventory_cost_and_stats((*base_keys, *completed_keys))
        candidate = _candidate_if_evolved(
            skill_name,
            full_stats,
            CORE_LEVELS[purchase_tier]["level"],
            full_gold,
            purchase_tier,
            "core_complete",
            (ITEM_CATALOG_NAMES.get(core_key, ITEMS[core_key]["name"]),),
        )
        if candidate:
            candidates.append(candidate)

    if not candidates:
        return None
    return min(
        candidates,
        key=lambda row: (
            row["gold"], row["core_tier"],
            0 if row["milestone_type"] == "component" else 1,
            len(row["components"]), row["components"],
        ),
    )


def evaluate_kaisa_evolution_investments(
    full_path,
    core_tier,
    doran_key="doranblade",
    boots_key="berserker",
):
    """실제 빌드 경로에서 Q/W/E 진화까지 필요한 최소 누적 골드를 계산한다.

    시작 아이템·신발·완성 코어·현재 코어의 실제 하위 조합식 가격을 모두 더한다.
    경로에 없는 임의 재료는 허용하지 않으며 4코어까지 진화하지 못하면 불가능(None)이다.
    core_tier는 현재 완성 코어 상태 표시용이고, 최소 골드는 full_path의 4코어 전체를 찾는다.
    E에는 아이템과 레벨 성장 공속만 포함하며 민첩함 같은 룬 공속은 포함하지 않는다.
    """
    if core_tier not in CORE_LEVELS:
        raise ValueError(f"Unsupported core tier: {core_tier}")
    if core_tier > len(full_path):
        raise ValueError(f"Core tier {core_tier} exceeds build length {len(full_path)}")

    active_keys = tuple(key for key in (doran_key, boots_key) if key) + tuple(full_path[:core_tier])
    current_gold, current_stats = _inventory_cost_and_stats(active_keys)
    current_level = CORE_LEVELS[core_tier]["level"]

    result = {}
    for skill_name, rule in _EVOLUTION_RULES.items():
        stat_key = rule["stat"]
        threshold = rule["threshold"]
        current_value = _evolution_value(skill_name, current_stats, current_level)
        deficit = max(0.0, threshold - current_value)
        milestone = _find_first_evolution_purchase(
            full_path, doran_key, boots_key, skill_name,
        )

        result[skill_name] = {
            "evolved": deficit <= 1e-9,
            "possible": milestone is not None,
            "stat": stat_key,
            "current_value": round(current_value, 6),
            "current_gold": current_gold,
            "threshold": threshold,
            "deficit": round(deficit, 6),
            "investment_gold": milestone["gold"] if milestone is not None else None,
            "components": milestone["components"] if milestone is not None else [],
            "minimum_gold": milestone["gold"] if milestone is not None else None,
            "minimum_components": milestone["components"] if milestone is not None else [],
            "evolution_value": milestone["value"] if milestone is not None else None,
            "evolution_core_tier": milestone["core_tier"] if milestone is not None else None,
            "milestone_type": milestone["milestone_type"] if milestone is not None else None,
        }
    return result


def format_kaisa_evolution_summary(full_path, doran_key="doranblade", boots_key="berserker"):
    """4코어 빌드의 Q/W/E 최초 진화 시점·판정값·누적 골드를 한 줄로 만든다."""
    core_tier = min(4, len(full_path))
    evolutions = evaluate_kaisa_evolution_investments(
        full_path,
        core_tier,
        doran_key=doran_key,
        boots_key=boots_key,
    )
    stat_labels = {"q": "AD", "w": "AP", "e": "AS"}
    cells = []
    for skill_name in ("q", "w", "e"):
        evolution = evolutions[skill_name]
        if not evolution["possible"]:
            cells.append(f"{skill_name.upper()}: 불가")
            continue

        tier = evolution["evolution_core_tier"]
        milestone_type = evolution["milestone_type"]
        if milestone_type == "starting":
            timing = "시작 아이템"
        elif milestone_type == "core_complete":
            timing = f"{tier}C 완성"
        else:
            component_text = "+".join(evolution["components"])
            timing = f"{tier}C 재료({component_text})"

        value = evolution["evolution_value"]
        if skill_name == "e":
            value_text = f"{stat_labels[skill_name]} {value * 100.0:.1f}%"
        else:
            value_text = f"{stat_labels[skill_name]} {value:.1f}"
        cells.append(
            f"{skill_name.upper()}: {timing} · {value_text} · {evolution['investment_gold']}g"
        )
    return "EVO | " + " | ".join(cells)


def format_kaisa_sustain_summary(sustain_by_core):
    """Format sustain tier, rates, and potential healing per second for each core timing."""
    if not sustain_by_core:
        return "SUSTAIN | N/A"
    tier = sustain_by_core[0]["tier"]
    cells = []
    for core_tier, sustain in enumerate(sustain_by_core[:4], start=1):
        cells.append(
            f"{core_tier}C LS{sustain['lifesteal_rate'] * 100.0:.1f}% "
            f"OV{sustain['omnivamp_rate'] * 100.0:.1f}% "
            f"{sustain['healing_per_second']:.1f}/s"
        )
    return f"SUSTAIN T{tier} | " + " | ".join(cells)


def build_kaisa_core_report_meta(
    full_path,
    core_tier,
    w_cast_count=None,
    doran_key="doranblade",
    boots_key="berserker",
    sustain=None,
):
    """Build serializable Kai'Sa metadata including evolutions and optional sustain metrics."""
    active_path = tuple(full_path[:core_tier])
    evolutions = evaluate_kaisa_evolution_investments(
        full_path, core_tier, doran_key=doran_key, boots_key=boots_key,
    )
    report = {
        "champion": "KaiSa",
        "core_tier": core_tier,
        "full_path": list(full_path),
        "active_path": list(active_path),
        "build": "-".join(full_path),
        "active_build": "-".join(active_path),
        "w_cast_count": w_cast_count,
        "evolutions": evolutions,
        "q_evolved": evolutions["q"]["evolved"],
        "q_evolution_possible": evolutions["q"]["possible"],
        "q_evolution_gold": evolutions["q"]["investment_gold"],
        "w_evolved": evolutions["w"]["evolved"],
        "w_evolution_possible": evolutions["w"]["possible"],
        "w_evolution_gold": evolutions["w"]["investment_gold"],
        "e_evolved": evolutions["e"]["evolved"],
        "e_evolution_possible": evolutions["e"]["possible"],
        "e_evolution_gold": evolutions["e"]["investment_gold"],
    }
    if sustain is not None:
        report.update({
            "sustain_tier": sustain["tier"],
            "lifesteal_rate": sustain["lifesteal_rate"],
            "omnivamp_rate": sustain["omnivamp_rate"],
            "lifesteal_healing": sustain["lifesteal_healing"],
            "omnivamp_healing": sustain["omnivamp_healing"],
            "total_healing": sustain["total_healing"],
            "healing_per_second": sustain["healing_per_second"],
            "botrk_lifesteal_damage": sustain["botrk_lifesteal_damage"],
        })
    return report


def is_kaisa_w_evolved_at_core(full_path, core_tier=4, include_ap_400_component=False):
    """지정 코어 완성 시점의 W 진화 여부를 반환한다.

    include_ap_400_component는 기존 호출 호환용이며 임의 AP 재료 구매는 더 이상 허용하지 않는다.
    """
    evolution = evaluate_kaisa_evolution_investments(full_path, core_tier)["w"]
    return evolution["evolved"]


def _ranked_subset(ranked_rows, predicate):
    """전체 정렬을 유지하며 필터 내 상대 순위, 전체 순위, 행을 함께 반환한다."""
    matched_rows = (
        (overall_rank, row)
        for overall_rank, row in enumerate(ranked_rows, start=1)
        if predicate(row)
    )
    return [
        (relative_rank, overall_rank, row)
        for relative_rank, (overall_rank, row) in enumerate(matched_rows, start=1)
    ]


_KAISA_4CORE_TOP1_CACHE = {}  # rank_by -> top1 dict


def get_kaisa_4core_top1_build(rank_by="dpg"):
    """Return the ranked 4-core Kai'Sa top1 build with control metadata."""
    if rank_by in _KAISA_4CORE_TOP1_CACHE:
        return _KAISA_4CORE_TOP1_CACHE[rank_by]

    # simulation_kaisa 메인 연구 조건 기준(4코어 비교용)
    # core1/core2 풀 통일: (기존 core1 ∪ core2) + nashor/ie/c44 추가 → 1·2코어 동일 풀
    core1_candidates = ["kraken", "storm", "yuntal", "statikk", "guinsoo", "terminus", "pd", "bot", "nashor", "ie", "c44"]
    core2_candidates = ["kraken", "storm", "yuntal", "statikk", "guinsoo", "terminus", "pd", "bot", "nashor", "ie", "c44"]
    core3_candidates = ["nashor", "guinsoo", "terminus", "pd", "bot", "storm", "ie", "ldr", "kraken"]
    core4_candidates = ["ie", "ldr", "mortal", "terminus", "bot", "guinsoo", "storm", "nashor", "rabadon", "shadowflame", "kraken", "pd"]

    ctrl1_core4_combo = tuple(sorted(["kraken", "guinsoo", "nashor", "terminus"]))
    ctrl2_core4_combo = tuple(sorted(["kraken", "guinsoo", "pd", "ie"]))

    ad_by_key = {}
    as_by_key = {}
    for k in set(core1_candidates + core2_candidates + core3_candidates + core4_candidates):
        item_obj = create_item_from_key(k)
        ad_by_key[k] = item_obj.stats.get("ad", 0)
        as_by_key[k] = item_obj.stats.get("as", 0.0)

    all_paths = []
    seen_paths = set()
    for c1 in core1_candidates:
        for c2 in core2_candidates:
            if len({c1, c2}) < 2:
                continue
            if (ad_by_key[c1] + ad_by_key[c2]) < 75:
                continue
            if (as_by_key[c1] + as_by_key[c2]) < 0.65:
                continue
            for c3 in core3_candidates:
                for c4 in core4_candidates:
                    if len({c1, c2, c3, c4}) < 4:
                        continue
                    if not pen_rule_ok((c1, c2, c3, c4)):
                        continue
                    path = (c1, c2, c3, c4)
                    if path in seen_paths:
                        continue
                    seen_paths.add(path)
                    all_paths.append(path)

    rows = []
    for path in all_paths:
        for pkg in ADC_PACKAGES:
            kw = dict(
                doran_key=pkg["doran"],
                boots_key=pkg["boots"],
                rune_as_bonus=pkg["rune_as"],
                bloodline_lifesteal=pkg.get("bloodline_lifesteal", 0.0),
            )
            dps = []
            costs = []
            for tier in range(1, 5):
                d, c, _w = simulate_kaisa_core_path(path, tier, **kw)
                dps.append(d)
                costs.append(c)
            dpg = [dps[i] / (costs[i] / 1000.0) if costs[i] > 0 else 0.0 for i in range(4)]
            combo4 = tuple(sorted(path))
            control_label = ""
            if combo4 == ctrl1_core4_combo:
                control_label = "CTRL 1"
            elif combo4 == ctrl2_core4_combo:
                control_label = "CTRL 2"
            rows.append({
                "path": path,
                "doran": pkg["doran"],
                "boots": pkg["boots"],
                "rune_as": pkg["rune_as"],
                "bloodline_lifesteal": pkg.get("bloodline_lifesteal", 0.0),
                "pkg_label": pkg["label"],
                "x": costs,
                "y": dps,
                "dpg": dpg,
                "is_control": bool(control_label),
                "control_label": control_label,
            })

    # main script와 동일한 4코어 중복 규칙 (윤탈 위치 민감)
    dedupe_weight_raw = list(CORE_WEIGHTS_RAW)
    for r in rows:
        r["dedupe_eff"] = sum(dedupe_weight_raw[i] * r["dpg"][i] for i in range(4))

    dedupe_best_by_key = {}
    for r in rows:
        core4 = r["path"]
        if "yuntal" in core4:
            yuntal_pos = core4.index("yuntal")
            others = [k for k in core4 if k != "yuntal"]
            dedupe_key = ("yuntal_pos", yuntal_pos, tuple(sorted(others)))
        else:
            dedupe_key = ("no_yuntal", tuple(sorted(core4)))
        prev = dedupe_best_by_key.get(dedupe_key)
        if prev is None or r["dedupe_eff"] > prev["dedupe_eff"]:
            dedupe_best_by_key[dedupe_key] = r
    rows_dedup = list(dedupe_best_by_key.values())

    # 컨트롤은 dedup 재정렬(초반 DPG 최대 순서)이 아니라 사용자 정의 순서(크라켄 1코어)로 고정 (main script와 동일).
    # DPS는 장착 '집합'에만 의존하므로 재정렬은 1코어 아이템만 바꾼다 → baseline 1코어를 크라켄으로 되돌림.
    canonical_control_order = {
        "CTRL 1": ("kraken", "guinsoo", "nashor", "terminus"),
        "CTRL 2": ("kraken", "guinsoo", "pd", "ie"),
    }
    rows_dedup = [r for r in rows_dedup if not r["is_control"]]
    for _cpath in canonical_control_order.values():
        _cands = [r for r in rows if tuple(r["path"]) == _cpath]
        if _cands:
            rows_dedup.append(max(_cands, key=lambda r: sum(dedupe_weight_raw[i] * r["dpg"][i] for i in range(4))))

    # baseline control (weighted DPG 1:1:1:1 최대)
    core_weight_raw = list(CORE_WEIGHTS_RAW)
    weight_sum = sum(core_weight_raw)
    core_weights = [w / weight_sum for w in core_weight_raw]
    for r in rows_dedup:
        r["weighted_dpg"] = sum(core_weights[i] * r["dpg"][i] for i in range(4))
        r["weighted_dps"] = sum(core_weights[i] * r["y"][i] for i in range(4))

    control_rows = [r for r in rows_dedup if r["is_control"]]
    ctrl1_rows = [r for r in control_rows if r["control_label"] == "CTRL 1"]
    ctrl2_rows = [r for r in control_rows if r["control_label"] == "CTRL 2"]
    filtered_controls = []
    if ctrl1_rows:
        filtered_controls.append(max(ctrl1_rows, key=lambda r: r["weighted_dpg"]))
    if ctrl2_rows:
        filtered_controls.append(max(ctrl2_rows, key=lambda r: r["weighted_dpg"]))
    best_control = max(filtered_controls, key=lambda r: r["weighted_dpg"]) if filtered_controls else max(rows_dedup, key=lambda r: r["weighted_dpg"])
    baseline_dpg_4 = best_control["dpg"][:4]

    for r in rows_dedup:
        # Ashe/Yunara/Corki 와 동일 스케일의 점수: 컨트롤 대비 가중 DPG 비율(×100).
        # (기존 rep_score = rel_dpg_score - 100 이었으므로 정렬 순서는 동일, 표기 스케일만 통일)
        core_rel_pct = []
        for i in range(4):
            base = baseline_dpg_4[i]
            ratio_pct = ((r["dpg"][i] / base) * 100.0) if base > 0 else 0.0
            core_rel_pct.append(ratio_pct)
        r["rel_dpg_score"] = sum(core_weights[i] * core_rel_pct[i] for i in range(4))

    sort_key = (lambda r: r["weighted_dps"]) if rank_by == "dps" else (lambda r: r["rel_dpg_score"])
    ranked = sorted(rows_dedup, key=sort_key, reverse=True)
    top1 = ranked[0]
    result = {
        "path": top1["path"],
        "doran": top1["doran"],
        "boots": top1["boots"],
        "rune_as": top1["rune_as"],
        "bloodline_lifesteal": top1.get("bloodline_lifesteal", 0.0),
        "pkg_label": top1["pkg_label"],
        "score": top1["rel_dpg_score"],
        "weighted_dps": top1["weighted_dps"],
        "control_path": best_control["path"],
        "control_pkg": best_control["pkg_label"],
        "total_paths_tested": len(all_paths),
    }
    _KAISA_4CORE_TOP1_CACHE[rank_by] = result
    return result


GAMMA = DEFAULT_DISCOUNT_GAMMA
HORIZON = 5
CORE1_CANDIDATES = [
    "kraken", "storm", "yuntal", "statikk", "guinsoo", "terminus",
    "pd", "bot", "nashor", "ie", "c44",
]
CORE2_CANDIDATES = list(CORE1_CANDIDATES)
CORE3_CANDIDATES = [
    "nashor", "guinsoo", "terminus", "pd", "bot", "storm", "ie", "ldr", "kraken",
]
CORE4_CANDIDATES = [
    "ie", "ldr", "mortal", "terminus", "bot", "guinsoo",
    "storm", "nashor", "rabadon", "shadowflame", "kraken", "pd",
]
CORE5_CANDIDATES = [
    "kraken", "nashor", "guinsoo", "terminus", "shadowflame", "pd",
    "rabadon", "storm", "shieldbow", "ie", "ldr",
]
CANDIDATES_BY_SLOT = {
    1: CORE1_CANDIDATES,
    2: CORE2_CANDIDATES,
    3: CORE3_CANDIDATES,
    4: CORE4_CANDIDATES,
    5: CORE5_CANDIDATES,
}
ITEM_SHORT = {
    "kraken": "Krk",
    "storm": "Storm",
    "yuntal": "Yun",
    "statikk": "Statikk",
    "guinsoo": "Gui",
    "terminus": "Terminus",
    "pd": "PD",
    "bot": "Bot",
    "nashor": "Nashor",
    "ie": "IE",
    "c44": "C44",
    "ldr": "LDR",
    "mortal": "Mortal",
    "rabadon": "Rabadon",
    "shadowflame": "ShadowFlame",
    "shieldbow": "Shieldbow",
}


class SimCache:
    """아이템 집합과 윤탈 구매 시점을 키로 카이사 DPS·골드를 메모이즈한다."""

    def __init__(
        self,
        doran_key,
        boots_key,
        rune_as_bonus,
        bloodline_lifesteal=0.0,
    ):
        """시작 패키지를 고정한 독립 receding-horizon 시뮬레이션 캐시를 초기화한다."""
        self.kw = {
            "doran_key": doran_key,
            "boots_key": boots_key,
            "rune_as_bonus": rune_as_bonus,
            "bloodline_lifesteal": bloodline_lifesteal,
        }
        self.cache = {}
        self.hits = 0
        self.misses = 0

    def _key(self, items_tuple):
        """순서 무관 아이템 집합과 윤탈이 현재 구매 슬롯인지 여부를 캐시 키로 반환한다."""
        sorted_items = tuple(sorted(items_tuple))
        yuntal_last = bool(items_tuple) and "yuntal" in sorted_items and items_tuple[-1] == "yuntal"
        return sorted_items, yuntal_last

    def sim(self, items_tuple):
        """주어진 순서의 완성 코어들을 장착한 DPS와 총 골드를 반환한다."""
        key = self._key(items_tuple)
        if key in self.cache:
            self.hits += 1
            return self.cache[key]
        self.misses += 1
        dps, gold, _w_cast_count = simulate_kaisa_core_path(
            list(items_tuple), len(items_tuple), **self.kw,
        )
        result = dps, gold
        self.cache[key] = result
        return result


def _kaisa_two_core_stats_ok(item_keys):
    """카이사 기존 후보 필터인 2코어 AD 75·공속 65% 하한 충족 여부를 반환한다."""
    if len(item_keys) < 2:
        return True
    first_two = item_keys[:2]
    total_ad = sum(float(ITEMS[key].get("stats", {}).get("ad", 0.0)) for key in first_two)
    total_as = sum(float(ITEMS[key].get("stats", {}).get("as", 0.0)) for key in first_two)
    return total_ad >= 75.0 and total_as >= 0.65


def _enumerate_future_combos(fixed, from_slot, horizon=HORIZON):
    """확정 코어 뒤에서 중복·관통·카이사 2코어 제약을 만족하는 미래 조합을 생성한다."""
    remaining = list(range(from_slot, horizon + 1))

    def rec(index, current):
        """현재 슬롯부터 가능한 미래 조합을 재귀적으로 생성한다."""
        if index == len(remaining):
            yield tuple(current)
            return
        slot = remaining[index]
        for item_key in CANDIDATES_BY_SLOT[slot]:
            if item_key in current or item_key in fixed:
                continue
            candidate_path = tuple(fixed) + tuple(current) + (item_key,)
            if not pen_rule_ok(candidate_path):
                continue
            if not _kaisa_two_core_stats_ok(candidate_path):
                continue
            current.append(item_key)
            yield from rec(index + 1, current)
            current.pop()

    yield from rec(0, [])


def _score_combo(cache, fixed, combo, from_slot, dps_prev, gold_prev, gamma=None, horizon=HORIZON):
    """미래 조합의 코어별 마지널 DPG를 할인해 합산한 점수와 상세값을 반환한다."""
    if gamma is None:
        gamma = GAMMA
    full_path = list(fixed) + list(combo)
    score = 0.0
    per_tier = []
    for offset, tier in enumerate(range(from_slot, horizon + 1)):
        dps, gold = cache.sim(tuple(full_path[:tier]))
        delta_dps = dps - dps_prev
        delta_gold = gold - gold_prev
        marginal_dpg = delta_dps / (delta_gold / 1000.0) if delta_gold > 0 else 0.0
        per_tier.append((tier, dps, gold, marginal_dpg))
        score += (gamma ** offset) * marginal_dpg
    return score, per_tier


def solve_greedy(
    cache,
    gamma=None,
    horizon=HORIZON,
    top_alt=3,
    initial_fixed=(),
    first_step_horizon=None,
    second_step_horizon=None,
):
    """베인과 같은 슬롯별 재탐색으로 카이사 1~5코어 궤적과 선택 상세를 반환한다.

    first_step_horizon/second_step_horizon은 각각 1·2코어 선택에만 사용할 lookahead
    끝 코어다. None이면 전체 horizon을 사용하고 이후 슬롯은 전체 horizon까지 재탐색한다.
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
                cache,
                fixed,
                combo,
                slot,
                dps_prev,
                gold_prev,
                gamma=gamma,
                horizon=lookahead_horizon,
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


def print_scenario(label, out, cache_stats, doran_key, boots_key, gamma=None):
    """카이사 receding-horizon 궤적·선택 대안과 기존 Q/W/E 진화 조건을 출력한다."""
    if gamma is None:
        gamma = GAMMA
    print(f"\n{'=' * 26}  {label}  {'=' * 26}")
    print(f"γ={gamma}, horizon={HORIZON}. 마지널 DPG 할인합 최대화 그리디.")
    level_note = " · ".join(
        f"C{tier}=lvl{CORE_LEVELS[tier]['level']}"
        for tier in range(1, HORIZON + 1)
    )
    print(f"레벨: {level_note}")
    total_cache = cache_stats["hits"] + cache_stats["misses"]
    hit_rate = cache_stats["hits"] / total_cache * 100.0 if total_cache else 0.0
    print(
        f"시뮬 캐시: {cache_stats['hits']:>7} hits / {cache_stats['misses']:>6} misses "
        f"({hit_rate:.1f}% hit)"
    )
    print(f"\n최종 궤적: {' → '.join(ITEM_SHORT.get(key, key) for key in out['trajectory'])}")
    if out["trajectory"]:
        print(format_kaisa_evolution_summary(
            out["trajectory"], doran_key=doran_key, boots_key=boots_key,
        ))
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


def _run_scenarios(packages, gamma):
    """카이사 시작 패키지별 receding-horizon 탐색 결과를 진화 표시와 함께 출력한다."""
    for package in packages:
        cache = SimCache(
            doran_key=package["doran"],
            boots_key=package["boots"],
            rune_as_bonus=package["rune_as"],
            bloodline_lifesteal=package.get("bloodline_lifesteal", 0.0),
        )
        out = solve_greedy(cache, gamma=gamma)
        print_scenario(
            package["label"],
            out,
            {"hits": cache.hits, "misses": cache.misses},
            doran_key=package["doran"],
            boots_key=package["boots"],
            gamma=gamma,
        )


def main(gamma=None):
    """두 카이사 기본 ADC 패키지를 베인식 receding-horizon 선택기로 탐색한다."""
    if gamma is None:
        gamma = GAMMA
    _run_scenarios(ADC_PACKAGES, gamma)


def main_legacy_ranking():
    """교체 전 카이사 4코어 전수 랭킹과 5코어 확장 표·그래프를 실행한다."""
    print("\n=== Kai'Sa Build Path Power Spike (Q/W instant cast + Auto Attack, 1->2->3->4 Core + 5C extension) ===")

    # core1/core2 풀 통일: (기존 core1 ∪ core2) + nashor/ie/c44 추가 → 1·2코어 동일 풀
    core1_candidates = ["kraken", "storm", "yuntal", "statikk", "guinsoo", "terminus", "pd", "bot", "nashor", "ie", "c44"]
    core2_candidates = ["kraken", "storm", "yuntal", "statikk", "guinsoo", "terminus", "pd", "bot", "nashor", "ie", "c44"]
    core3_candidates = ["nashor", "guinsoo", "terminus", "pd", "bot", "storm", "ie", "ldr", "kraken"]
    core4_candidates = ["ie", "ldr", "mortal", "terminus", "bot", "guinsoo", "storm", "nashor", "rabadon", "shadowflame", "kraken", "pd"]
    core5_candidates = ["kraken", "nashor", "guinsoo", "terminus", "shadowflame", "pd", "rabadon", "storm", "shieldbow", "ie", "ldr"]

    item_short = {
        "kraken": "Krk",
        "storm": "Storm",
        "yuntal": "Yun",
        "statikk": "Statikk",
        "guinsoo": "Gui",
        "terminus": "Terminus",
        "pd": "PD",
        "bot": "Bot",
        "nashor": "Nashor",
        "ie": "IE",
        "c44": "C44",
        "ldr": "LDR",
        "mortal": "Mortal",
        "rabadon": "Rabadon",
        "shadowflame": "ShadowFlame",
        "shieldbow": "Shieldbow",
    }

    # 대조군(4코어 기준)
    # CTRL 1: Krk-Gui-Nashor-Terminus (+ ShadowFlame 5코어)
    # CTRL 2: Krk-Gui-PD-IE (+ Terminus 5코어)
    # 랭킹 baseline은 4코어 집합 기준; 5코어는 표/그래프에 top2 옵션으로 표시(핀 고정 아님)
    ctrl1_core4_combo = tuple(sorted(["kraken", "guinsoo", "nashor", "terminus"]))
    ctrl2_core4_combo = tuple(sorted(["kraken", "guinsoo", "pd", "ie"]))

    all_paths = []
    seen_paths = set()
    ad_by_key = {}
    as_by_key = {}
    for k in set(core1_candidates + core2_candidates + core3_candidates + core4_candidates + core5_candidates):
        item_obj = create_item_from_key(k)
        ad_by_key[k] = item_obj.stats.get("ad", 0)
        as_by_key[k] = item_obj.stats.get("as", 0.0)


    for c1 in core1_candidates:
        for c2 in core2_candidates:
            # 2코어 조건:
            # - AD 합 75 미만 제거
            # - 추가 공속(%) 합 65% 미만 제거
            if (ad_by_key[c1] + ad_by_key[c2]) < 75:
                continue
            if (as_by_key[c1] + as_by_key[c2]) < 0.65:
                continue
            for c3 in core3_candidates:
                for c4 in core4_candidates:
                    for c5 in core5_candidates:
                        if len({c1, c2, c3, c4, c5}) < 5:
                            continue

                        # 경계/도미닉/모탈은 동시 구매 불가
                        if not pen_rule_ok((c1, c2, c3, c4, c5)):
                            continue

                        path_tuple = (c1, c2, c3, c4, c5)
                        if path_tuple in seen_paths:
                            continue
                        seen_paths.add(path_tuple)
                        all_paths.append(path_tuple)

    results = []
    for path in all_paths:
        for pkg in ADC_PACKAGES:
            kw = dict(
                doran_key=pkg["doran"],
                boots_key=pkg["boots"],
                rune_as_bonus=pkg["rune_as"],
                bloodline_lifesteal=pkg.get("bloodline_lifesteal", 0.0),
                return_sustain=True,
            )
            dps1, cost1, w1, sustain1 = simulate_kaisa_core_path(path, 1, **kw)
            dps2, cost2, w2, sustain2 = simulate_kaisa_core_path(path, 2, **kw)
            dps3, cost3, w3, sustain3 = simulate_kaisa_core_path(path, 3, **kw)
            dps4, cost4, w4, sustain4 = simulate_kaisa_core_path(path, 4, **kw)
            dps5, cost5, w5, sustain5 = simulate_kaisa_core_path(path, 5, **kw)

            combo_key = tuple(sorted(path))
            combo_key_4 = tuple(sorted(path[:4]))
            label = (
                f"{item_short[path[0]]}-{item_short[path[1]]}-{item_short[path[2]]}-"
                f"{item_short[path[3]]}-{item_short[path[4]]} [{pkg['label']}]"
            )
            control_label = ""
            if combo_key_4 == ctrl1_core4_combo:
                control_label = "CTRL 1"
            elif combo_key_4 == ctrl2_core4_combo:
                control_label = "CTRL 2"

            results.append({
                "path": path,
                "doran": pkg["doran"],
                "boots": pkg["boots"],
                "rune_as": pkg["rune_as"],
                "bloodline_lifesteal": pkg.get("bloodline_lifesteal", 0.0),
                "pkg_label": pkg["label"],
                "combo_key": combo_key,
                "combo_key_4": combo_key_4,
                "label": label,
                "x": [cost1, cost2, cost3, cost4, cost5],
                "y": [dps1, dps2, dps3, dps4, dps5],
                "w": [w1, w2, w3, w4, w5],
                "sustain": [sustain1, sustain2, sustain3, sustain4, sustain5],
                "is_control": control_label != "",
                "control_label": control_label,
            })

    # 중복 조합 처리 규칙(4코어 평가 기준)
    # 1) 윤탈 포함 + 윤탈 위치가 다르면 서로 다른 빌드로 취급
    # 2) 1이 아니면서 조합이 같고 순서만 다르면, 1:1:1:1 효율 최고 1개만 유지
    dedupe_weight_raw = list(CORE_WEIGHTS_RAW)

    for r in results:
        dpg = []
        for i in range(5):
            cost = r["x"][i]
            dps = r["y"][i]
            dpg.append(dps / (cost / 1000.0) if cost > 0 else 0.0)
        r["dpg"] = dpg
        r["dedupe_eff"] = sum(dedupe_weight_raw[i] * dpg[i] for i in range(4))

    def dedupe_rows(rows):
        dedupe_best_by_key = {}
        for r in rows:
            path = r["path"]
            core4 = path[:4]
            if "yuntal" in core4:
                yuntal_pos = core4.index("yuntal")
                others = [k for k in core4 if k != "yuntal"]
                dedupe_key = ("yuntal_pos", yuntal_pos, tuple(sorted(others)))
            else:
                dedupe_key = ("no_yuntal", tuple(sorted(core4)))

            prev = dedupe_best_by_key.get(dedupe_key)
            if prev is None or r["dedupe_eff"] > prev["dedupe_eff"]:
                dedupe_best_by_key[dedupe_key] = r
        return list(dedupe_best_by_key.values())

    # 전체 후보를 보존해 두고, 메인 표는 기존대로 전역 중복 제거 결과를 사용
    all_results = list(results)
    results = dedupe_rows(all_results)

    # 컨트롤은 dedup 재정렬(초반 가중 DPG 최대 순서)이 아니라 사용자 정의 순서(크라켄 1코어)로 고정한다.
    # 근거: DPS는 장착 '집합'에만 의존 → 재정렬은 1코어 아이템만 바꾼다. baseline 1코어가 크라켄이어야
    #       "크라켄 선행 빌드의 1코어 상대 DPG = 0%"가 성립한다(2~4코어 집합은 순서 무관 동일).
    CANONICAL_CONTROL_ORDER = {
        "CTRL 1": ("kraken", "guinsoo", "nashor", "terminus"),
        "CTRL 2": ("kraken", "guinsoo", "pd", "ie"),
    }
    results = [r for r in results if not r["is_control"]]
    for _cpath in CANONICAL_CONTROL_ORDER.values():
        _cands = [r for r in all_results if tuple(r["path"][:4]) == _cpath]
        if _cands:
            # 같은 4코어+패키지면 1~4코어 DPG 동일(5코어 무관) → 4코어 가중 최대(=최적 패키지) 1개 선택
            results.append(max(_cands, key=lambda r: sum(dedupe_weight_raw[i] * r["dpg"][i] for i in range(4))))

    print(
        f"\nPower Spike Paths Used: {len(results)} builds "
        f"(yuntal-position-sensitive + no-yuntal best-order-by-{CORE_WEIGHTS_LABEL}, controls fixed to canonical order)"
    )

    # 랭킹 기준:
    # 대조군 중 최강 빌드의 코어별 DPS/1000g를 baseline으로 두고,
    # 각 빌드의 상대 비율(부호 있는 %)을 1:1:1:1 가중 평균한 값(%)
    core_weight_raw = list(CORE_WEIGHTS_RAW)
    weight_sum = sum(core_weight_raw)
    core_weights = [w / weight_sum for w in core_weight_raw]

    control_results = [r for r in results if r["is_control"]]

    # 컨트롤 행은 위에서 사용자 정의 순서로 고정됨 → 라벨별 1개(최적 패키지)만 baseline 후보로 남는다
    ctrl1_rows = [r for r in control_results if r["control_label"] == "CTRL 1"]
    ctrl2_rows = [r for r in control_results if r["control_label"] == "CTRL 2"]
    filtered_controls = []
    if ctrl1_rows:
        filtered_controls.append(max(ctrl1_rows, key=lambda r: sum(core_weights[i] * r["dpg"][i] for i in range(4))))
    if ctrl2_rows:
        filtered_controls.append(max(ctrl2_rows, key=lambda r: sum(core_weights[i] * r["dpg"][i] for i in range(4))))
    control_results = filtered_controls

    for r in results:
        r["weighted_dpg"] = sum(core_weights[i] * r["dpg"][i] for i in range(4))

    if control_results:
        best_control = max(control_results, key=lambda r: r["weighted_dpg"])
        baseline_mode = "control"
    else:
        # 대조군이 제거된 경우 안전 폴백
        best_control = max(results, key=lambda r: r["weighted_dpg"])
        baseline_mode = "fallback_best_build"
    baseline_dpg_4 = best_control["dpg"][:4]

    for r in all_results:
        core_rel_delta_pct = []
        for i in range(4):
            base = baseline_dpg_4[i]
            ratio_pct = ((r["dpg"][i] / base) * 100.0) if base > 0 else 0.0
            core_rel_delta_pct.append(ratio_pct - 100.0)
        r["core_rel_delta_pct_4"] = core_rel_delta_pct
        # rel_dpg_score: 컨트롤 대비 가중 DPG 비율(×100) — Ashe/Yunara/Corki 와 동일 스케일.
        # core_rel_delta_pct(코어별 +X% delta)는 표의 per-core 열에 그대로 사용.
        r["rel_dpg_score"] = sum(core_weights[i] * core_rel_delta_pct[i] for i in range(4)) + 100.0

    # 4코어 대표 빌드마다 5코어 후보 상위 2개를 구성
    rows_by_core4 = {}
    for r in all_results:
        core4 = tuple(r["path"][:4])
        rows_by_core4.setdefault(core4, []).append(r)

    baseline_ctrl_5_dps = 0.0
    baseline_ctrl_candidates = rows_by_core4.get(tuple(best_control["path"][:4]), [])
    if baseline_ctrl_candidates:
        baseline_ctrl_5_dps = max(x["y"][4] for x in baseline_ctrl_candidates)

    for r in results:
        cands = rows_by_core4.get(tuple(r["path"][:4]), [])
        # 요청 반영: 5코어는 해당 4코어 기준에서 DPS가 가장 높은 상위 2개를 선택
        cands = sorted(cands, key=lambda x: x["y"][4], reverse=True)
        top2 = []
        seen_5 = set()
        for c in cands:
            c5 = c["path"][4]
            if c5 in seen_5:
                continue
            seen_5.add(c5)
            delta5 = 0.0
            if baseline_ctrl_5_dps > 0:
                delta5 = (c["y"][4] / baseline_ctrl_5_dps) * 100.0 - 100.0
            top2.append({
                "item": c5,
                "dps": c["y"][4],
                "dpg": c["dpg"][4],
                "cost": c["x"][4],
                "delta_pct": delta5,
            })
            if len(top2) == 2:
                break
        r["top5_options"] = top2

    ranked = sorted(results, key=lambda r: r["rel_dpg_score"], reverse=True)
    ranked_main = ranked
    control_build_text = {
        "CTRL 1": "Krk-Gui-Nashor-Terminus",
        "CTRL 2": "Krk-Gui-PD-IE",
    }

    def trim_text(text, width):
        if len(text) <= width:
            return text
        return text[:max(1, width - 3)] + "..."

    def fmt_build4(r):
        p = r["path"]
        pkg_tag = f" [{r['pkg_label']}]" if r.get("pkg_label") else ""
        return f"{item_short[p[0]]}-{item_short[p[1]]}-{item_short[p[2]]}-{item_short[p[3]]}{pkg_tag}"

    def fmt_core_cell(y, d):
        return f"{y:.1f}/{d:+.1f}%"

    def print_evolution_line(row):
        """순위 행 아래 한 줄에 해당 템트리의 진화와 피흡 집계를 함께 출력한다."""
        print(
            "    ↳ "
            + format_kaisa_evolution_summary(
                row["path"], doran_key=row["doran"], boots_key=row["boots"],
            )
            + " || "
            + format_kaisa_sustain_summary(row.get("sustain", ()))
        )

    print("\n=== Control Builds ===")
    print("Control Definitions:")
    print(f"- CTRL 1: {control_build_text['CTRL 1']}")
    print(f"- CTRL 2: {control_build_text['CTRL 2']}")
    if control_results:
        for r in control_results:
            y1, y2, y3, y4 = r["y"][:4]
            c1, c2, c3, c4 = r["x"][:4]
            top5s = r.get("top5_options", [])
            if top5s:
                c5txt = " / ".join([f"{item_short[o['item']]} {o['dps']:.1f}@{o['cost']}" for o in top5s])
            else:
                c5txt = "N/A"
            cdesc = control_build_text.get(r["control_label"], "-")
            print(
                f"{r['control_label']} ({cdesc}): "
                f"1C {y1:.1f}@{c1} | 2C {y2:.1f}@{c2} | "
                f"3C {y3:.1f}@{c3} | 4C {y4:.1f}@{c4} | 5C {c5txt} | AVG4 {(y1+y2+y3+y4)/4.0:.1f}"
            )
    else:
        print("No control builds survived filters (2-core AD <= 75 removed).")

    # 기준 대조군: weighted DPS/1000g가 가장 높은 대조군
    if baseline_mode == "control":
        base_ctrl_desc = control_build_text.get(best_control["control_label"], "-")
        print(
            f"\nBaseline Control (Rel 기준): {best_control['control_label']} "
            f"({base_ctrl_desc}, {best_control['label']}) | Weighted DPG {best_control['weighted_dpg']:.2f}"
        )
    else:
        print(
            f"\nBaseline Fallback (No control survived): "
            f"{best_control['label']} | Weighted DPG {best_control['weighted_dpg']:.2f}"
        )

    top_n = min(30, len(ranked_main))
    top_rows = ranked_main[:top_n]
    top_row_keys = {tuple(r["path"]) for r in top_rows}
    extra_controls = [r for r in control_results if tuple(r["path"]) not in top_row_keys]
    output_rows = top_rows + extra_controls

    print(
        f"\nTop {len(output_rows)} Rows: Top {top_n} + All Controls "
        f"(Rel DPG Score: control 대비 코어별 DPG 비율(×100) 가중 평균, {CORE_WEIGHTS_LABEL})"
    )
    col_build = 34
    col_ctrl = 24
    col_core = 18
    col_opt = 26
    col_rep = 9
    header_main = (
        f"{'RK':>3} | {'BUILD(4C)':<{col_build}} | {'CONTROL':<{col_ctrl}} | "
        f"{'1C DPS/ΔDPG%':>{col_core}} | {'2C DPS/ΔDPG%':>{col_core}} | {'3C DPS/ΔDPG%':>{col_core}} | {'4C DPS/ΔDPG%':>{col_core}} | "
        f"{'5C OPT1 (DPS/Δ%)':>{col_opt}} | {'5C OPT2 (DPS/Δ%)':>{col_opt}} | {'RelDPG':>{col_rep}}"
    )
    header_sub = (
        f"{'RK':>3} | {'BUILD(4C)':<{col_build}} | {'CONTROL':<{col_ctrl}} | "
        f"{'1C DPS/ΔDPG%':>{col_core}} | {'2C DPS/ΔDPG%':>{col_core}} | {'3C DPS/ΔDPG%':>{col_core}} | {'4C DPS/ΔDPG%':>{col_core}} | "
        f"{'RelDPG':>{col_rep}}"
    )
    col_relative_rank = 13
    col_rank = 4
    header_ranked_sub = (
        f"{'Relative Rank':>{col_relative_rank}} | {'Rank':>{col_rank}} | "
        f"{'BUILD(4C)':<{col_build}} | {'CONTROL':<{col_ctrl}} | "
        f"{'1C DPS/ΔDPG%':>{col_core}} | {'2C DPS/ΔDPG%':>{col_core}} | "
        f"{'3C DPS/ΔDPG%':>{col_core}} | {'4C DPS/ΔDPG%':>{col_core}} | "
        f"{'RelDPG':>{col_rep}}"
    )
    print(header_main)
    print("-" * len(header_main))

    for rank, r in enumerate(output_rows, start=1):
        y1, y2, y3, y4 = r["y"][:4]
        d1, d2, d3, d4 = r["core_rel_delta_pct_4"]
        label = trim_text(fmt_build4(r), col_build)
        ctrl_txt = trim_text(control_build_text.get(r["control_label"], "-"), col_ctrl)
        c1v = fmt_core_cell(y1, d1)
        c2v = fmt_core_cell(y2, d2)
        c3v = fmt_core_cell(y3, d3)
        c4v = fmt_core_cell(y4, d4)
        top5 = r.get("top5_options", [])
        c5a = "N/A"
        c5b = "N/A"
        if len(top5) >= 1:
            c5a = f"{item_short[top5[0]['item']]} {top5[0]['dps']:.1f}/{top5[0]['delta_pct']:+.1f}%"
        if len(top5) >= 2:
            c5b = f"{item_short[top5[1]['item']]} {top5[1]['dps']:.1f}/{top5[1]['delta_pct']:+.1f}%"
        print(
            f"{rank:>3} | {label:<{col_build}} | {ctrl_txt:<{col_ctrl}} | "
            f"{c1v:>{col_core}} | {c2v:>{col_core}} | {c3v:>{col_core}} | {c4v:>{col_core}} | "
            f"{trim_text(c5a, col_opt):>{col_opt}} | {trim_text(c5b, col_opt):>{col_opt}} | "
            f"{r['rel_dpg_score']:>{col_rep}.2f}"
        )
        print_evolution_line(r)

    # 요청 빌드 확인: Yun-Gui-IE-LDR에서 5코어 Nashor도 별도 출력(상위 2옵션 여부와 무관)
    requested_core4 = ("yuntal", "guinsoo", "ie", "ldr")
    requested_nashor_row = next(
        (r for r in all_results if tuple(r["path"][:5]) == requested_core4 + ("nashor",)),
        None
    )
    requested_core4_row = next(
        (r for r in results if tuple(r["path"][:4]) == requested_core4),
        None
    )
    if requested_nashor_row is not None:
        y1, y2, y3, y4, y5 = requested_nashor_row["y"]
        d1, d2, d3, d4 = requested_nashor_row["core_rel_delta_pct_4"]
        dpg5 = requested_nashor_row["dpg"][4]
        c5 = requested_nashor_row["x"][4]
        delta5 = 0.0
        if baseline_ctrl_5_dps > 0:
            delta5 = (y5 / baseline_ctrl_5_dps) * 100.0 - 100.0

        in_top2 = False
        if requested_core4_row is not None:
            in_top2 = any(o["item"] == "nashor" for o in requested_core4_row.get("top5_options", []))

        print("\nRequested 5C Check: Yun-Gui-IE-LDR + Nashor")
        print(
            f"4C Row Present: {'Yes' if requested_core4_row is not None else 'No'} | "
            f"Nashor in displayed Top2 options: {'Yes' if in_top2 else 'No'}"
        )
        print(
            f"1C {y1:.1f}/{d1:+.1f}% | 2C {y2:.1f}/{d2:+.1f}% | "
            f"3C {y3:.1f}/{d3:+.1f}% | 4C {y4:.1f}/{d4:+.1f}% | "
            f"5C Nashor {y5:.1f}@{c5} (DPG {dpg5:.2f}, ΔvsCtrl5 {delta5:+.1f}%) | "
            f"RelDPG {requested_nashor_row['rel_dpg_score']:.2f}"
        )

    # 별도 표: 임의 400g AP 재료 추가 없이 4코어 완성 시 W가 진화한 빌드.
    w_evo_ranked_rows = _ranked_subset(
        ranked,
        lambda row: is_kaisa_w_evolved_at_core(
            row["path"], 4, include_ap_400_component=True,
        ),
    )
    if w_evo_ranked_rows:
        w_top_n = min(30, len(w_evo_ranked_rows))
        print(
            f"\nW-Evolved at 4-Core Ranking (Top {w_top_n}, AP>=100 at completed 4C, same RelDPG metric)"
        )
        print(header_ranked_sub)
        print("-" * len(header_ranked_sub))
        for relative_rank, overall_rank, r in w_evo_ranked_rows[:w_top_n]:
            y1, y2, y3, y4 = r["y"][:4]
            d1, d2, d3, d4 = r["core_rel_delta_pct_4"]
            label = trim_text(fmt_build4(r), col_build)
            ctrl_txt = trim_text(control_build_text.get(r["control_label"], "-"), col_ctrl)
            c1v = fmt_core_cell(y1, d1)
            c2v = fmt_core_cell(y2, d2)
            c3v = fmt_core_cell(y3, d3)
            c4v = fmt_core_cell(y4, d4)
            print(
                f"{relative_rank:>{col_relative_rank}} | {overall_rank:>{col_rank}} | "
                f"{label:<{col_build}} | {ctrl_txt:<{col_ctrl}} | "
                f"{c1v:>{col_core}} | {c2v:>{col_core}} | {c3v:>{col_core}} | {c4v:>{col_core}} | "
                f"{r['rel_dpg_score']:>{col_rep}.2f}"
            )
            print_evolution_line(r)

    # 별도 표: 1코어 크라켄 고정 랭킹 (그래프 없음)
    kraken_rows = [r for r in ranked if r["path"][0] == "kraken"]
    if kraken_rows:
        kraken_top_n = min(30, len(kraken_rows))
        print(
            f"\nKraken-First Ranking (Top {kraken_top_n}, no graph, same RelDPG metric)"
        )
        print(header_sub)
        print("-" * len(header_sub))
        for rank, r in enumerate(kraken_rows[:kraken_top_n], start=1):
            y1, y2, y3, y4 = r["y"][:4]
            d1, d2, d3, d4 = r["core_rel_delta_pct_4"]
            label = trim_text(fmt_build4(r), col_build)
            ctrl_txt = trim_text(control_build_text.get(r["control_label"], "-"), col_ctrl)
            c1v = fmt_core_cell(y1, d1)
            c2v = fmt_core_cell(y2, d2)
            c3v = fmt_core_cell(y3, d3)
            c4v = fmt_core_cell(y4, d4)
            print(
                f"{rank:>3} | {label:<{col_build}} | {ctrl_txt:<{col_ctrl}} | "
                f"{c1v:>{col_core}} | {c2v:>{col_core}} | {c3v:>{col_core}} | {c4v:>{col_core}} | "
                f"{r['rel_dpg_score']:>{col_rep}.2f}"
            )
            print_evolution_line(r)

    # 별도 표: 전체 랭킹 중 유령무희가 2·3·4코어에 포함된 빌드
    pd_234_ranked_rows = _ranked_subset(
        ranked,
        lambda row: "pd" in row["path"][1:4],
    )
    if pd_234_ranked_rows:
        pd_top_n = min(30, len(pd_234_ranked_rows))
        print(
            f"\nPD in Core2/Core3/Core4 Ranking (Top {pd_top_n}, no graph, same RelDPG metric)"
        )
        print(header_ranked_sub)
        print("-" * len(header_ranked_sub))
        for relative_rank, overall_rank, r in pd_234_ranked_rows[:pd_top_n]:
            y1, y2, y3, y4 = r["y"][:4]
            d1, d2, d3, d4 = r["core_rel_delta_pct_4"]
            label = trim_text(fmt_build4(r), col_build)
            ctrl_txt = trim_text(control_build_text.get(r["control_label"], "-"), col_ctrl)
            c1v = fmt_core_cell(y1, d1)
            c2v = fmt_core_cell(y2, d2)
            c3v = fmt_core_cell(y3, d3)
            c4v = fmt_core_cell(y4, d4)
            print(
                f"{relative_rank:>{col_relative_rank}} | {overall_rank:>{col_rank}} | "
                f"{label:<{col_build}} | {ctrl_txt:<{col_ctrl}} | "
                f"{c1v:>{col_core}} | {c2v:>{col_core}} | {c3v:>{col_core}} | {c4v:>{col_core}} | "
                f"{r['rel_dpg_score']:>{col_rep}.2f}"
            )
            print_evolution_line(r)

    # 그래프: 4코어 기준 상위 5개 + 대조군 2개, 각 빌드의 5코어 상위 2옵션 분기
    top5_non_control = [r for r in ranked if not r["is_control"]][:5]

    control_best_by_label = {}
    for r in control_results:
        key = r["control_label"]
        if key not in control_best_by_label or r["rel_dpg_score"] > control_best_by_label[key]["rel_dpg_score"]:
            control_best_by_label[key] = r
    graph_controls = list(control_best_by_label.values())

    plt.figure(figsize=(13, 8.5))
    label_points_by_core = {0: [], 1: [], 2: [], 3: [], 4: []}

    def collect_dps_labels(x_vals, y_vals, color, series_name, option_idx):
        for ci, (xv, yv) in enumerate(zip(x_vals, y_vals)):
            label_points_by_core[ci].append({
                "x": xv,
                "y": yv,
                "color": color,
                "text": f"{int(round(yv))}",
                "series": series_name,
                "option_idx": option_idx,
            })

    top_colors = ["#E4572E", "#F3A712", "#54A24B", "#4C78A8", "#B279A2"]
    for i, r in enumerate(top5_non_control):
        color = top_colors[i % len(top_colors)]
        x4 = r["x"][:4]
        y4 = r["y"][:4]
        opts = r.get("top5_options", [])
        if not opts:
            plt.plot(
                x4, y4,
                color=color, linewidth=2.4, marker="D", markersize=6,
                label=f"Top{i+1} {r['label']} (RelDPG {r['rel_dpg_score']:.2f})"
            )
            collect_dps_labels(x4, y4, color=color, series_name=f"Top{i+1}", option_idx=0)
            continue
        for oi, o in enumerate(opts):
            alpha = 0.95 if oi == 0 else 0.72
            ls = "-" if oi == 0 else "--"
            marker = "D" if oi == 0 else "s"
            p = r["path"]
            label4 = f"{item_short[p[0]]}-{item_short[p[1]]}-{item_short[p[2]]}-{item_short[p[3]]}"
            xs = x4 + [o["cost"]]
            ys = y4 + [o["dps"]]
            plt.plot(
                xs, ys,
                color=color, linewidth=2.2, marker=marker, markersize=6, linestyle=ls, alpha=alpha,
                label=f"Top{i+1} {label4}+{item_short[o['item']]} (RelDPG {r['rel_dpg_score']:.2f})"
            )
            collect_dps_labels(xs, ys, color=color, series_name=f"Top{i+1}", option_idx=oi)

    ctrl_colors = ["#111111", "#666666"]
    for i, r in enumerate(graph_controls):
        color = ctrl_colors[i % len(ctrl_colors)]
        x4 = r["x"][:4]
        y4 = r["y"][:4]
        opts = r.get("top5_options", [])
        if not opts:
            ctrl_desc = control_build_text.get(r["control_label"], "Unknown")
            plt.plot(
                x4, y4,
                color=color, linewidth=2.8, marker="o", markersize=7, linestyle="--",
                label=f"{r['control_label']}({ctrl_desc}) {r['label']} (RelDPG {r['rel_dpg_score']:.2f})"
            )
            collect_dps_labels(x4, y4, color=color, series_name=r["control_label"], option_idx=0)
            continue
        for oi, o in enumerate(opts):
            alpha = 0.95 if oi == 0 else 0.72
            ls = "--" if oi == 0 else ":"
            xs = x4 + [o["cost"]]
            ys = y4 + [o["dps"]]
            ctrl_desc = control_build_text.get(r["control_label"], "Unknown")
            plt.plot(
                xs, ys,
                color=color, linewidth=2.6, marker="o", markersize=7, linestyle=ls, alpha=alpha,
                label=f"{r['control_label']}({ctrl_desc}) +{item_short[o['item']]} (RelDPG {r['rel_dpg_score']:.2f})"
            )
            collect_dps_labels(xs, ys, color=color, series_name=r["control_label"], option_idx=oi)

    # 코어 타이밍(각 x축 위치)별로 라벨을 세로 정렬해 충돌 최소화
    for core_idx, points in label_points_by_core.items():
        if not points:
            continue
        points_sorted = sorted(points, key=lambda p: p["y"])
        y_min = points_sorted[0]["y"]
        y_max = points_sorted[-1]["y"]
        spread = max(80.0, y_max - y_min)
        min_gap = max(22.0, spread * 0.055)

        adjusted_y = []
        for p in points_sorted:
            if not adjusted_y:
                adjusted_y.append(p["y"])
            else:
                adjusted_y.append(max(p["y"], adjusted_y[-1] + min_gap))

        for idx in range(len(adjusted_y) - 2, -1, -1):
            adjusted_y[idx] = min(adjusted_y[idx], adjusted_y[idx + 1] - min_gap)

        x_dir = -1 if core_idx in (0, 2, 4) else 1
        x_off = 22 if x_dir > 0 else -22
        for p, y_adj in zip(points_sorted, adjusted_y):
            plt.annotate(
                p["text"],
                xy=(p["x"], p["y"]),
                xytext=(x_off, y_adj - p["y"]),
                textcoords="offset points",
                ha="left" if x_dir > 0 else "right",
                va="center",
                fontsize=6.8,
                color=p["color"],
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=p["color"], alpha=0.82, lw=0.6),
                arrowprops=dict(arrowstyle="-", color=p["color"], alpha=0.35, lw=0.6),
            )

    plt.title("Kai'Sa Power Spike: 4-Core Ranked Top5 + 5C Top2 Options (DPS Labels)")
    plt.xlabel("Total Gold at Core Timing")
    plt.ylabel("DPS (Auto Attack Only)")
    plt.grid(True, alpha=0.3)
    plt.legend(loc="best", fontsize=8)
    plt.tight_layout()
    plt.show()


def run_cli(args=None):
    """카이사 CLI를 실행한다.

    기본은 1~5코어 receding-horizon이며 `legacy-ranking`은 교체 전 4코어 전수
    랭킹과 5코어 확장 표·그래프를 실행한다. 숫자 인자는 기본 탐색의 할인율이다.
    """
    import sys

    cli_args = list(sys.argv[1:] if args is None else args)
    mode = "default"
    if cli_args and cli_args[0] == "legacy-ranking":
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
    main(gamma=gamma)


if __name__ == "__main__":
    run_cli()
