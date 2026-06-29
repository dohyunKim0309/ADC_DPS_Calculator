import matplotlib.pyplot as plt
# import json # JSON 저장 제거
# import os # JSON 저장 제거
# from datetime import datetime # JSON 저장 제거
from adc_sim.champion import Ashe, Jinx, Target, Yunara
from adc_sim.items import (
    KrakenSlayer, InfinityEdge, BerserkerGreaves, BladeOfRuinedKing,
    TheCollector, YunTalWildarrows, PhantomDancer, HextechScopeC44, Stormrazor, RunaansHurricane, StatikkShiv,
    GuinsoosRageblade, Terminus, MortalReminder, Bloodthirster, LordDominiksRegards, SerpentsFang, Item, GuardianAngel, MercurialScimitar,
    Pickaxe, BFSword, ScoutingsSlingshot, LongSword, RecurveBow, Noonquiver, VampiricScepter, HearthboundAxe, Dagger, CloakofAgility,
    EssenceReaver, DemonHunterCrossbow
)
from adc_sim.settings import SIMULATION_SETTINGS
from adc_sim.runes import LethalTempo, CutDown
from adc_sim.engine import run_simulation


# 코어 단계별 고정 타겟 스탯
CORE_TARGET_STATS = {
    1: {"hp": 1700, "armor": 50, "mr": 25},
    2: {"hp": 1900, "armor": 70, "mr": 30},
    3: {"hp": 2400, "armor": 100, "mr": 50},
    4: {"hp": 2600, "armor": 120, "mr": 70},
    5: {"hp": 3000, "armor": 150, "mr": 90},
}

# 코어 타이밍별 애쉬 레벨/Q 레벨
CORE_ASHE_LEVELS = {
    1: {"level": 9, "q_level": 2},
    2: {"level": 11, "q_level": 4},
    3: {"level": 13, "q_level": 5},
    4: {"level": 15, "q_level": 5},
    5: {"level": 17, "q_level": 5},
}

# 코어 타이밍별 징크스 레벨/Q 레벨 (챔피언 레벨은 애쉬와 동일)
CORE_JINX_LEVELS = {
    1: {"level": CORE_ASHE_LEVELS[1]["level"], "q_level": 3},
    2: {"level": CORE_ASHE_LEVELS[2]["level"], "q_level": 4},
    3: {"level": CORE_ASHE_LEVELS[3]["level"], "q_level": 5},
    4: {"level": CORE_ASHE_LEVELS[4]["level"], "q_level": 5},
    5: {"level": CORE_ASHE_LEVELS[5]["level"], "q_level": 5},
}

# 코어 타이밍별 유나라 레벨/Q 레벨 (챔피언 레벨은 애쉬와 동일)
# [Hypothesis] 스킬오더 가정: Q 선마 → W 차선마 → E, 궁(R) 6/11/16.
# 순수 맥스 오더로 도출 → 레벨 9/11/13/15/17 시점의 W 레벨 3/4/5/5/5, 궁 레벨 1/2/2/2/3.
# (기존 q_level 가정은 건드리지 않고 W/R만 추가)
CORE_YUNARA_LEVELS = {
    1: {"level": CORE_ASHE_LEVELS[1]["level"], "q_level": 3, "w_level": 3, "r_level": 1},
    2: {"level": CORE_ASHE_LEVELS[2]["level"], "q_level": 4, "w_level": 4, "r_level": 2},
    3: {"level": CORE_ASHE_LEVELS[3]["level"], "q_level": 5, "w_level": 5, "r_level": 2},
    4: {"level": CORE_ASHE_LEVELS[4]["level"], "q_level": 5, "w_level": 5, "r_level": 2},
    5: {"level": CORE_ASHE_LEVELS[5]["level"], "q_level": 5, "w_level": 5, "r_level": 3},
}


def build_target_for_core(core_tier):
    stats = CORE_TARGET_STATS[core_tier]
    return Target(
        hp=stats["hp"],
        armor=stats["armor"],
        magic_resist=stats["mr"],
        bonus_hp=max(0, stats["hp"] - 1500),
    )


# 아이템 키 → 인스턴스 생성은 통합 레지스트리 사용 (스탯/가격은 adc_sim/data/items_data.py)
from adc_sim.data.items_registry import create_item_from_key
from adc_sim.data.items_data import DORAN_OPTIONS, DORAN_SHORT, ADC_PACKAGES


def simulate_ashe_core_path(core_item_keys, core_tier, doran_key=None, boots_key="berserker", rune_as_bonus=0.0):
    """Simulate Ashe DPS and total gold for the given core progression.

    doran_key: 시작 도란 아이템(검/활). None이면 미포함.
    boots_key: 신발(기본 광전사). rune_as_bonus: 공속 룬(민첩함 등)의 평타 공속 가산(골드 무료).
    """
    target = build_target_for_core(core_tier)
    level_cfg = CORE_ASHE_LEVELS[core_tier]
    ashe = Ashe(level=level_cfg["level"], q_level=level_cfg["q_level"])
    ashe.set_rune(LethalTempo())
    ashe.set_sub_rune(CutDown())

    core_items = []
    for idx, key in enumerate(core_item_keys, start=1):
        # 윤탈 치명타 가정:
        # - 구매한 코어 타이밍: 5% (단, 1코어 구매는 0%)
        # - 그 다음 코어 타이밍부터: 25%
        if key == "yuntal25":
            current_tier = len(core_item_keys)
            purchase_tier = idx
            if current_tier == purchase_tier:
                if idx == 1:
                    yuntal_crit = 0.0
                elif idx == 2:
                    yuntal_crit = 0.12
                else:
                    yuntal_crit = 0.05
            else:
                yuntal_crit = 0.25
            core_items.append(create_item_from_key(key, yuntal_crit=yuntal_crit))
        else:
            core_items.append(create_item_from_key(key))

    doran_items = [create_item_from_key(doran_key)] if doran_key else []
    items = doran_items + [create_item_from_key(boots_key)] + core_items
    total_cost = 0
    for item in items:
        total_cost += item.cost
        ashe.add_item(item)
    ashe.bonus_as_percent += rune_as_bonus  # 공속 룬(민첩함): 골드 무료, 평타 공속 가산

    _, dps, _ = run_simulation(ashe, target, verbose=False)
    return dps, total_cost


def simulate_jinx_reference_path(core_tier, q_mode="minigun", q_stacks=3):
    # 비교 기준: C44 -> PD -> IE -> LDR (징크스 Q 모드 고정)
    jinx_core_order = ["c44", "pd", "ie", "ldr"]
    target = build_target_for_core(core_tier)
    level_cfg = CORE_JINX_LEVELS[core_tier]
    jinx = Jinx(level=level_cfg["level"], q_level=level_cfg["q_level"], minigun_stacks=q_stacks, q_mode=q_mode)
    jinx.set_rune(LethalTempo())
    jinx.set_sub_rune(CutDown())

    core_items = [create_item_from_key(k) for k in jinx_core_order[:core_tier]]
    items = [BerserkerGreaves()] + core_items

    total_cost = 0
    for item in items:
        total_cost += item.cost
        jinx.add_item(item)

    _, dps, _ = run_simulation(jinx, target, verbose=False)
    return dps, total_cost


