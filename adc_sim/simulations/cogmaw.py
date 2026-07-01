from adc_sim.champion import CogMaw, Target
import matplotlib.pyplot as plt
from adc_sim.runes import LethalTempo, PressTheAttack, CutDown
from adc_sim.engine import run_simulation
from adc_sim.data.items_registry import create_item_from_key
from adc_sim.data.items_data import ADC_PACKAGES
from adc_sim.settings import CORE_WEIGHTS_RAW, CORE_WEIGHTS_LABEL

# 코어 단계별 고정 타겟 (Ashe/KaiSa 시뮬과 동일)
CORE_TARGET_STATS = {
    1: {"hp": 1700, "armor": 50, "mr": 25},
    2: {"hp": 1900, "armor": 70, "mr": 30},
    3: {"hp": 2400, "armor": 100, "mr": 50},
    4: {"hp": 2600, "armor": 120, "mr": 70},
    5: {"hp": 3000, "armor": 150, "mr": 90},
}
CORE_COGMAW_LEVELS = {1: {"level": 9}, 2: {"level": 11}, 3: {"level": 13},
                      4: {"level": 15}, 5: {"level": 17}}


def build_target_for_core(core_tier):
    s = CORE_TARGET_STATS[core_tier]
    return Target(hp=s["hp"], armor=s["armor"], magic_resist=s["mr"],
                  bonus_hp=max(0, s["hp"] - 1500))


def _skill_levels_for_core(core_tier):
    """코어별 스킬레벨 가정: W 선마, 그 다음 Q. R은 6렙부터(tier1=lvl9 → r 가능)."""
    # 단순화: q/w/e는 코어가 오를수록 최대로, r은 레벨 기반.
    lvl = CORE_COGMAW_LEVELS[core_tier]["level"]
    w = min(5, max(1, core_tier + 1))
    q = min(5, max(1, core_tier))
    e = min(5, max(1, core_tier - 1)) if core_tier > 1 else 1
    r = 1 if lvl < 11 else (2 if lvl < 16 else 3)
    return q, w, e, r


def simulate_cogmaw_core_path(full_path, core_tier, doran_key="doranblade",
                              boots_key="berserker", rune_as_bonus=0.0, keystone_cls=LethalTempo):
    """Cog'Maw DPS + total gold for a core timing. W/Q/E/R 쿨마다 시전(마나 바운드).
    keystone_cls: 키스톤 룬 클래스(LethalTempo|PressTheAttack). 보조룬은 CutDown 고정."""
    target = build_target_for_core(core_tier)
    lvl = CORE_COGMAW_LEVELS[core_tier]["level"]
    q, w, e, r = _skill_levels_for_core(core_tier)
    cog = CogMaw(level=lvl, q_level=q, w_level=w, e_level=e, r_level=r)
    cog.set_rune(keystone_cls())
    cog.set_sub_rune(CutDown())

    items = ([create_item_from_key(doran_key)] if doran_key else []) + [create_item_from_key(boots_key)]
    for key in full_path[:core_tier]:
        items.append(create_item_from_key(key))
    total_cost = 0
    for it in items:
        total_cost += it.cost
        cog.add_item(it)
    cog.bonus_as_percent += rune_as_bonus

    # W를 t=0에 시전(버프 시작), 이후 Q/E/R + W 재시전 모두 쿨마다 자동.
    skill_plan = {
        "manual_casts": [(0.0, "w")],
        "auto_cast": {"q": True, "w": True, "e": True, "r": True},
        "auto_order": ["w", "q", "e", "r"],
    }
    _, dps, _ = run_simulation(cog, target, verbose=False, skill_plan=skill_plan, respawn_to_full_kills=2)
    return dps, total_cost


# 컨트롤(베이스라인) = 실전 메타 빌드 — 모든 빌드 RelDPG 를 '메타 대비'로 측정. 풀에 존재해야 함.
CONTROL_PATH = ("guinsoo", "navori", "terminus", "wit")
_COGMAW_TOP1_CACHE = {}  # (keystone_cls, rank_by) → top1 dict (룬·랭킹기준별 캐시)


