from champion import KaiSa, Target
import matplotlib.pyplot as plt
from items import (
    BerserkerGreaves,
    KrakenSlayer,
    Stormrazor,
    YunTalWildarrows,
    StatikkShiv,
    GuinsoosRageblade,
    Terminus,
    PhantomDancer,
    BladeOfRuinedKing,
    NashorsTooth,
    InfinityEdge,
    LordDominiksRegards,
    MortalReminder,
    RabadonsDeathcap, Shadowflame, ImmortalShieldbow,
)
from runes import LethalTempo, CutDown
from engine import run_simulation


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


def create_item_from_key(item_key, yuntal_crit=None):
    if item_key == "kraken":
        return KrakenSlayer()
    if item_key == "storm":
        return Stormrazor()
    if item_key == "yuntal":
        return YunTalWildarrows(crit=0.25 if yuntal_crit is None else yuntal_crit)
    if item_key == "statikk":
        return StatikkShiv()
    if item_key == "guinsoo":
        return GuinsoosRageblade()
    if item_key == "terminus":
        return Terminus()
    if item_key == "pd":
        return PhantomDancer()
    if item_key == "bot":
        return BladeOfRuinedKing()
    if item_key == "nashor":
        return NashorsTooth()
    if item_key == "ie":
        return InfinityEdge()
    if item_key == "ldr":
        return LordDominiksRegards()
    if item_key == "mortal":
        return MortalReminder()
    if item_key == "rabadon":
        return RabadonsDeathcap()
    if item_key == "shadowflame":
        return Shadowflame()
    if item_key == "shieldbow":
        return ImmortalShieldbow()
    raise ValueError(f"Unknown item key: {item_key}")


def get_item_ad_from_key(item_key):
    return create_item_from_key(item_key).stats.get("ad", 0)


def get_yuntal_crit_for_tier(purchase_tier, current_tier):
    # 요청 규칙:
    # - 1코어 구매 시: 1코어 타이밍 0%, 이후 25%
    # - 2코어 구매 시: 2코어 타이밍 10%, 이후 25%
    if purchase_tier == 1:
        return 0.0 if current_tier == 1 else 0.25
    if purchase_tier == 2:
        return 0.10 if current_tier == 2 else 0.25
    return 0.25


def simulate_kaisa_core_path(full_path, core_tier):
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

    items = [BerserkerGreaves()]
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

    # 진화 조건은 카이사 기본 규칙 사용:
    # Q: 보너스 AD >= 100, W: AP >= 100
    kaisa.q_evolved_override = None
    kaisa.w_evolved_override = None

    # 스킬 시나리오를 simulation에서 정의하고 engine가 처리
    skill_plan = {
        "manual_casts": [(0.0, "e"), (0.0, "q"), (0.0, "w")],
        "auto_cast": {"q": True, "w": True, "e": False, "r": False},
        "auto_order": ["q", "w", "e", "r"],
    }

    _, dps, _ = run_simulation(kaisa, target, verbose=False, skill_plan=skill_plan)
    return dps, total_cost, kaisa.w_cast_count


def is_kaisa_w_evolved_at_core(full_path, core_tier=4, include_ap_400_component=False):
    level_cfg = CORE_LEVELS[core_tier]
    e_level_for_tier = get_e_level_for_core(core_tier)
    kaisa = KaiSa(level=level_cfg["level"], q_level=5, w_level=5, e_level=e_level_for_tier, r_level=3)

    # 본 시뮬과 동일하게 신발 포함 상태에서 코어 타이밍 판정
    kaisa.add_item(BerserkerGreaves())
    for idx, key in enumerate(full_path[:core_tier], start=1):
        if key == "yuntal":
            crit = get_yuntal_crit_for_tier(idx, core_tier)
            kaisa.add_item(create_item_from_key(key, yuntal_crit=crit))
        else:
            kaisa.add_item(create_item_from_key(key))

    if kaisa.has_w_evolved():
        return True

    # 요청 반영: 400원 AP 보조템(증폭의 고서 가정, AP +20)까지 고려한 W 진화 가능 판정
    if include_ap_400_component:
        return (kaisa.total_ap + 20.0) >= 100.0

    return False


_KAISA_4CORE_TOP1_CACHE = None