def simulate_yunara_reference_path(core_tier):
    # 비교 기준: Krk -> PD -> IE -> LDR
    yunara_core_order = ["kraken", "pd", "ie", "ldr"]
    target = build_target_for_core(core_tier)
    level_cfg = CORE_YUNARA_LEVELS[core_tier]
    yunara = Yunara(level=level_cfg["level"], q_level=level_cfg["q_level"],
                    w_level=level_cfg["w_level"], r_level=level_cfg["r_level"])
    yunara.set_rune(LethalTempo())
    yunara.set_sub_rune(CutDown())

    core_items = [create_item_from_key(k) for k in yunara_core_order[:core_tier]]
    items = [BerserkerGreaves()] + core_items

    total_cost = 0
    for item in items:
        total_cost += item.cost
        yunara.add_item(item)

    # 요청 반영: 전투 시작과 동시에 궁극기로 Q 활성화 상태 진입
    yunara.activate_q(0.0)

    _, dps, _ = run_simulation(yunara, target, verbose=False)
    return dps, total_cost


def simulate_yunara_core_path(core_item_keys, core_tier, doran_key=None, boots_key="berserker", rune_as_bonus=0.0):
    """Simulate Yunara DPS and total gold for the given core progression.

    doran_key: 시작 도란 아이템(검/활). None이면 미포함.
    boots_key: 신발(기본 광전사). rune_as_bonus: 공속 룬(민첩함 등)의 평타 공속 가산(골드 무료).
    """
    target = build_target_for_core(core_tier)
    level_cfg = CORE_YUNARA_LEVELS[core_tier]
    yunara = Yunara(level=level_cfg["level"], q_level=level_cfg["q_level"],
                    w_level=level_cfg["w_level"], r_level=level_cfg["r_level"])
    yunara.set_rune(LethalTempo())
    yunara.set_sub_rune(CutDown())

    active_core_keys = list(core_item_keys[:core_tier])
    core_items = []
    for idx, key in enumerate(active_core_keys, start=1):
        if key == "yuntal25":
            current_tier = len(active_core_keys)
            purchase_tier = idx
            # [Hypothesis] 윤탈 치명타 누적 가정: 구매한 그 코어 시점=10%(전 코어 통일),
            # 다음 코어부터는 항상 25%. 실측이 아닌 스택 누적 속도에 대한 단순 가정.
            if current_tier == purchase_tier:
                yuntal_crit = 0.10
            else:
                yuntal_crit = 0.25
            core_items.append(create_item_from_key(key, yuntal_crit=yuntal_crit))
        else:
            core_items.append(create_item_from_key(key))

    doran_items = [create_item_from_key(doran_key)] if doran_key else []
    items = doran_items + [create_item_from_key(boots_key)] + core_items
    total_cost = 0
    for item in items:
        total_cost += item.cost
        yunara.add_item(item)
    yunara.bonus_as_percent += rune_as_bonus  # 공속 룬(민첩함): 골드 무료, 평타 공속 가산

    # 현재 비교/시뮬 기준: 전투 시작 시 Q 활성 상태
    yunara.activate_q(0.0)
    _, dps, _ = run_simulation(yunara, target, verbose=False)
    return dps, total_cost


def build_ashe_like_core_report_meta(champion_name, full_path, core_tier):
    """Build serializable metadata for Ashe/Yunara core-path report rows."""
    active_path = tuple(full_path[:core_tier])
    return {
        "champion": champion_name,
        "core_tier": core_tier,
        "full_path": list(full_path),
        "active_path": list(active_path),
        "build": "-".join(full_path),
        "active_build": "-".join(active_path),
    }


def _build_ashe_4core_all_paths():
    core1_candidates = ["kraken", "yuntal25", "storm", "c44", "bot", "guinsoo", "terminus"]
    core2_candidates = ["kraken", "yuntal25", "storm", "c44", "bot", "pd", "runaan", "terminus", "guinsoo"]
    core3_candidates = ["ie", "ldr", "guinsoo", "terminus"]
    core4_candidates = ["ie", "ldr", "storm", "c44", "pd", "runaan", "kraken", "statikk", "guinsoo", "terminus"]

    all_paths = []
    seen_exact_paths = set()
    pen_exclusive_keys = {"terminus", "ldr", "mortal"}

    for c1 in core1_candidates:
        for c2 in core2_candidates:
            if c1 == c2:
                continue
            for c3 in core3_candidates:
                if c3 in {c1, c2}:
                    continue
                for c4 in core4_candidates:
                    if c4 in {c1, c2, c3}:
                        continue
                    path_keys = [c1, c2, c3, c4]
                    pen_count = sum(1 for key in path_keys if key in pen_exclusive_keys)
                    if pen_count > 1:
                        continue
                    exact_path = (c1, c2, c3, c4)
                    if exact_path in seen_exact_paths:
                        continue
                    seen_exact_paths.add(exact_path)
                    all_paths.append(exact_path)

    forced_paths = []
    for c3 in core3_candidates:
        for c4 in core4_candidates:
            if c4 == c3:
                continue
            if c4 in {"yuntal25", "kraken"}:
                continue
            path_keys = ["yuntal25", "kraken", c3, c4]
            pen_count = sum(1 for key in path_keys if key in pen_exclusive_keys)
            if pen_count > 1:
                continue
            forced_paths.append(("yuntal25", "kraken", c3, c4))
            forced_paths.append(("kraken", "yuntal25", c3, c4))
    for fp in forced_paths:
        if fp not in seen_exact_paths:
            seen_exact_paths.add(fp)
            all_paths.append(fp)

    return all_paths


def _rank_ashe_like_4core_paths(simulate_core_path_fn):
    """Rank Ashe-like 4-core paths while preserving per-core DPS/gold series.

    각 경로를 도란검/도란활 두 경우로 평가(2배)하고, 같은 4아이템 집합은
    (순서 × 도란) 중 최고 점수 하나로 dedup → 빌드별 최적 도란이 자동 선택된다.
    컨트롤(기준) 빌드도 도란 최적을 고른다(가중 DPG 최대).
    """
    control_combo_key = tuple(sorted(("kraken", "pd", "ie", "ldr")))
    all_paths = _build_ashe_4core_all_paths()

    core_weight_raw = [5.0, 4.0, 3.0, 3.0]
    weight_sum = sum(core_weight_raw)
    core_weights = [w / weight_sum for w in core_weight_raw]

    # (경로 × 패키지A/B) 전 조합 평가
    base_results = []
    for c1, c2, c3, c4 in all_paths:
        for pkg in ADC_PACKAGES:
            kw = dict(doran_key=pkg["doran"], boots_key=pkg["boots"], rune_as_bonus=pkg["rune_as"])
            dps1, cost1 = simulate_core_path_fn([c1], 1, **kw)
            dps2, cost2 = simulate_core_path_fn([c1, c2], 2, **kw)
            dps3, cost3 = simulate_core_path_fn([c1, c2, c3], 3, **kw)
            dps4, cost4 = simulate_core_path_fn([c1, c2, c3, c4], 4, **kw)
            base_results.append({
                "base_key": (c1, c2, c3, c4),
                "doran": pkg["doran"],
                "boots": pkg["boots"],
                "rune_as": pkg["rune_as"],
                "pkg_label": pkg["label"],
                "x": [cost1, cost2, cost3, cost4],
                "y": [dps1, dps2, dps3, dps4],
                "is_control": tuple(sorted((c1, c2, c3, c4))) == control_combo_key,
            })

    def _weighted_dpg(res):
        return sum(
            core_weights[i] * (res["y"][i] / (res["x"][i] / 1000.0) if res["x"][i] > 0 else 0.0)
            for i in range(4)
        )

    # 컨트롤 baseline: 컨트롤 빌드(검/활) 중 가중 DPG 최대
    control_candidates = [r for r in base_results if r["is_control"]]
    if not control_candidates:
        raise RuntimeError("Control build Krk-PD-IE-LDR not found in generated Ashe-like paths.")
    best_control = max(control_candidates, key=_weighted_dpg)
    ctrl_x = best_control["x"]
    ctrl_y = best_control["y"]
    ctrl_dpg = [ctrl_y[i] / (ctrl_x[i] / 1000.0) if ctrl_x[i] > 0 else 0.0 for i in range(4)]

    for res in base_results:
        row_dpg = [
            res["y"][i] / (res["x"][i] / 1000.0) if res["x"][i] > 0 else 0.0
            for i in range(4)
        ]
        rels = [(row_dpg[i] / ctrl_dpg[i]) if ctrl_dpg[i] > 0 else 0.0 for i in range(4)]
        res["rel_dpg_score"] = sum(core_weights[i] * rels[i] for i in range(4)) * 100.0

    combo_best = {}
    for res in base_results:
        combo_key = tuple(sorted(res["base_key"]))
        prev = combo_best.get(combo_key)
        if prev is None or res["rel_dpg_score"] > prev["rel_dpg_score"]:
            combo_best[combo_key] = res

    ranked = sorted(combo_best.values(), key=lambda r: r["rel_dpg_score"], reverse=True)
    return {
        "ranked": ranked,
        "top1": ranked[0],
        "control": next(r for r in ranked if r["is_control"]),
        "all_paths_count": len(all_paths),
        "packages_evaluated": len(ADC_PACKAGES),
    }