def get_cogmaw_4core_top1_build(keystone_cls=LethalTempo, rank_by="dpg"):
    """Return the ranked 4-core Cog'Maw top1 build (주어진 keystone 룬) with control metadata.

    Control = CONTROL_PATH (실전 메타 빌드 guinsoo-navori-terminus-wit). Raises RuntimeError
    if the control build is absent from the search space. keystone_cls 별로 캐시한다.
    [H-KOG-6] yuntal dedup uses simple sorted-combo (no position sensitivity) because
    cogmaw v1 makes no yuntal-crit distinction per build position.
    """
    if (keystone_cls, rank_by) in _COGMAW_TOP1_CACHE:
        return _COGMAW_TOP1_CACHE[(keystone_cls, rank_by)]

    core1_candidates = ["guinsoo", "kraken", "nashor", "terminus", "bot", "rfc", "statikk", "storm", "pd", "ie", "yuntal", "shadowflame", "dawn", "navori", "wit"]
    core2_candidates = ["guinsoo", "kraken", "nashor", "terminus", "bot", "rfc", "statikk", "storm", "pd", "ie", "yuntal", "shadowflame", "void", "dawn", "navori", "wit"]
    core3_candidates = ["guinsoo", "nashor", "terminus", "bot", "kraken", "rfc", "pd", "ie", "ldr", "rabadon", "shadowflame", "void", "dawn", "navori", "wit"]
    core4_candidates = ["nashor", "rabadon", "shadowflame", "ie", "ldr", "mortal", "terminus", "bot", "guinsoo", "kraken", "pd", "void", "dawn", "navori", "wit"]
    pen_exclusive = {"terminus", "ldr", "mortal"}
    ctrl_combo = tuple(sorted(CONTROL_PATH))

    all_paths = []
    seen_paths = set()
    for c1 in core1_candidates:
        for c2 in core2_candidates:
            if len({c1, c2}) < 2:
                continue
            for c3 in core3_candidates:
                for c4 in core4_candidates:
                    if len({c1, c2, c3, c4}) < 4:
                        continue
                    if sum(1 for k in (c1, c2, c3, c4) if k in pen_exclusive) > 1:
                        continue
                    path = (c1, c2, c3, c4)
                    if path in seen_paths:
                        continue
                    seen_paths.add(path)
                    all_paths.append(path)

    dedupe_weight_raw = list(CORE_WEIGHTS_RAW)
    core_weight_raw = list(CORE_WEIGHTS_RAW)
    weight_sum = sum(core_weight_raw)
    core_weights = [w / weight_sum for w in core_weight_raw]

    rows = []
    for path in all_paths:
        for pkg in ADC_PACKAGES:
            kw = dict(doran_key=pkg["doran"], boots_key=pkg["boots"], rune_as_bonus=pkg["rune_as"], keystone_cls=keystone_cls)
            dps_list, cost_list = [], []
            for tier in range(1, 5):
                d, c = simulate_cogmaw_core_path(path, tier, **kw)
                dps_list.append(d)
                cost_list.append(c)
            dpg = [dps_list[i] / (cost_list[i] / 1000.0) if cost_list[i] > 0 else 0.0 for i in range(4)]
            rows.append({
                "path": path,
                "doran": pkg["doran"],
                "boots": pkg["boots"],
                "rune_as": pkg["rune_as"],
                "pkg_label": pkg["label"],
                "x": cost_list,
                "y": dps_list,
                "dpg": dpg,
                "is_control": tuple(sorted(path)) == ctrl_combo,
                "dedupe_eff": sum(dedupe_weight_raw[i] * dpg[i] for i in range(4)),
            })

    # dedup by sorted combo — [H-KOG-6] no yuntal-position sensitivity in v1
    dedupe_best = {}
    for r in rows:
        key = tuple(sorted(r["path"]))
        if key not in dedupe_best or r["dedupe_eff"] > dedupe_best[key]["dedupe_eff"]:
            dedupe_best[key] = r
    rows_dedup = list(dedupe_best.values())

    # fix control to canonical CONTROL_PATH ordering (same house rule as kaisa)
    rows_dedup = [r for r in rows_dedup if not r["is_control"]]
    ctrl_cands = [r for r in rows if tuple(r["path"]) == CONTROL_PATH]
    if ctrl_cands:
        rows_dedup.append(max(ctrl_cands, key=lambda r: r["dedupe_eff"]))

    for r in rows_dedup:
        r["weighted_dpg"] = sum(core_weights[i] * r["dpg"][i] for i in range(4))
        r["weighted_dps"] = sum(core_weights[i] * r["y"][i] for i in range(4))

    control_rows = [r for r in rows_dedup if r["is_control"]]
    if not control_rows:
        raise RuntimeError(
            f"Control build {CONTROL_PATH} not found in search space. "
            "Check that all 4 control items appear in candidate pools."
        )
    best_control = max(control_rows, key=lambda r: r["weighted_dpg"])
    baseline_dpg_4 = best_control["dpg"][:4]

    for r in rows_dedup:
        core_rel_pct = [
            (r["dpg"][i] / baseline_dpg_4[i] * 100.0 if baseline_dpg_4[i] > 0 else 0.0)
            for i in range(4)
        ]
        r["rel_dpg_score"] = sum(core_weights[i] * core_rel_pct[i] for i in range(4))

    sort_key = (lambda r: r["weighted_dps"]) if rank_by == "dps" else (lambda r: r["rel_dpg_score"])
    ranked = sorted(rows_dedup, key=sort_key, reverse=True)
    top1 = ranked[0]
    result = {
        "path": top1["path"],
        "doran": top1["doran"],
        "boots": top1["boots"],
        "rune_as": top1["rune_as"],
        "pkg_label": top1["pkg_label"],
        "score": top1["rel_dpg_score"],
        "weighted_dpg": top1["weighted_dpg"],          # 절대 파워(룬 간 비교용)
        "weighted_dps": top1["weighted_dps"],          # 절대 DPS 가중합(rank_by="dps" 선택 기준)
        "keystone_cls": keystone_cls,
        "control_path": best_control["path"],
        "control_doran": best_control["doran"],
        "control_boots": best_control["boots"],
        "control_rune_as": best_control["rune_as"],
        "control_pkg": best_control["pkg_label"],
        "control_weighted_dpg": best_control["weighted_dpg"],
        "total_paths_tested": len(all_paths),
    }
    _COGMAW_TOP1_CACHE[(keystone_cls, rank_by)] = result
    return result


