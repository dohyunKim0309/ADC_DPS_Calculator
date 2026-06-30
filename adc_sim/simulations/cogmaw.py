from adc_sim.champion import CogMaw, Target
import matplotlib.pyplot as plt
from adc_sim.runes import LethalTempo, CutDown
from adc_sim.engine import run_simulation
from adc_sim.data.items_registry import create_item_from_key
from adc_sim.data.items_data import ADC_PACKAGES

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
                              boots_key="berserker", rune_as_bonus=0.0):
    """Cog'Maw DPS + total gold for a core timing. W/Q/E/R 쿨마다 시전(마나 바운드)."""
    target = build_target_for_core(core_tier)
    lvl = CORE_COGMAW_LEVELS[core_tier]["level"]
    q, w, e, r = _skill_levels_for_core(core_tier)
    cog = CogMaw(level=lvl, q_level=q, w_level=w, e_level=e, r_level=r)
    cog.set_rune(LethalTempo())
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
    _, dps, _ = run_simulation(cog, target, verbose=False, skill_plan=skill_plan)
    return dps, total_cost


CONTROL_PATH = ("kraken", "guinsoo", "nashor", "terminus")
_COGMAW_4CORE_TOP1_CACHE = None


def get_cogmaw_4core_top1_build():
    """Return the ranked 4-core Cog'Maw top1 build with control metadata.

    Control = CONTROL_PATH (kraken-guinsoo-nashor-terminus). Raises RuntimeError if the
    control build is absent from the search space.
    [H-KOG-6] yuntal dedup uses simple sorted-combo (no position sensitivity) because
    cogmaw v1 makes no yuntal-crit distinction per build position.
    """
    global _COGMAW_4CORE_TOP1_CACHE
    if _COGMAW_4CORE_TOP1_CACHE is not None:
        return _COGMAW_4CORE_TOP1_CACHE

    core1_candidates = ["guinsoo", "kraken", "nashor", "terminus", "bot", "rfc", "statikk", "storm", "pd", "ie", "yuntal"]
    core2_candidates = ["guinsoo", "kraken", "nashor", "terminus", "bot", "rfc", "statikk", "storm", "pd", "ie", "yuntal"]
    core3_candidates = ["guinsoo", "nashor", "terminus", "bot", "kraken", "rfc", "pd", "ie", "ldr", "rabadon"]
    core4_candidates = ["nashor", "rabadon", "shadowflame", "ie", "ldr", "mortal", "terminus", "bot", "guinsoo", "kraken", "pd"]
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

    dedupe_weight_raw = [5.0, 4.0, 3.0, 3.0]
    core_weight_raw = [5.0, 4.0, 3.0, 3.0]
    weight_sum = sum(core_weight_raw)
    core_weights = [w / weight_sum for w in core_weight_raw]

    rows = []
    for path in all_paths:
        for pkg in ADC_PACKAGES:
            kw = dict(doran_key=pkg["doran"], boots_key=pkg["boots"], rune_as_bonus=pkg["rune_as"])
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

    ranked = sorted(rows_dedup, key=lambda r: r["rel_dpg_score"], reverse=True)
    top1 = ranked[0]
    _COGMAW_4CORE_TOP1_CACHE = {
        "path": top1["path"],
        "doran": top1["doran"],
        "boots": top1["boots"],
        "rune_as": top1["rune_as"],
        "pkg_label": top1["pkg_label"],
        "score": top1["rel_dpg_score"],
        "control_path": best_control["path"],
        "control_pkg": best_control["pkg_label"],
        "total_paths_tested": len(all_paths),
    }
    return _COGMAW_4CORE_TOP1_CACHE


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


if __name__ == "__main__":
    print("\n=== Cog'Maw Build Path Power Spike (W/Q/E/R auto-cast, 1→4 Core) ===")

    core1_candidates = ["guinsoo", "kraken", "nashor", "terminus", "bot", "rfc", "statikk", "storm", "pd", "ie", "yuntal"]
    core2_candidates = ["guinsoo", "kraken", "nashor", "terminus", "bot", "rfc", "statikk", "storm", "pd", "ie", "yuntal"]
    core3_candidates = ["guinsoo", "nashor", "terminus", "bot", "kraken", "rfc", "pd", "ie", "ldr", "rabadon"]
    core4_candidates = ["nashor", "rabadon", "shadowflame", "ie", "ldr", "mortal", "terminus", "bot", "guinsoo", "kraken", "pd"]
    pen_exclusive = {"terminus", "ldr", "mortal"}
    ctrl_combo = tuple(sorted(CONTROL_PATH))

    item_short = {
        "guinsoo": "Gui", "kraken": "Krk", "nashor": "Nashor", "terminus": "Terminus",
        "bot": "BotRK", "rfc": "RFC", "statikk": "Statikk", "storm": "Storm",
        "pd": "PD", "ie": "IE", "yuntal": "Yun", "ldr": "LDR",
        "rabadon": "Rabadon", "shadowflame": "ShadowFlame", "mortal": "Mortal",
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

    dedupe_weight_raw = [5.0, 4.0, 3.0, 3.0]
    core_weight_raw = [5.0, 4.0, 3.0, 3.0]
    weight_sum = sum(core_weight_raw)
    core_weights = [w / weight_sum for w in core_weight_raw]

    rows = []
    for path in all_paths:
        for pkg in ADC_PACKAGES:
            kw = dict(doran_key=pkg["doran"], boots_key=pkg["boots"], rune_as_bonus=pkg["rune_as"])
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

    print(
        f"Builds after dedup (best-order-by-5:4:3:3, control fixed to canonical): {len(rows_dedup)}"
    )

    for r in rows_dedup:
        r["weighted_dpg"] = sum(core_weights[i] * r["dpg"][i] for i in range(4))

    control_rows = [r for r in rows_dedup if r["is_control"]]
    if not control_rows:
        raise RuntimeError(f"Control build {CONTROL_PATH} not found in search space.")
    best_control = max(control_rows, key=lambda r: r["weighted_dpg"])
    baseline_dpg_4 = best_control["dpg"][:4]

    print(
        f"\nBaseline Control: {'-'.join(best_control['path'])} [{best_control['pkg_label']}] "
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
        return f"{s[p[0]]}-{s[p[1]]}-{s[p[2]]}-{s[p[3]]} [{r['pkg_label']}]"

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
        f"(RelDPG = control-normalised weighted DPG ×100, 5:4:3:3)"
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
            f"Top{i+1} {item_short[p[0]]}-{item_short[p[1]]}-{item_short[p[2]]}-{item_short[p[3]]}"
            f" [{r['pkg_label']}] (RelDPG {r['rel_dpg_score']:.2f})"
        )
        plt.plot(r["x"][:4], r["y"][:4], color=color, linewidth=2.4, marker="D", markersize=6, label=lbl)
        collect_labels(r["x"][:4], r["y"][:4], color, f"Top{i+1}")

    ctrl_colors = ["#111111"]
    for i, r in enumerate(control_rows):
        color = ctrl_colors[i % len(ctrl_colors)]
        p = r["path"]
        lbl = (
            f"[CTRL] {item_short[p[0]]}-{item_short[p[1]]}-{item_short[p[2]]}-{item_short[p[3]]}"
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