_ASHE_4CORE_TOP1_CACHE = None


def get_ashe_4core_top1_build():
    global _ASHE_4CORE_TOP1_CACHE
    if _ASHE_4CORE_TOP1_CACHE is None:
        ranking = _rank_ashe_like_4core_paths(simulate_ashe_core_path)
        top1 = ranking["top1"]
        _ASHE_4CORE_TOP1_CACHE = {
            "path": top1["base_key"],
            "doran": top1["doran"],
            "boots": top1["boots"],
            "rune_as": top1["rune_as"],
            "pkg_label": top1["pkg_label"],
            "score": top1["rel_dpg_score"],
            "control_path": ranking["control"]["base_key"],
            "control_pkg": ranking["control"]["pkg_label"],
            "total_paths_tested": ranking["all_paths_count"],
        }
    return _ASHE_4CORE_TOP1_CACHE


# Yunara 의 4코어 top1 랭킹은 adc_sim/simulations/yunara.py 가 정본(자체 표/그래프 포함).
# 과거 여기 있던 중복 get_yunara_4core_top1_build 는 제거(미사용·혼란 방지).


# 1코어 아이템 세트 생성 함수
def get_1core_item_set(set_name):
    # 1. Yun(10)
    if set_name == "Set1":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.10)]
    # 2. Yun(5)
    elif set_name == "Set2":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.05)]
    # 3. Yun(0)
    elif set_name == "Set3":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.0)]
    # 4. Yun(15)
    elif set_name == "Set4":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.15)]
    # 5. Yun(20)
    elif set_name == "Set5":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.20)]
    # 6. Yun(25)
    elif set_name == "Set6":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.25)]
    # 7. Krk
    elif set_name == "Set7":
        return [BerserkerGreaves(), KrakenSlayer()]
    # 8. Bot
    elif set_name == "Set8":
        return [BerserkerGreaves(), BladeOfRuinedKing()]
    # 9. Bot(AS18)
    elif set_name == "Set9":
        bot = BladeOfRuinedKing()
        bot.stats['as'] += 0.18
        bot.name = "BotRK (AS+18%)"
        return [BerserkerGreaves(), bot]
    # 10. Storm
    elif set_name == "Set10":
        return [BerserkerGreaves(), Stormrazor()]
    # 11. Shiv
    elif set_name == "Set11":
        return [BerserkerGreaves(), StatikkShiv()]
    # 12. C44
    elif set_name == "Set12":
        return [BerserkerGreaves(), HextechScopeC44()]
    # 13. IE
    elif set_name == "Set13":
        return [BerserkerGreaves(), InfinityEdge()]
    return []

# 2코어 아이템 세트 생성 함수
def get_2core_item_set(set_name):
    # 1. Yun(25) + Storm
    if set_name == "Set1":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.25), Stormrazor()]
    # 2. Yun(25) + Krk
    elif set_name == "Set2":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.25), KrakenSlayer()]
    # 3. Yun(25) + Bot
    elif set_name == "Set3":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.25), BladeOfRuinedKing()]
    # 4. Yun(25) + Shiv
    elif set_name == "Set4":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.25), StatikkShiv()]
    # 5. Yun(25) + PD
    elif set_name == "Set5":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.25), PhantomDancer()]
    # 6. Yun(25) + Runaan
    elif set_name == "Set6":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.25), RunaansHurricane()]
    # 7. Yun(25) + C44
    elif set_name == "Set7":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.25), HextechScopeC44()]
    # 8. Krk + Yun(15)
    elif set_name == "Set8":
        return [BerserkerGreaves(), KrakenSlayer(), YunTalWildarrows(crit=0.15)]
    # 9. Krk + Bot
    elif set_name == "Set9":
        return [BerserkerGreaves(), KrakenSlayer(), BladeOfRuinedKing()]
    # 10. Krk + PD
    elif set_name == "Set10":
        return [BerserkerGreaves(), KrakenSlayer(), PhantomDancer()]
    # 11. Krk + Runaan
    elif set_name == "Set11":
        return [BerserkerGreaves(), KrakenSlayer(), RunaansHurricane()]
    # 12. Krk + Storm
    elif set_name == "Set12":
        return [BerserkerGreaves(), KrakenSlayer(), Stormrazor()]
    # 13. Krk + C44
    elif set_name == "Set13":
        return [BerserkerGreaves(), KrakenSlayer(), HextechScopeC44()]
    # 14. Bot(AS18) + Storm
    elif set_name == "Set14":
        bot = BladeOfRuinedKing()
        bot.stats['as'] += 0.18
        bot.name = "BotRK (AS+18%)"
        return [BerserkerGreaves(), bot, Stormrazor()]
    # 15. Bot(AS18) + Shiv
    elif set_name == "Set15":
        bot = BladeOfRuinedKing()
        bot.stats['as'] += 0.18
        bot.name = "BotRK (AS+18%)"
        return [BerserkerGreaves(), bot, StatikkShiv()]
    # 16. Bot(AS18) + PD
    elif set_name == "Set16":
        bot = BladeOfRuinedKing()
        bot.stats['as'] += 0.18
        bot.name = "BotRK (AS+18%)"
        return [BerserkerGreaves(), bot, PhantomDancer()]
    # 17. Bot(AS18) + Runaan
    elif set_name == "Set17":
        bot = BladeOfRuinedKing()
        bot.stats['as'] += 0.18
        bot.name = "BotRK (AS+18%)"
        return [BerserkerGreaves(), bot, RunaansHurricane()]
    # 18. Bot(AS18) + C44
    elif set_name == "Set18":
        bot = BladeOfRuinedKing()
        bot.stats['as'] += 0.18
        bot.name = "BotRK (AS+18%)"
        return [BerserkerGreaves(), bot, HextechScopeC44()]
    # 19. Bot(AS18) + Yun(15)
    elif set_name == "Set19":
        bot = BladeOfRuinedKing()
        bot.stats['as'] += 0.18
        bot.name = "BotRK (AS+18%)"
        return [BerserkerGreaves(), bot, YunTalWildarrows(crit=0.15)]
    return []