def build_cogmaw_core_report_meta(full_path, core_tier):
    """Build serializable metadata for a Cog'Maw report row (mirrors kaisa variant)."""
    active_path = tuple(full_path[:core_tier])
    return {
        "champion": "CogMaw",
        "core_tier": core_tier,
        "full_path": list(full_path),
        "active_path": list(active_path),
        "build": "-".join(full_path),
        "active_build": "-".join(active_path),
    }


def get_cogmaw_powercompare_builds():
    """power_compare 연동용 두 빌드 (best, meta) 반환.

    - best: 룬 무관 가장 강한 빌드 — LethalTempo·PressTheAttack 각각 DPS 1:1:1:1 top1(rank_by="dps")
      중 절대 weighted-DPS 가 높은 (빌드, 룬). power_compare 가 DPS 기준 비교라 DPS 로 선택.
    - meta: 실전 메타 빌드(CONTROL_PATH=guinsoo-navori-terminus-wit) under 치속(LethalTempo),
      최적 패키지(= LT 랭킹의 control 행).
    각 dict: path / keystone_cls / doran / boots / rune_as / pkg_label / rune_label / weighted_dpg.
    주의: LT·PtA 두 룬 전수 랭킹을 돌리므로 느리다(룬별 캐시됨).
    """
    lt = get_cogmaw_4core_top1_build(LethalTempo, rank_by="dps")
    pta = get_cogmaw_4core_top1_build(PressTheAttack, rank_by="dps")
    src = lt if lt["weighted_dps"] >= pta["weighted_dps"] else pta
    best = {
        "path": src["path"], "keystone_cls": src["keystone_cls"],
        "doran": src["doran"], "boots": src["boots"], "rune_as": src["rune_as"],
        "pkg_label": src["pkg_label"],
        "rune_label": "LT" if src["keystone_cls"] is LethalTempo else "PtA",
        "weighted_dps": src["weighted_dps"],
    }
    meta = {  # LT 결과의 control = 메타 빌드(최적 패키지)
        "path": lt["control_path"], "keystone_cls": LethalTempo,
        "doran": lt["control_doran"], "boots": lt["control_boots"], "rune_as": lt["control_rune_as"],
        "pkg_label": lt["control_pkg"], "rune_label": "LT",
        "weighted_dpg": lt["control_weighted_dpg"],
    }
    return best, meta