def get_kaisa_4core_top1_build():
    global _KAISA_4CORE_TOP1_CACHE
    if _KAISA_4CORE_TOP1_CACHE is not None:
        return _KAISA_4CORE_TOP1_CACHE

    # simulation_kaisa 메인 연구 조건 기준(4코어 비교용)
    core1_candidates = ["kraken", "storm", "yuntal", "statikk"]
    core2_candidates = ["guinsoo", "terminus", "pd", "bot", "yuntal", "storm"]
    core3_candidates = ["nashor", "guinsoo", "terminus", "pd", "bot", "storm", "ie", "ldr", "kraken"]
    core4_candidates = ["ie", "ldr", "mortal", "terminus", "bot", "guinsoo", "storm", "nashor", "rabadon", "shadowflame", "kraken", "pd"]

    ctrl1_core4_combo = tuple(sorted(["kraken", "guinsoo", "nashor", "terminus"]))
    ctrl2_core4_combo = tuple(sorted(["kraken", "guinsoo", "terminus", "pd"]))
    pen_exclusive = {"terminus", "ldr", "mortal"}

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
                    pen_count = sum(1 for k in [c1, c2, c3, c4] if k in pen_exclusive)
                    if pen_count > 1:
                        continue
                    path = (c1, c2, c3, c4)
                    if path in seen_paths:
                        continue
                    seen_paths.add(path)
                    all_paths.append(path)

    rows = []
    for path in all_paths:
        dps = []
        costs = []
        for tier in range(1, 5):
            d, c, _w = simulate_kaisa_core_path(path, tier)
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
            "x": costs,
            "y": dps,
            "dpg": dpg,
            "is_control": bool(control_label),
            "control_label": control_label,
        })

    # main script와 동일한 4코어 중복 규칙 (윤탈 위치 민감)
    dedupe_weight_raw = [5.0, 3.0, 2.0, 2.0]
    for r in rows:
        r["dedupe_eff_5322"] = sum(dedupe_weight_raw[i] * r["dpg"][i] for i in range(4))

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
        if prev is None or r["dedupe_eff_5322"] > prev["dedupe_eff_5322"]:
            dedupe_best_by_key[dedupe_key] = r
    rows_dedup = list(dedupe_best_by_key.values())

    # baseline control (weighted DPG 5:3:2:2 최대)
    core_weight_raw = [5.0, 3.0, 2.0, 2.0]
    weight_sum = sum(core_weight_raw)
    core_weights = [w / weight_sum for w in core_weight_raw]
    for r in rows_dedup:
        r["weighted_dpg"] = sum(core_weights[i] * r["dpg"][i] for i in range(4))

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
        core_rel_delta_pct = []
        for i in range(4):
            base = baseline_dpg_4[i]
            ratio_pct = ((r["dpg"][i] / base) * 100.0) if base > 0 else 0.0
            core_rel_delta_pct.append(ratio_pct - 100.0)
        r["rep_score"] = sum(core_weights[i] * core_rel_delta_pct[i] for i in range(4))

    ranked = sorted(rows_dedup, key=lambda r: r["rep_score"], reverse=True)
    top1 = ranked[0]
    _KAISA_4CORE_TOP1_CACHE = {
        "path": top1["path"],
        "score": top1["rep_score"],
        "control_path": best_control["path"],
        "total_paths_tested": len(all_paths),
    }
    return _KAISA_4CORE_TOP1_CACHE