# 3코어 아이템 세트 생성 함수
def get_3core_item_set(set_name):
    # 1. Col+Yun+IE
    if set_name == "Set1":
        return [TheCollector(), YunTalWildarrows(crit=0.25), InfinityEdge(), BerserkerGreaves()]
    # 2. Col+Yun+LDR
    elif set_name == "Set2":
        return [TheCollector(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), BerserkerGreaves()]
    # 3. Krk+PD+IE
    elif set_name == "Set3":
        return [KrakenSlayer(), PhantomDancer(), InfinityEdge(), BerserkerGreaves()]
    # 4. Krk+PD+LDR
    elif set_name == "Set4":
        return [KrakenSlayer(), PhantomDancer(), LordDominiksRegards(), BerserkerGreaves()]
    # 5. Krk+Bot+Gui
    elif set_name == "Set5":
        return [KrakenSlayer(), BladeOfRuinedKing(), GuinsoosRageblade(), BerserkerGreaves()]
    # 6. Krk+Bot+LDR
    elif set_name == "Set6":
        return [KrakenSlayer(), BladeOfRuinedKing(), LordDominiksRegards(), BerserkerGreaves()]
    # 7. Yun+Krk+LDR
    elif set_name == "Set7":
        return [YunTalWildarrows(crit=0.25), KrakenSlayer(), LordDominiksRegards(), BerserkerGreaves()]
    # 8. Krk+BT(AS18)+LDR
    elif set_name == "Set8":
        bt = Bloodthirster()
        bt.stats['as'] = 0.18
        bt.name = "Bloodthirster (AS+18%)"
        return [KrakenSlayer(), bt, LordDominiksRegards(), BerserkerGreaves()]
    # 9. Yun+Krk+IE
    elif set_name == "Set9":
        return [YunTalWildarrows(crit=0.25), KrakenSlayer(), InfinityEdge(), BerserkerGreaves()]
    # 10. ER+DHC+IE
    elif set_name == "Set10":
        return [EssenceReaver(), DemonHunterCrossbow(), InfinityEdge(), BerserkerGreaves()]
    # 11. ER+DHC+LDR
    elif set_name == "Set11":
        return [EssenceReaver(), DemonHunterCrossbow(), LordDominiksRegards(), BerserkerGreaves()]
    # 12. ER+Yun+IE
    elif set_name == "Set12":
        return [EssenceReaver(), YunTalWildarrows(crit=0.25), InfinityEdge(), BerserkerGreaves()]
    # 13. ER+Yun+LDR
    elif set_name == "Set13":
        return [EssenceReaver(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), BerserkerGreaves()]
    # 14. Yun+Krk+C44
    elif set_name == "Set14":
        return [YunTalWildarrows(crit=0.25), KrakenSlayer(), HextechScopeC44(), BerserkerGreaves()]
    # 15. ER+Yun+C44
    elif set_name == "Set15":
        return [EssenceReaver(), YunTalWildarrows(crit=0.25), HextechScopeC44(), BerserkerGreaves()]
    # 16. Bot(AD5.4, AS8)+Yun+LDR
    elif set_name == "Set16":
        bot = BladeOfRuinedKing()
        bot.stats['ad'] += 5.4
        bot.stats['as'] += 0.08
        bot.name = "BotRK (AD+5.4, AS+8%)"
        return [bot, YunTalWildarrows(crit=0.25), LordDominiksRegards(), BerserkerGreaves()]
    # 17. Bot(AD5.4, AS8)+Yun+IE
    elif set_name == "Set17":
        bot = BladeOfRuinedKing()
        bot.stats['ad'] += 5.4
        bot.stats['as'] += 0.08
        bot.name = "BotRK (AD+5.4, AS+8%)"
        return [bot, YunTalWildarrows(crit=0.25), InfinityEdge(), BerserkerGreaves()]
    # 18. Bot(AS18)+Yun+LDR
    elif set_name == "Set18":
        bot = BladeOfRuinedKing()
        bot.stats['as'] += 0.18
        bot.name = "BotRK (AS+18%)"
        return [bot, YunTalWildarrows(crit=0.25), LordDominiksRegards(), BerserkerGreaves()]
    # 19. Bot(AS18)+Yun+IE
    elif set_name == "Set19":
        bot = BladeOfRuinedKing()
        bot.stats['as'] += 0.18
        bot.name = "BotRK (AS+18%)"
        return [bot, YunTalWildarrows(crit=0.25), InfinityEdge(), BerserkerGreaves()]
    # 20. Bot(AS18)+ER+LDR
    elif set_name == "Set20":
        bot = BladeOfRuinedKing()
        bot.stats['as'] += 0.18
        bot.name = "BotRK (AS+18%)"
        return [bot, EssenceReaver(), LordDominiksRegards(), BerserkerGreaves()]
    # 21. Bot(AS18)+ER+IE
    elif set_name == "Set21":
        bot = BladeOfRuinedKing()
        bot.stats['as'] += 0.18
        bot.name = "BotRK (AS+18%)"
        return [bot, EssenceReaver(), InfinityEdge(), BerserkerGreaves()]
    # 22. Bot(AD5.4, AS8)+ER+LDR
    elif set_name == "Set22":
        bot = BladeOfRuinedKing()
        bot.stats['ad'] += 5.4
        bot.stats['as'] += 0.08
        bot.name = "BotRK (AD+5.4, AS+8%)"
        return [bot, EssenceReaver(), LordDominiksRegards(), BerserkerGreaves()]
    # 23. Bot(AD5.4, AS8)+ER+IE
    elif set_name == "Set23":
        bot = BladeOfRuinedKing()
        bot.stats['ad'] += 5.4
        bot.stats['as'] += 0.08
        bot.name = "BotRK (AD+5.4, AS+8%)"
        return [bot, EssenceReaver(), InfinityEdge(), BerserkerGreaves()]
    # 24. C44+Yun+LDR
    elif set_name == "Set24":
        return [HextechScopeC44(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), BerserkerGreaves()]
    # 25. C44+PD+LDR
    elif set_name == "Set25":
        return [HextechScopeC44(), PhantomDancer(), LordDominiksRegards(), BerserkerGreaves()]
    # 26. C44+PD+IE
    elif set_name == "Set26":
        return [HextechScopeC44(), PhantomDancer(), InfinityEdge(), BerserkerGreaves()]
    # 27. C44+Yun+IE
    elif set_name == "Set27":
        return [HextechScopeC44(), YunTalWildarrows(crit=0.25), InfinityEdge(), BerserkerGreaves()]
    # 28. Storm+Yun+LDR
    elif set_name == "Set28":
        return [Stormrazor(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), BerserkerGreaves()]
    return []