def _run_cogmaw_ranking(keystone_cls, keystone_label, all_paths, item_short, ctrl_combo):
    """주어진 keystone(룬)으로 전 빌드 시뮬→dedup→1:1:1:1 rel-DPG 랭킹→표 출력. ranked 반환.
    룬-2배: __main__ 이 치명적 속도·집중공격 두 번 호출. 보조룬은 CutDown 고정(simulate 내부)."""
    dedupe_weight_raw = list(CORE_WEIGHTS_RAW)
    core_weight_raw = list(CORE_WEIGHTS_RAW)
    weight_sum = sum(core_weight_raw)
    core_weights = [w / weight_sum for w in core_weight_raw]

    rows = []
    for path in all_paths:
        for pkg in ADC_PACKAGES:
            kw = dict(doran_key=pkg["doran"], boots_key=pkg["boots"],
                      rune_as_bonus=pkg["rune_as"], keystone_cls=keystone_cls)
            dps_list, cost_list = [], []
            for tier in range(1, 5):
                d, c = simulate_cogmaw_core_path(path, tier, **kw)
                dps_list.append(d)
                cost_list.append(c)
            dpg = [dps_list[i] / (cost_list[i] / 1000.0) if cost_list[i] > 0 else 0.0 for i in range(4)]
            rows.append({
                "path": path,
                "doran": pkg["doran"],
                "boots": pkg["boots"],
                "rune_as": pkg["rune_as"],
                "pkg_label": pkg["label"],
                "x": cost_list,
                "y": dps_list,
                "dpg": dpg,
                "is_control": tuple(sorted(path)) == ctrl_combo,
                "dedupe_eff": sum(dedupe_weight_raw[i] * dpg[i] for i in range(4)),
            })

    # dedup by sorted combo — [H-KOG-6] no yuntal-position sensitivity in v1
    dedupe_best = {}
    for r in rows:
        key = tuple(sorted(r["path"]))
        if key not in dedupe_best or r["dedupe_eff"] > dedupe_best[key]["dedupe_eff"]:
            dedupe_best[key] = r
    rows_dedup = list(dedupe_best.values())

    # fix control to canonical ordering
    rows_dedup = [r for r in rows_dedup if not r["is_control"]]
    ctrl_cands = [r for r in rows if tuple(r["path"]) == CONTROL_PATH]
    if ctrl_cands:
        rows_dedup.append(max(ctrl_cands, key=lambda r: r["dedupe_eff"]))

    print(f"\n{'=' * 28}  RUNE: {keystone_label}  {'=' * 28}")
    print(f"Builds after dedup (best-order-by-{CORE_WEIGHTS_LABEL}, control fixed to canonical): {len(rows_dedup)}")

    for r in rows_dedup:
        r["weighted_dpg"] = sum(core_weights[i] * r["dpg"][i] for i in range(4))

    control_rows = [r for r in rows_dedup if r["is_control"]]
    if not control_rows:
        raise RuntimeError(f"Control build {CONTROL_PATH} not found in search space.")
    best_control = max(control_rows, key=lambda r: r["weighted_dpg"])
    baseline_dpg_4 = best_control["dpg"][:4]

    print(
        f"Baseline Control: {'-'.join(best_control['path'])} [{best_control['pkg_label']}] "
        f"| Weighted DPG {best_control['weighted_dpg']:.2f}"
    )

    for r in rows_dedup:
        core_rel_pct = [
            (r["dpg"][i] / baseline_dpg_4[i] * 100.0 if baseline_dpg_4[i] > 0 else 0.0)
            for i in range(4)
        ]
        r["core_rel_delta_pct_4"] = [p - 100.0 for p in core_rel_pct]
        r["rel_dpg_score"] = sum(core_weights[i] * core_rel_pct[i] for i in range(4))

    ranked = sorted(rows_dedup, key=lambda r: r["rel_dpg_score"], reverse=True)

    top_n = min(30, len(ranked))
    top_rows = ranked[:top_n]
    top_row_paths = {tuple(r["path"]) for r in top_rows}
    extra_controls = [r for r in control_rows if tuple(r["path"]) not in top_row_paths]
    output_rows = top_rows + extra_controls

    def trim_text(text, width):
        return text if len(text) <= width else text[:max(1, width - 3)] + "..."

    def fmt_build4(r):
        p = r["path"]
        s = item_short
        return f"{s.get(p[0], p[0])}-{s.get(p[1], p[1])}-{s.get(p[2], p[2])}-{s.get(p[3], p[3])} [{r['pkg_label']}]"

    def fmt_core_cell(dps, delta):
        return f"{dps:.1f}/{delta:+.1f}%"

    col_build = 34
    col_core = 18
    col_rep = 9
    header = (
        f"{'RK':>3} | {'BUILD(4C)':<{col_build}} | {'CTRL':>6} | "
        f"{'1C DPS/ΔDPG%':>{col_core}} | {'2C DPS/ΔDPG%':>{col_core}} | "
        f"{'3C DPS/ΔDPG%':>{col_core}} | {'4C DPS/ΔDPG%':>{col_core}} | "
        f"{'RelDPG':>{col_rep}}"
    )
    print(
        f"\nTop {len(output_rows)} Rows: Top {top_n} + Controls "
        f"(RelDPG = control-normalised weighted DPG ×100, {CORE_WEIGHTS_LABEL})"
    )
    print(header)
    print("-" * len(header))

    for rank, r in enumerate(output_rows, start=1):
        y1, y2, y3, y4 = r["y"][:4]
        d1, d2, d3, d4 = r["core_rel_delta_pct_4"]
        ctrl_tag = "[CTRL]" if r["is_control"] else ""
        label = trim_text(fmt_build4(r), col_build)
        print(
            f"{rank:>3} | {label:<{col_build}} | {ctrl_tag:>6} | "
            f"{fmt_core_cell(y1,d1):>{col_core}} | {fmt_core_cell(y2,d2):>{col_core}} | "
            f"{fmt_core_cell(y3,d3):>{col_core}} | {fmt_core_cell(y4,d4):>{col_core}} | "
            f"{r['rel_dpg_score']:>{col_rep}.2f}"
        )

    return ranked