if __name__ == "__main__":
    print("\n=== Kai'Sa Build Path Power Spike (Q/W instant cast + Auto Attack, 1->2->3->4 Core + 5C extension) ===")

    core1_candidates = ["kraken", "storm", "yuntal", "statikk"]
    core2_candidates = ["guinsoo", "terminus", "pd", "bot", "yuntal", "storm"]
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
        "ldr": "LDR",
        "mortal": "Mortal",
        "rabadon": "Rabadon",
        "shadowflame": "ShadowFlame",
        "shieldbow": "Shieldbow",
    }

    # 대조군(4코어 기준)
    # CTRL 1: Krk-Gui-Nashor-Terminus + (ShadowFlame/Rabadon 중 강한 5코어)
    # CTRL 2: Krk-Gui-Terminus-PD + IE(5코어)
    ctrl1_core4_combo = tuple(sorted(["kraken", "guinsoo", "nashor", "terminus"]))
    ctrl2_core4_combo = tuple(sorted(["kraken", "guinsoo", "terminus", "pd"]))

    all_paths = []
    seen_paths = set()
    pen_exclusive = {"terminus", "ldr", "mortal"}
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
                        pen_count = sum(1 for k in [c1, c2, c3, c4, c5] if k in pen_exclusive)
                        if pen_count > 1:
                            continue

                        path_tuple = (c1, c2, c3, c4, c5)
                        if path_tuple in seen_paths:
                            continue
                        seen_paths.add(path_tuple)
                        all_paths.append(path_tuple)

    results = []
    for path in all_paths:
        dps1, cost1, w1 = simulate_kaisa_core_path(path, 1)
        dps2, cost2, w2 = simulate_kaisa_core_path(path, 2)
        dps3, cost3, w3 = simulate_kaisa_core_path(path, 3)
        dps4, cost4, w4 = simulate_kaisa_core_path(path, 4)
        dps5, cost5, w5 = simulate_kaisa_core_path(path, 5)

        combo_key = tuple(sorted(path))
        combo_key_4 = tuple(sorted(path[:4]))
        label = f"{item_short[path[0]]}-{item_short[path[1]]}-{item_short[path[2]]}-{item_short[path[3]]}-{item_short[path[4]]}"
        control_label = ""
        if combo_key_4 == ctrl1_core4_combo:
            control_label = "CTRL 1"
        elif combo_key_4 == ctrl2_core4_combo:
            control_label = "CTRL 2"

        results.append({
            "path": path,
            "combo_key": combo_key,
            "combo_key_4": combo_key_4,
            "label": label,
            "x": [cost1, cost2, cost3, cost4, cost5],
            "y": [dps1, dps2, dps3, dps4, dps5],
            "w": [w1, w2, w3, w4, w5],
            "is_control": control_label != "",
            "control_label": control_label,
        })

    # 중복 조합 처리 규칙(4코어 평가 기준)
    # 1) 윤탈 포함 + 윤탈 위치가 다르면 서로 다른 빌드로 취급
    # 2) 1이 아니면서 조합이 같고 순서만 다르면, 5:3:2:2 효율 최고 1개만 유지
    dedupe_weight_raw = [5.0, 3.0, 2.0, 2.0]

    for r in results:
        dpg = []
        for i in range(5):
            cost = r["x"][i]
            dps = r["y"][i]
            dpg.append(dps / (cost / 1000.0) if cost > 0 else 0.0)
        r["dpg"] = dpg
        r["dedupe_eff_5322"] = sum(dedupe_weight_raw[i] * dpg[i] for i in range(4))

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
            if prev is None or r["dedupe_eff_5322"] > prev["dedupe_eff_5322"]:
                dedupe_best_by_key[dedupe_key] = r
        return list(dedupe_best_by_key.values())

    # 전체 후보를 보존해 두고, 메인 표는 기존대로 전역 중복 제거 결과를 사용
    all_results = list(results)
    results = dedupe_rows(all_results)

    print(
        "\nPower Spike Paths Used "
        f"({len(results)} total, yuntal-position-sensitive + no-yuntal best-order-by-5:3:2:2)"
    )
    for idx, r in enumerate(results, start=1):
        c1, c2, c3, c4, c5 = r["path"]
        print(f"{idx:03d}. {item_short[c1]}-{item_short[c2]}-{item_short[c3]}-{item_short[c4]}-{item_short[c5]}")

    # 랭킹 기준:
    # 대조군 중 최강 빌드의 코어별 DPS/1000g를 baseline으로 두고,
    # 각 빌드의 상대 비율(부호 있는 %)을 5:3:2:2 가중 평균한 값(%)
    core_weight_raw = [5.0, 3.0, 2.0, 2.0]
    weight_sum = sum(core_weight_raw)
    core_weights = [w / weight_sum for w in core_weight_raw]

    control_results = [r for r in results if r["is_control"]]

    # CTRL 1은 ShadowFlame 버전과 Rabadon 버전 중 더 강한 것 1개만 대조군으로 유지
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
        r["rep_score"] = sum(core_weights[i] * core_rel_delta_pct[i] for i in range(4))

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

    ranked = sorted(results, key=lambda r: r["rep_score"], reverse=True)
    ranked_main = ranked
    control_build_text = {
        "CTRL 1": "Krk-Gui-Nashor-Terminus",
        "CTRL 2": "Krk-Gui-Terminus-PD",
    }

    def trim_text(text, width):
        if len(text) <= width:
            return text
        return text[:max(1, width - 3)] + "..."

    def fmt_build4(r):
        p = r["path"]
        return f"{item_short[p[0]]}-{item_short[p[1]]}-{item_short[p[2]]}-{item_short[p[3]]}"

    def fmt_core_cell(y, d):
        return f"{y:.1f}/{d:+.1f}%"

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
        f"(Rep Score: weighted avg of core (DPG ratio% - 100), 5:3:2:2)"
    )
    col_build = 34
    col_ctrl = 24
    col_core = 18
    col_opt = 26
    col_rep = 9
    header_main = (
        f"{'RK':>3} | {'BUILD(4C)':<{col_build}} | {'CONTROL':<{col_ctrl}} | "
        f"{'1C DPS/ΔDPG%':>{col_core}} | {'2C DPS/ΔDPG%':>{col_core}} | {'3C DPS/ΔDPG%':>{col_core}} | {'4C DPS/ΔDPG%':>{col_core}} | "
        f"{'5C OPT1 (DPS/Δ%)':>{col_opt}} | {'5C OPT2 (DPS/Δ%)':>{col_opt}} | {'REP%':>{col_rep}}"
    )
    header_sub = (
        f"{'RK':>3} | {'BUILD(4C)':<{col_build}} | {'CONTROL':<{col_ctrl}} | "
        f"{'1C DPS/ΔDPG%':>{col_core}} | {'2C DPS/ΔDPG%':>{col_core}} | {'3C DPS/ΔDPG%':>{col_core}} | {'4C DPS/ΔDPG%':>{col_core}} | "
        f"{'REP%':>{col_rep}}"
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
            f"{r['rep_score']:>{col_rep}.2f}"
        )

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
            f"REP {requested_nashor_row['rep_score']:.2f}"
        )

    # 별도 표: 4코어 시점 W 진화 가능한 빌드(AP 100+ 또는 400g AP 보조템으로 도달 가능)
    w_evo_rows = [r for r in ranked if is_kaisa_w_evolved_at_core(r["path"], 4, include_ap_400_component=True)]
    if w_evo_rows:
        w_top_n = min(30, len(w_evo_rows))
        print(
            f"\nW-Evolved at 4-Core Ranking (Top {w_top_n}, AP>=100 at 4C or +400g AP component, same REP metric)"
        )
        print(header_sub)
        print("-" * len(header_sub))
        for rank, r in enumerate(w_evo_rows[:w_top_n], start=1):
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
                f"{r['rep_score']:>{col_rep}.2f}"
            )

    # 별도 표: 1코어 크라켄 고정 랭킹 (그래프 없음)
    kraken_rows = [r for r in ranked if r["path"][0] == "kraken"]
    if kraken_rows:
        kraken_top_n = min(30, len(kraken_rows))
        print(
            f"\nKraken-First Ranking (Top {kraken_top_n}, no graph, same REP metric)"
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
                f"{r['rep_score']:>{col_rep}.2f}"
            )

    # 별도 표: 유령무희가 2코어 또는 3코어에 포함된 빌드
    # PD 2/3코어 표는 "PD 2/3 포함 후보를 먼저 만든 뒤" 그 집합 내부에서 중복 제거
    pd_23_pool = [r for r in all_results if (r["path"][1] == "pd" or r["path"][2] == "pd")]
    pd_23_rows = sorted(dedupe_rows(pd_23_pool), key=lambda r: r["rep_score"], reverse=True)
    if pd_23_rows:
        pd_top_n = min(30, len(pd_23_rows))
        print(
            f"\nPD in Core2/Core3 Ranking (Top {pd_top_n}, no graph, same REP metric)"
        )
        print(header_sub)
        print("-" * len(header_sub))
        for rank, r in enumerate(pd_23_rows[:pd_top_n], start=1):
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
                f"{r['rep_score']:>{col_rep}.2f}"
            )

    # 그래프: 4코어 기준 상위 5개 + 대조군 2개, 각 빌드의 5코어 상위 2옵션 분기
    top5_non_control = [r for r in ranked if not r["is_control"]][:5]

    control_best_by_label = {}
    for r in control_results:
        key = r["control_label"]
        if key not in control_best_by_label or r["rep_score"] > control_best_by_label[key]["rep_score"]:
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
                label=f"Top{i+1} {r['label']} (Rep {r['rep_score']:.2f}%)"
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
                label=f"Top{i+1} {label4}+{item_short[o['item']]} (Rep {r['rep_score']:.2f}%)"
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
                label=f"{r['control_label']}({ctrl_desc}) {r['label']} (Rep {r['rep_score']:.2f}%)"
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
                label=f"{r['control_label']}({ctrl_desc}) +{item_short[o['item']]} (Rep {r['rep_score']:.2f}%)"
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