# 4코어 아이템 세트 생성 함수
def get_4core_item_set(set_name):
    # 1. ER+DHC+IE+LDR (유행하는 정수 애쉬 빌드)
    if set_name == "Set1":
        return [EssenceReaver(), DemonHunterCrossbow(), InfinityEdge(), LordDominiksRegards(), BerserkerGreaves()]
    # 2. Krk+PD+IE+LDR (기존 크라켄 빌드)
    elif set_name == "Set2":
        return [KrakenSlayer(), PhantomDancer(), InfinityEdge(), LordDominiksRegards(), BerserkerGreaves()]
    # 3. Yun+PD+IE+LDR (기존 윤탈 빌드)
    elif set_name == "Set3":
        return [YunTalWildarrows(crit=0.25), PhantomDancer(), InfinityEdge(), LordDominiksRegards(), BerserkerGreaves()]
    # 4. Yun+Krk+IE+LDR (dps 빌드)
    elif set_name == "Set4":
        return [YunTalWildarrows(crit=0.25), KrakenSlayer(), InfinityEdge(), LordDominiksRegards(), BerserkerGreaves()]
    # 5. ER+Yun+LDR+IE (정수 애쉬 변형 빌드)
    elif set_name == "Set5":
        return [EssenceReaver(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), InfinityEdge(), BerserkerGreaves()]
    # 6. Yun+Bot(AS18)+IE+LDR (몰왕 포함 dps 빌드 1)
    elif set_name == "Set6":
        bot = BladeOfRuinedKing()
        bot.stats['as'] += 0.18
        bot.name = "BotRK (AS+18%)"
        return [YunTalWildarrows(crit=0.25), bot, InfinityEdge(), LordDominiksRegards(), BerserkerGreaves()]
    # 7. Yun+Bot(AD5.4, AS8)+IE+LDR (몰왕 포함 dps 빌드 2)
    elif set_name == "Set7":
        bot = BladeOfRuinedKing()
        bot.stats['ad'] += 5.4
        bot.stats['as'] += 0.08
        bot.name = "BotRK (AD+5.4, AS+8%)"
        return [YunTalWildarrows(crit=0.25), bot, InfinityEdge(), LordDominiksRegards(), BerserkerGreaves()]
    return []

# 5코어 아이템 세트 생성 함수
def get_5core_item_set(set_name):
    # 1. Yun + PD + LDR + IE + BTc
    if set_name == "Set1":
        return [YunTalWildarrows(crit=0.25), PhantomDancer(), LordDominiksRegards(), InfinityEdge(), Bloodthirster(), BerserkerGreaves()]
    # 2. Yun + PD + LDR + IE + BotRK
    elif set_name == "Set2":
        return [YunTalWildarrows(crit=0.25), PhantomDancer(), LordDominiksRegards(), InfinityEdge(), BladeOfRuinedKing(), BerserkerGreaves()]
    # 3. Yun + PD + LDR + IE + Krk
    elif set_name == "Set3":
        return [YunTalWildarrows(crit=0.25), PhantomDancer(), LordDominiksRegards(), InfinityEdge(), KrakenSlayer(), BerserkerGreaves()]
    # 4. Krk + PD + LDR + IE + BT
    elif set_name == "Set4":
        return [KrakenSlayer(), PhantomDancer(), LordDominiksRegards(), InfinityEdge(), Bloodthirster(), BerserkerGreaves()]
    # 5. Krk + PD + LDR + IE + C44
    elif set_name == "Set5":
        return [KrakenSlayer(), PhantomDancer(), LordDominiksRegards(), InfinityEdge(), HextechScopeC44(), BerserkerGreaves()]
    # 6. ER + DHC + LDR + IE + BT
    elif set_name == "Set6":
        return [EssenceReaver(), DemonHunterCrossbow(), LordDominiksRegards(), InfinityEdge(), Bloodthirster(), BerserkerGreaves()]
    # 7. ER + DHC + LDR + IE + BotRK
    elif set_name == "Set7":
        return [EssenceReaver(), DemonHunterCrossbow(), LordDominiksRegards(), InfinityEdge(), BladeOfRuinedKing(), BerserkerGreaves()]
    # 8. Yun + Krk + LDR + IE + C44
    elif set_name == "Set8":
        return [YunTalWildarrows(crit=0.25), KrakenSlayer(), LordDominiksRegards(), InfinityEdge(), HextechScopeC44(), BerserkerGreaves()]
    # 9. ER + Yun + LDR + IE + C44
    elif set_name == "Set9":
        return [EssenceReaver(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), InfinityEdge(), HextechScopeC44(), BerserkerGreaves()]
    # 10. ER + Yun + LDR + IE + BT
    elif set_name == "Set10":
        return [EssenceReaver(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), InfinityEdge(), Bloodthirster(), BerserkerGreaves()]
    # 11. ER + Yun + LDR + IE + BotRK
    elif set_name == "Set11":
        return [EssenceReaver(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), InfinityEdge(), BladeOfRuinedKing(), BerserkerGreaves()]
    # 12. Yun + Bot(AS18) + LDR + IE + C44
    elif set_name == "Set12":
        bot = BladeOfRuinedKing()
        bot.stats['as'] += 0.18
        bot.name = "BotRK (AS+18%)"
        return [YunTalWildarrows(crit=0.25), bot, LordDominiksRegards(), InfinityEdge(), HextechScopeC44(), BerserkerGreaves()]
    return []