if __name__ == "__main__":
    print("\n=== Cog'Maw Build Path Power Spike (W/Q/E/R auto-cast, 1→4 Core) ===")

    core1_candidates = ["guinsoo", "kraken", "nashor", "terminus", "bot", "rfc", "statikk", "storm", "pd", "ie", "yuntal", "shadowflame", "dawn", "navori", "wit"]
    core2_candidates = ["guinsoo", "kraken", "nashor", "terminus", "bot", "rfc", "statikk", "storm", "pd", "ie", "yuntal", "shadowflame", "void", "dawn", "navori", "wit"]
    core3_candidates = ["guinsoo", "nashor", "terminus", "bot", "kraken", "rfc", "pd", "ie", "ldr", "rabadon", "shadowflame", "void", "dawn", "navori", "wit"]
    core4_candidates = ["nashor", "rabadon", "shadowflame", "ie", "ldr", "mortal", "terminus", "bot", "guinsoo", "kraken", "pd", "void", "dawn", "navori", "wit"]
    pen_exclusive = {"terminus", "ldr", "mortal"}
    ctrl_combo = tuple(sorted(CONTROL_PATH))

    item_short = {
        "guinsoo": "Gui", "kraken": "Krk", "nashor": "Nashor", "terminus": "Terminus",
        "bot": "BotRK", "rfc": "RFC", "statikk": "Statikk", "storm": "Storm",
        "pd": "PD", "ie": "IE", "yuntal": "Yun", "ldr": "LDR",
        "rabadon": "Rabadon", "shadowflame": "ShadowFlame", "mortal": "Mortal", "void": "Void", "dawn": "D&D",
        "navori": "Navori", "wit": "Wit's",
    }

    all_paths = []
    seen_paths = set()
    for c1 in core1_candidates:
        for c2 in core2_candidates:
            if len({c1, c2}) < 2:
                continue
            for c3 in core3_candidates:
                for c4 in core4_candidates:
                    if len({c1, c2, c3, c4}) < 4:
                        continue
                    if sum(1 for k in (c1, c2, c3, c4) if k in pen_exclusive) > 1:
                        continue
                    path = (c1, c2, c3, c4)
                    if path in seen_paths:
                        continue
                    seen_paths.add(path)
                    all_paths.append(path)

    print(f"\nTotal unique paths in search space: {len(all_paths)}")

    keystones = [(LethalTempo, "치명적 속도 (Lethal Tempo)"),
                 (PressTheAttack, "집중공격 (Press the Attack)")]
    ranked_by_rune = []
    for _ks, _klabel in keystones:
        ranked_by_rune.append(_run_cogmaw_ranking(_ks, _klabel, all_paths, item_short, ctrl_combo))

    # 그래프는 첫 룬(치명적 속도) 기준 1장
    ranked = ranked_by_rune[0]
    control_rows = [r for r in ranked if r["is_control"]]

    # ── Graph: Top 5 non-control + Control, 4-core DPS curves ──
    top5_non_ctrl = [r for r in ranked if not r["is_control"]][:5]

    plt.figure(figsize=(12, 8))
    label_points_by_core = {i: [] for i in range(4)}

    def collect_labels(xs, ys, color, name):
        for ci, (xv, yv) in enumerate(zip(xs, ys)):
            label_points_by_core[ci].append({"x": xv, "y": yv, "color": color, "text": f"{int(round(yv))}", "series": name})

    top_colors = ["#E4572E", "#F3A712", "#54A24B", "#4C78A8", "#B279A2"]
    for i, r in enumerate(top5_non_ctrl):
        color = top_colors[i % len(top_colors)]
        p = r["path"]
        lbl = (
            f"Top{i+1} {item_short.get(p[0], p[0])}-{item_short.get(p[1], p[1])}-{item_short.get(p[2], p[2])}-{item_short.get(p[3], p[3])}"
            f" [{r['pkg_label']}] (RelDPG {r['rel_dpg_score']:.2f})"
        )
        plt.plot(r["x"][:4], r["y"][:4], color=color, linewidth=2.4, marker="D", markersize=6, label=lbl)
        collect_labels(r["x"][:4], r["y"][:4], color, f"Top{i+1}")

    ctrl_colors = ["#111111"]
    for i, r in enumerate(control_rows):
        color = ctrl_colors[i % len(ctrl_colors)]
        p = r["path"]
        lbl = (
            f"[CTRL] {item_short.get(p[0], p[0])}-{item_short.get(p[1], p[1])}-{item_short.get(p[2], p[2])}-{item_short.get(p[3], p[3])}"
            f" [{r['pkg_label']}] (RelDPG {r['rel_dpg_score']:.2f})"
        )
        plt.plot(r["x"][:4], r["y"][:4], color=color, linewidth=2.8, marker="o", markersize=7, linestyle="--", label=lbl)
        collect_labels(r["x"][:4], r["y"][:4], color, "[CTRL]")

    # annotate DPS values at each core timing
    for core_idx, points in label_points_by_core.items():
        if not points:
            continue
        points_sorted = sorted(points, key=lambda p: p["y"])
        y_min = points_sorted[0]["y"]
        y_max = points_sorted[-1]["y"]
        spread = max(80.0, y_max - y_min)
        min_gap = max(22.0, spread * 0.055)
        adjusted_y = []
        for pt in points_sorted:
            if not adjusted_y:
                adjusted_y.append(pt["y"])
            else:
                adjusted_y.append(max(pt["y"], adjusted_y[-1] + min_gap))
        for idx in range(len(adjusted_y) - 2, -1, -1):
            adjusted_y[idx] = min(adjusted_y[idx], adjusted_y[idx + 1] - min_gap)
        x_dir = -1 if core_idx in (0, 2) else 1
        x_off = 22 if x_dir > 0 else -22
        for pt, y_adj in zip(points_sorted, adjusted_y):
            plt.annotate(
                pt["text"],
                xy=(pt["x"], pt["y"]),
                xytext=(x_off, y_adj - pt["y"]),
                textcoords="offset points",
                ha="left" if x_dir > 0 else "right",
                va="center",
                fontsize=6.8,
                color=pt["color"],
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=pt["color"], alpha=0.82, lw=0.6),
                arrowprops=dict(arrowstyle="-", color=pt["color"], alpha=0.35, lw=0.6),
            )

    plt.title("Cog'Maw Power Spike: 4-Core Ranked Top5 + Control (DPS Labels)")
    plt.xlabel("Total Gold at Core Timing")
    plt.ylabel("DPS (AA + Skills, W/Q/E/R auto-cast)")
    plt.grid(True, alpha=0.3)
    plt.legend(loc="best", fontsize=8)
    plt.tight_layout()
    plt.show()