# --- 메인 실행부 ---
if __name__ == "__main__":
    # 기존 1/2/3코어 단순 DPS 비교 시뮬레이션/그래프는 비활성화
    # (필요 시 이전 버전에서 복원 가능)
    if False:
        print("\n=== 1/2/3-Core Simple Simulation (Disabled) ===")

    # === 빌드 경로 파워스파이크 그래프 ===
    print("\n=== Build Path Power Spike (1->2->3->4->5 Core) ===")
    core1_candidates = ["kraken", "yuntal25", "storm", "c44", "bot", "guinsoo", "terminus"]
    core2_candidates = ["kraken", "yuntal25", "storm", "c44", "bot", "pd", "runaan", "terminus", "guinsoo"]
    core3_candidates = ["ie", "ldr", "guinsoo", "terminus"]
    core4_candidates = ["ie", "ldr", "storm", "c44", "pd", "runaan", "kraken", "statikk", "guinsoo", "terminus"]
    core5_candidates = ["bt", "bot", "c44", "kraken", "pd", "ga", "mercurial"]

    control_paths = {
        ("kraken", "pd", "ie", "ldr"): "Control Krk-PD-IE-LDR",
    }

    item_short = {
        "kraken": "Krk",
        "yuntal25": "Yun",
        "bot_as18": "Bot(AS18)",
        "storm": "Storm",
        "statikk": "Statikk",
        "c44": "C44",
        "bot": "Bot",
        "pd": "PD",
        "runaan": "Runaan",
        "terminus": "Terminus",
        "guinsoo": "Gui",
        "ie": "IE",
        "ldr": "LDR",
        "bt": "BT",
        "ga": "GA",
        "mercurial": "Mercurial",
    }

    all_paths = []
    seen_exact_paths = set()
    pen_exclusive_keys = {"terminus", "ldr", "mortal"}
    for c1 in core1_candidates:
        for c2 in core2_candidates:
            if c1 == c2:
                continue
            for c3 in core3_candidates:
                if c3 in {c1, c2}:
                    continue
                for c4 in core4_candidates:
                    if c4 in {c1, c2, c3}:
                        continue
                    # 방관/관통 계열(경계, LDR, 모렐로 대체 키)의 상호 배타 규칙 (4코어 베이스 기준)
                    path_keys = [c1, c2, c3, c4]
                    pen_count = sum(1 for key in path_keys if key in pen_exclusive_keys)
                    if pen_count > 1:
                        continue

                    # 정확히 같은 경로만 제거 (순서 차이는 점수 계산 후 최적 1개 선택)
                    exact_path = (c1, c2, c3, c4)
                    if exact_path in seen_exact_paths:
                        continue
                    seen_exact_paths.add(exact_path)
                    all_paths.append(exact_path)

    # 윤탈 구매 타이밍 차이를 보기 위해, 아래 2개 경로는 중복 규칙과 무관하게 항상 포함
    forced_paths = []
    for c3 in core3_candidates:
        for c4 in core4_candidates:
            if c4 == c3:
                continue
            # 같은 아이템 중복 구매 불가
            if c4 in {"yuntal25", "kraken"}:
                continue
            path_keys = ["yuntal25", "kraken", c3, c4]
            pen_count = sum(1 for key in path_keys if key in pen_exclusive_keys)
            if pen_count > 1:
                continue
            forced_paths.append(("yuntal25", "kraken", c3, c4))
            forced_paths.append(("kraken", "yuntal25", c3, c4))
    for fp in forced_paths:
        if fp not in seen_exact_paths:
            seen_exact_paths.add(fp)
            all_paths.append(fp)

    print(f"\nPower Spike Paths Used ({len(all_paths)} total)")
    for idx, (c1, c2, c3, c4) in enumerate(all_paths, start=1):
        print(f"{idx:03d}. {item_short[c1]}-{item_short[c2]}-{item_short[c3]}-{item_short[c4]}")

    spike_results = []
    for path in all_paths:
        c1, c2, c3, c4 = path
        for pkg in ADC_PACKAGES:
            kw = dict(doran_key=pkg["doran"], boots_key=pkg["boots"], rune_as_bonus=pkg["rune_as"])
            dps1, cost1 = simulate_ashe_core_path([c1], 1, **kw)
            dps2, cost2 = simulate_ashe_core_path([c1, c2], 2, **kw)
            dps3, cost3 = simulate_ashe_core_path([c1, c2, c3], 3, **kw)
            dps4, cost4 = simulate_ashe_core_path([c1, c2, c3, c4], 4, **kw)
            spike_results.append({
                "path": path,
                "doran": pkg["doran"],
                "pkg_label": pkg["label"],
                "label": f"{item_short[c1]}-{item_short[c2]}-{item_short[c3]}-{item_short[c4]} [{pkg['label']}]",
                "x": [cost1, cost2, cost3, cost4],
                "y": [dps1, dps2, dps3, dps4],
                "is_control": path in control_paths,
                "control_label": control_paths.get(path, ""),
            })

    control_combo_key = tuple(sorted(("kraken", "pd", "ie", "ldr")))

    # 4코어 기준 랭킹용 결과
    base_results = {}
    for res in spike_results:
        c1, c2, c3, c4 = res["path"]
        base_key = (c1, c2, c3, c4)
        dkey = (base_key, res["doran"])  # 패키지(도란검↔활)까지 구분해 두 경우 모두 보존
        if dkey not in base_results:
            base_results[dkey] = {
                "base_key": base_key,
                "doran": res["doran"],
                "pkg_label": res["pkg_label"],
                "label": res["label"],
                "x": res["x"],
                "y": res["y"],
                "is_control": tuple(sorted(base_key)) == control_combo_key,
                "control_label": control_paths.get(("kraken", "pd", "ie", "ldr"), "") if tuple(sorted(base_key)) == control_combo_key else "",
            }
    base_results = list(base_results.values())

    # 상위 빌드 출력 (1~4코어 기준, DPG-only)
    core_weight_raw = [5.0, 4.0, 3.0, 3.0]
    weight_sum = sum(core_weight_raw)
    core_weights = [w / weight_sum for w in core_weight_raw]

    control_results = [r for r in base_results if r["is_control"]]
    # 컨트롤도 도란검/도란활 중 가중 DPG 최대를 baseline 으로
    best_control = max(
        control_results,
        key=lambda r: sum(
            core_weights[i] * (r["y"][i] / (r["x"][i] / 1000.0) if r["x"][i] > 0 else 0.0)
            for i in range(4)
        ),
    )
    control_y1, control_y2, control_y3, control_y4 = best_control["y"]
    ctrl_cost1, ctrl_cost2, ctrl_cost3, ctrl_cost4 = best_control["x"]
    ctrl_dpg1 = control_y1 / (ctrl_cost1 / 1000.0) if ctrl_cost1 > 0 else 0.0
    ctrl_dpg2 = control_y2 / (ctrl_cost2 / 1000.0) if ctrl_cost2 > 0 else 0.0
    ctrl_dpg3 = control_y3 / (ctrl_cost3 / 1000.0) if ctrl_cost3 > 0 else 0.0
    ctrl_dpg4 = control_y4 / (ctrl_cost4 / 1000.0) if ctrl_cost4 > 0 else 0.0

    for res in base_results:
        y1, y2, y3, y4 = res["y"]
        c1, c2, c3, c4 = res["x"]
        dpg1 = y1 / (c1 / 1000.0) if c1 > 0 else 0.0
        dpg2 = y2 / (c2 / 1000.0) if c2 > 0 else 0.0
        dpg3 = y3 / (c3 / 1000.0) if c3 > 0 else 0.0
        dpg4 = y4 / (c4 / 1000.0) if c4 > 0 else 0.0
        rel_dpg_1 = (dpg1 / ctrl_dpg1) if ctrl_dpg1 > 0 else 0.0
        rel_dpg_2 = (dpg2 / ctrl_dpg2) if ctrl_dpg2 > 0 else 0.0
        rel_dpg_3 = (dpg3 / ctrl_dpg3) if ctrl_dpg3 > 0 else 0.0
        rel_dpg_4 = (dpg4 / ctrl_dpg4) if ctrl_dpg4 > 0 else 0.0
        res["rel_dpg_score"] = (
            (core_weights[0] * rel_dpg_1) +
            (core_weights[1] * rel_dpg_2) +
            (core_weights[2] * rel_dpg_3) +
            (core_weights[3] * rel_dpg_4)
        ) * 100.0
        res["spike_score"] = res["rel_dpg_score"]

    # 4코어 아이템 조합이 같고 순서만 다른 경우: 가장 점수가 높은 1개만 유지
    combo_best_results = {}
    for res in base_results:
        combo_key = tuple(sorted(res["base_key"]))
        prev = combo_best_results.get(combo_key)
        if prev is None or res["rel_dpg_score"] > prev["rel_dpg_score"]:
            combo_best_results[combo_key] = res

    base_results = list(combo_best_results.values())

    ranked_by_dpg = sorted(base_results, key=lambda r: r["rel_dpg_score"], reverse=True)
    top5_spikes = ranked_by_dpg[:5]
    top_n = 20
    top20_dpg = ranked_by_dpg[:top_n]

    best_control_rel_dpg = best_control["rel_dpg_score"]
    print(
        f"\nBest Control Baseline (Weighted Relative 5:4:3:3 over 1~4 Core, DPG-only): "
        f"DPG={best_control_rel_dpg:.2f} "
        f"({best_control['control_label']} / {best_control['label']})"
    )

    control_results = [r for r in base_results if r["is_control"]]
    total_rows = top_n + len(control_results)

    def print_relative_table(title, rows, score_key, score_col, show_dpg_columns=False):
        print(f"\n{title}")
        core1 = "1C (DPG)" if show_dpg_columns else "1C (DPS@g)"
        core2 = "2C (DPG)" if show_dpg_columns else "2C (DPS@g)"
        core3 = "3C (DPG)" if show_dpg_columns else "3C (DPS@g)"
        core4 = "4C (DPG)" if show_dpg_columns else "4C (DPS@g)"
        header = (
            f"{'RK':>2} | {'BUILD':<22} | "
            f"{core1:^14} | {core2:^14} | {core3:^14} | {core4:^14} | "
            f"{score_col:^9} | {'VS CTRL':^10} | "
            f"{'C1 ΔDPS/ΔDPG%':^14} | {'C2 ΔDPS/ΔDPG%':^14} | {'C3 ΔDPS/ΔDPG%':^14} | {'C4 ΔDPS/ΔDPG%':^14}"
        )
        print(header)
        print("-" * len(header))
        output_rows = rows + control_results
        baseline = best_control_rel_dpg
        for rank, res in enumerate(output_rows, start=1):
            c1_cost, c2_cost, c3_cost, c4_cost = res["x"]
            dps1, dps2, dps3, dps4 = res["y"]
            diff_pct = ((res[score_key] / baseline) - 1.0) * 100.0 if baseline > 0 else 0.0
            label = res["label"] + (" [CTRL]" if res["is_control"] else "")

            ctrl_dps = [control_y1, control_y2, control_y3, control_y4]
            row_dps = [dps1, dps2, dps3, dps4]
            row_costs = [c1_cost, c2_cost, c3_cost, c4_cost]
            ctrl_costs = [ctrl_cost1, ctrl_cost2, ctrl_cost3, ctrl_cost4]
            row_dpgs = [
                row_dps[0] / (row_costs[0] / 1000.0) if row_costs[0] > 0 else 0.0,
                row_dps[1] / (row_costs[1] / 1000.0) if row_costs[1] > 0 else 0.0,
                row_dps[2] / (row_costs[2] / 1000.0) if row_costs[2] > 0 else 0.0,
                row_dps[3] / (row_costs[3] / 1000.0) if row_costs[3] > 0 else 0.0,
            ]

            core_delta_cells = []
            for i in range(4):
                dps_pct = ((row_dps[i] / ctrl_dps[i]) - 1.0) * 100.0 if ctrl_dps[i] > 0 else 0.0
                row_dpg = row_dps[i] / (row_costs[i] / 1000.0) if row_costs[i] > 0 else 0.0
                ctrl_dpg = ctrl_dps[i] / (ctrl_costs[i] / 1000.0) if ctrl_costs[i] > 0 else 0.0
                dpg_pct = ((row_dpg / ctrl_dpg) - 1.0) * 100.0 if ctrl_dpg > 0 else 0.0
                core_delta_cells.append(f"{dps_pct:+5.1f}/{dpg_pct:+5.1f}")

            if show_dpg_columns:
                c1v = f"{row_dpgs[0]:>10.1f}"
                c2v = f"{row_dpgs[1]:>10.1f}"
                c3v = f"{row_dpgs[2]:>10.1f}"
                c4v = f"{row_dpgs[3]:>10.1f}"
            else:
                c1v = f"{dps1:>6.1f}@{c1_cost:<5}"
                c2v = f"{dps2:>6.1f}@{c2_cost:<5}"
                c3v = f"{dps3:>6.1f}@{c3_cost:<5}"
                c4v = f"{dps4:>6.1f}@{c4_cost:<5}"
            line = (
                f"{rank:>2} | {label:<22} | "
                f"{c1v:>14} | {c2v:>14} | {c3v:>14} | {c4v:>14} | "
                f"{res[score_key]:>9.2f} | {diff_pct:+8.2f}% | "
                f"{core_delta_cells[0]:>14} | {core_delta_cells[1]:>14} | {core_delta_cells[2]:>14} | {core_delta_cells[3]:>14}"
            )
            print(line)

    print_relative_table(
        f"Top {total_rows} Rows: Top {top_n} + All Controls (Rel by DPS/1000g ratio, weighted 5:4:3:3 over 1~4 Core)",
        top20_dpg,
        "rel_dpg_score",
        " REL_DPG%",
        show_dpg_columns=True
    )

    # 징크스 기준 빌드 비교선 (C44-PD-IE-LDR)
    jinx_ref_x = []
    jinx_ref_y = []
    jinx_fish_x = []
    jinx_fish_y = []
    for tier in [1, 2, 3, 4]:
        dps, cost = simulate_jinx_reference_path(tier, q_mode="minigun", q_stacks=0)
        jinx_ref_x.append(cost)
        jinx_ref_y.append(dps)
        fish_dps, fish_cost = simulate_jinx_reference_path(tier, q_mode="fishbones", q_stacks=0)
        jinx_fish_x.append(fish_cost)
        jinx_fish_y.append(fish_dps)

    print("\nJinx Reference Path (C44-PD-IE-LDR, Minigun 0->1->2->3 stacks)")
    for tier in [1, 2, 3, 4]:
        ashe_ctrl_dps = best_control["y"][tier - 1]
        ashe_ctrl_cost = best_control["x"][tier - 1]
        jinx_dps = jinx_ref_y[tier - 1]
        jinx_cost = jinx_ref_x[tier - 1]
        dps_diff_pct = ((jinx_dps / ashe_ctrl_dps) - 1.0) * 100.0 if ashe_ctrl_dps > 0 else 0.0
        print(
            f"{tier}C | Jinx {jinx_dps:.1f}@{jinx_cost}g | "
            f"vs CTRL {ashe_ctrl_dps:.1f}@{ashe_ctrl_cost}g | ΔDPS {dps_diff_pct:+.1f}%"
        )
    print("\nJinx Fishbones Path (C44-PD-IE-LDR, no Q AS stacks, bonus AS x0.9, AD x1.10)")
    for tier in [1, 2, 3, 4]:
        ashe_ctrl_dps = best_control["y"][tier - 1]
        ashe_ctrl_cost = best_control["x"][tier - 1]
        jinx_dps = jinx_fish_y[tier - 1]
        jinx_cost = jinx_fish_x[tier - 1]
        dps_diff_pct = ((jinx_dps / ashe_ctrl_dps) - 1.0) * 100.0 if ashe_ctrl_dps > 0 else 0.0
        print(
            f"{tier}C | Jinx(Fishbones) {jinx_dps:.1f}@{jinx_cost}g | "
            f"vs CTRL {ashe_ctrl_dps:.1f}@{ashe_ctrl_cost}g | ΔDPS {dps_diff_pct:+.1f}%"
        )

    yunara_ref_x = []
    yunara_ref_y = []
    for tier in [1, 2, 3, 4]:
        dps, cost = simulate_yunara_reference_path(tier)
        yunara_ref_x.append(cost)
        yunara_ref_y.append(dps)
    print("\nYunara Reference Path (Krk-PD-IE-LDR, Q 3/4/5/5)")
    for tier in [1, 2, 3, 4]:
        ashe_ctrl_dps = best_control["y"][tier - 1]
        ashe_ctrl_cost = best_control["x"][tier - 1]
        yun_dps = yunara_ref_y[tier - 1]
        yun_cost = yunara_ref_x[tier - 1]
        dps_diff_pct = ((yun_dps / ashe_ctrl_dps) - 1.0) * 100.0 if ashe_ctrl_dps > 0 else 0.0
        print(
            f"{tier}C | Yunara {yun_dps:.1f}@{yun_cost}g | "
            f"vs CTRL {ashe_ctrl_dps:.1f}@{ashe_ctrl_cost}g | ΔDPS {dps_diff_pct:+.1f}%"
        )

    # 4코어 파워스파이크 그래프 (기존 유지)
    plt.figure(figsize=(15, 10))
    for res in base_results:
        if not res["is_control"]:
            plt.plot(res["x"], res["y"], color="#9AA0A6", alpha=0.18, linewidth=0.8, marker="o", markersize=2)

    top4_colors = ["#FF8C00", "#FF4500", "#FF1493", "#8A2BE2", "#20B2AA"]
    top_label_offsets = [(-14, 10), (-14, -12), (10, 10), (10, -12), (0, 16)]
    for i, res in enumerate(top5_spikes):
        color = top4_colors[i % len(top4_colors)]
        plt.plot(
            res["x"], res["y"],
            color=color, linewidth=2.3, marker="D", markersize=5,
            label=f"Top{i+1} {res['label']} (RelDPG:{res['spike_score']:.1f})"
        )
        ox, oy = top_label_offsets[i % len(top_label_offsets)]
        for j in range(4):
            plt.annotate(
                f"{res['y'][j]:.0f}",
                (res["x"][j], res["y"][j]),
                textcoords="offset points",
                xytext=(ox + (j * 2), oy + ((j % 2) * 2)),
                fontsize=7,
                color=color,
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor=color, alpha=0.85, linewidth=0.6)
            )

    ctrl_label_offsets = [(-16, -14), (12, -14), (-16, 12), (12, 12)]
    for res in control_results:
        plt.plot(
            res["x"], res["y"],
            color="#000000", linewidth=2.8, marker="o", markersize=7,
            label=f"{res['control_label']} ({res['label']})"
        )
        for j in range(4):
            cox, coy = ctrl_label_offsets[j % len(ctrl_label_offsets)]
            plt.annotate(
                f"{res['y'][j]:.0f}",
                (res["x"][j], res["y"][j]),
                textcoords="offset points",
                xytext=(cox, coy),
                fontsize=8,
                color="#111111",
                bbox=dict(boxstyle="round,pad=0.18", facecolor="#F8F9FA", edgecolor="#222222", alpha=0.95, linewidth=0.7)
            )

    plt.title("Ashe Build Path Power Spike (1/2/3/4 Core + Top1 5-Core Options)")
    plt.xlabel("Total Gold at Core Timing")
    plt.ylabel("DPS")
    plt.grid(True, alpha=0.3)

    # 5코어 옵션 비교: 4코어 Top1 베이스에 5코어 후보를 붙여 모두 비교
    top1_base = ranked_by_dpg[0]
    b1, b2, b3, b4 = top1_base["base_key"]
    base_set = {b1, b2, b3, b4}
    top1_5core_results = []
    for c5 in core5_candidates:
        if c5 in base_set:
            continue
        dps1, cost1 = simulate_ashe_core_path([b1], 1)
        dps2, cost2 = simulate_ashe_core_path([b1, b2], 2)
        dps3, cost3 = simulate_ashe_core_path([b1, b2, b3], 3)
        dps4, cost4 = simulate_ashe_core_path([b1, b2, b3, b4], 4)
        dps5, cost5 = simulate_ashe_core_path([b1, b2, b3, b4, c5], 5)
        top1_5core_results.append({
            "label": f"{item_short[b1]}-{item_short[b2]}-{item_short[b3]}-{item_short[b4]}-{item_short[c5]}",
            "x": [cost1, cost2, cost3, cost4, cost5],
            "y": [dps1, dps2, dps3, dps4, dps5],
        })

    print(f"\n5-Core Variants on Top1 4-Core Base: {top1_base['label']}")
    for i, res in enumerate(sorted(top1_5core_results, key=lambda r: r['y'][4], reverse=True), start=1):
        print(f"{i:02d}. {res['label']} | 5C DPS: {res['y'][4]:.2f} @ {res['x'][4]}g")

    # 5코어 옵션을 기존 4코어 그래프에 이어서 표시 (4->5 구간만)
    top5_colors = ["#00A676", "#0EA5E9", "#E11D48", "#7C3AED", "#F59E0B", "#14B8A6", "#4B5563"]
    end_label_offsets = [(6, 8), (6, -10), (-26, 8), (-26, -10), (10, 16), (-28, 16), (10, -18)]
    for i, res in enumerate(sorted(top1_5core_results, key=lambda r: r['y'][4], reverse=True)):
        c = top5_colors[i % len(top5_colors)]
        plt.plot(
            res["x"][3:5], res["y"][3:5],
            color=c, linewidth=2.0, linestyle="--", marker="o", markersize=5,
            label=f"5C {res['label'].split('-')[-1]}"
        )
        ex, ey = end_label_offsets[i % len(end_label_offsets)]
        plt.annotate(
            f"{res['y'][4]:.0f}",
            (res["x"][4], res["y"][4]),
            textcoords="offset points",
            xytext=(ex, ey),
            fontsize=7,
            color=c,
            bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor=c, alpha=0.85, linewidth=0.6)
        )

    plt.legend(loc="best", fontsize=9)
    plt.tight_layout()
    plt.show()

    # 2번 그래프: 징크스 기준 빌드 vs 애쉬 Top1 vs 애쉬 대조군
    ashe_top1 = ranked_by_dpg[0]
    plt.figure(figsize=(11, 7))

    plt.plot(
        ashe_top1["x"], ashe_top1["y"],
        color="#E4572E", linewidth=2.6, marker="D", markersize=6,
        label=f"Ashe Top1 {ashe_top1['label']}"
    )
    plt.plot(
        best_control["x"], best_control["y"],
        color="#111111", linewidth=2.6, marker="o", markersize=6,
        label=f"Ashe CTRL {best_control['label']}"
    )
    plt.plot(
        jinx_ref_x, jinx_ref_y,
        color="#00A3A3", linewidth=2.6, marker="s", markersize=6,
        label="Jinx C44-PD-IE-LDR (Minigun Q)"
    )
    plt.plot(
        jinx_fish_x, jinx_fish_y,
        color="#1F7A6B", linewidth=2.4, marker="v", markersize=6, linestyle="--",
        label="Jinx C44-PD-IE-LDR (Fishbones Q)"
    )
    plt.plot(
        yunara_ref_x, yunara_ref_y,
        color="#7B61FF", linewidth=2.4, marker="P", markersize=6,
        label="Yunara Krk-PD-IE-LDR"
    )

    for j in range(4):
        plt.annotate(f"{ashe_top1['y'][j]:.0f}", (ashe_top1["x"][j], ashe_top1["y"][j]),
                     textcoords="offset points", xytext=(8, 10), fontsize=8, color="#E4572E")
        plt.annotate(f"{best_control['y'][j]:.0f}", (best_control["x"][j], best_control["y"][j]),
                     textcoords="offset points", xytext=(8, -12), fontsize=8, color="#111111")
        plt.annotate(f"{jinx_ref_y[j]:.0f}", (jinx_ref_x[j], jinx_ref_y[j]),
                     textcoords="offset points", xytext=(-28, 8), fontsize=8, color="#00A3A3")
        plt.annotate(f"{jinx_fish_y[j]:.0f}", (jinx_fish_x[j], jinx_fish_y[j]),
                     textcoords="offset points", xytext=(-26, -14), fontsize=8, color="#1F7A6B")
        plt.annotate(f"{yunara_ref_y[j]:.0f}", (yunara_ref_x[j], yunara_ref_y[j]),
                     textcoords="offset points", xytext=(10, 18), fontsize=8, color="#7B61FF")

    plt.title("Ashe vs Jinx Power Spike Compare (1/2/3/4 Core)")
    plt.xlabel("Total Gold at Core Timing")
    plt.ylabel("DPS")
    plt.grid(True, alpha=0.3)
    plt.legend(loc="best", fontsize=9)
    plt.tight_layout()
    plt.show()
