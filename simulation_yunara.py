import matplotlib.pyplot as plt

from simulation_ashe import (
    simulate_yunara_core_path,
    _build_ashe_4core_all_paths,
)


ITEM_SHORT = {
    "kraken": "Krk",
    "yuntal25": "Yun",
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
}

CONTROL_COMBO = tuple(sorted(("kraken", "pd", "ie", "ldr")))
CONTROL_LABEL = "Control Krk-PD-IE-LDR"
CORE_WEIGHTS_RAW = [5.0, 4.0, 3.0, 3.0]
CORE_WEIGHTS = [w / sum(CORE_WEIGHTS_RAW) for w in CORE_WEIGHTS_RAW]
_YUNARA_4CORE_TOP1_CACHE = None


def _path_label(path):
    return "-".join(ITEM_SHORT[k] for k in path)


def rank_yunara_4core_paths():
    all_paths = _build_ashe_4core_all_paths()

    results = []
    for c1, c2, c3, c4 in all_paths:
        dps1, cost1 = simulate_yunara_core_path([c1], 1)
        dps2, cost2 = simulate_yunara_core_path([c1, c2], 2)
        dps3, cost3 = simulate_yunara_core_path([c1, c2, c3], 3)
        dps4, cost4 = simulate_yunara_core_path([c1, c2, c3, c4], 4)
        path = (c1, c2, c3, c4)
        results.append({
            "path": path,
            "label": _path_label(path),
            "x": [cost1, cost2, cost3, cost4],
            "y": [dps1, dps2, dps3, dps4],
            "is_control": tuple(sorted(path)) == CONTROL_COMBO,
            "control_label": CONTROL_LABEL if tuple(sorted(path)) == CONTROL_COMBO else "",
        })

    control_candidates = [r for r in results if r["is_control"]]
    if not control_candidates:
        raise RuntimeError("Control build not found: Krk-PD-IE-LDR")
    best_control = control_candidates[0]
    ctrl_dps = best_control["y"]
    ctrl_costs = best_control["x"]
    ctrl_dpg = [
        ctrl_dps[i] / (ctrl_costs[i] / 1000.0) if ctrl_costs[i] > 0 else 0.0
        for i in range(4)
    ]

    for r in results:
        row_dps = r["y"]
        row_costs = r["x"]
        row_dpg = [
            row_dps[i] / (row_costs[i] / 1000.0) if row_costs[i] > 0 else 0.0
            for i in range(4)
        ]
        rel = [(row_dpg[i] / ctrl_dpg[i]) if ctrl_dpg[i] > 0 else 0.0 for i in range(4)]
        r["rel_dpg_score"] = sum(CORE_WEIGHTS[i] * rel[i] for i in range(4)) * 100.0

    # same 4-core item set, different order -> keep best scored path only
    combo_best = {}
    for r in results:
        combo_key = tuple(sorted(r["path"]))
        prev = combo_best.get(combo_key)
        if prev is None or r["rel_dpg_score"] > prev["rel_dpg_score"]:
            combo_best[combo_key] = r

    deduped = list(combo_best.values())
    deduped.sort(key=lambda x: x["rel_dpg_score"], reverse=True)
    best_control_after = next(r for r in deduped if r["is_control"])

    return {
        "ranked": deduped,
        "best_control": best_control_after,
        "total_paths_simulated": len(all_paths),
    }


def get_yunara_4core_top1_build():
    global _YUNARA_4CORE_TOP1_CACHE
    if _YUNARA_4CORE_TOP1_CACHE is None:
        ranked_data = rank_yunara_4core_paths()
        top1 = ranked_data["ranked"][0]
        _YUNARA_4CORE_TOP1_CACHE = {
            "path": top1["path"],
            "score": top1["rel_dpg_score"],
            "control_path": ranked_data["best_control"]["path"],
            "total_paths_tested": ranked_data["total_paths_simulated"],
        }
    return _YUNARA_4CORE_TOP1_CACHE


def print_table(ranked, best_control, top_n=20):
    ctrl_dps = best_control["y"]
    ctrl_costs = best_control["x"]
    baseline = best_control["rel_dpg_score"]
    controls = [r for r in ranked if r["is_control"]]
    top_rows = ranked[:top_n]
    total_rows = top_n + len(controls)

    print(
        f"\nTop {total_rows} Rows: Top {top_n} + All Controls "
        f"(Rel by DPS/1000g ratio, weighted 5:4:3:3 over 1~4 Core)"
    )
    header = (
        f"{'RK':>2} | {'BUILD':<22} | {'1C (DPS/DPG)':^20} | {'2C (DPS/DPG)':^20} | {'3C (DPS/DPG)':^20} | {'4C (DPS/DPG)':^20} | "
        f"{'REL_DPG%':^9} | {'VS CTRL':^10} | {'C1 ΔDPS/ΔDPG%':^14} | {'C2 ΔDPS/ΔDPG%':^14} | {'C3 ΔDPS/ΔDPG%':^14} | {'C4 ΔDPS/ΔDPG%':^14}"
    )
    print(header)
    print("-" * len(header))

    output_rows = top_rows + controls
    for rank, r in enumerate(output_rows, start=1):
        dps = r["y"]
        costs = r["x"]
        dpgs = [dps[i] / (costs[i] / 1000.0) if costs[i] > 0 else 0.0 for i in range(4)]
        vs_ctrl = ((r["rel_dpg_score"] / baseline) - 1.0) * 100.0 if baseline > 0 else 0.0
        cells = []
        for i in range(4):
            dps_pct = ((dps[i] / ctrl_dps[i]) - 1.0) * 100.0 if ctrl_dps[i] > 0 else 0.0
            ctrl_dpg_i = ctrl_dps[i] / (ctrl_costs[i] / 1000.0) if ctrl_costs[i] > 0 else 0.0
            dpg_pct = ((dpgs[i] / ctrl_dpg_i) - 1.0) * 100.0 if ctrl_dpg_i > 0 else 0.0
            cells.append(f"{dps_pct:+5.1f}/{dpg_pct:+5.1f}")

        label = r["label"] + (" [CTRL]" if r["is_control"] else "")
        print(
            f"{rank:>2} | {label:<22} | "
            f"{dps[0]:>6.1f}/{dpgs[0]:<6.1f} | {dps[1]:>6.1f}/{dpgs[1]:<6.1f} | {dps[2]:>6.1f}/{dpgs[2]:<6.1f} | {dps[3]:>6.1f}/{dpgs[3]:<6.1f} | "
            f"{r['rel_dpg_score']:>9.2f} | {vs_ctrl:+8.2f}% | "
            f"{cells[0]:>14} | {cells[1]:>14} | {cells[2]:>14} | {cells[3]:>14}"
        )


def plot_graph(ranked, best_control):
    top5 = ranked[:5]
    controls = [r for r in ranked if r["is_control"]]

    plt.figure(figsize=(15, 10))
    for r in ranked:
        if not r["is_control"]:
            plt.plot(r["x"], r["y"], color="#B0B7C3", alpha=0.15, linewidth=0.8, marker="o", markersize=2)

    top_colors = ["#E4572E", "#F3A712", "#2E86AB", "#3A7D44", "#A23B72"]
    for i, r in enumerate(top5):
        c = top_colors[i % len(top_colors)]
        plt.plot(
            r["x"], r["y"], color=c, linewidth=2.4, marker="D", markersize=5,
            label=f"Top{i+1} {r['label']} (RelDPG:{r['rel_dpg_score']:.1f})"
        )
        for j in range(4):
            plt.annotate(
                f"{r['y'][j]:.0f}", (r["x"][j], r["y"][j]),
                textcoords="offset points", xytext=(8, 8 if j % 2 == 0 else -12),
                fontsize=7, color=c,
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor=c, alpha=0.85, linewidth=0.6)
            )

    for r in controls:
        plt.plot(
            r["x"], r["y"], color="#111111", linewidth=2.8, marker="o", markersize=7,
            label=f"{r['control_label']} ({r['label']})"
        )
        for j in range(4):
            plt.annotate(
                f"{r['y'][j]:.0f}", (r["x"][j], r["y"][j]),
                textcoords="offset points", xytext=(-16, 10 if j % 2 == 0 else -14),
                fontsize=8, color="#111111",
                bbox=dict(boxstyle="round,pad=0.15", facecolor="#F8F9FA", edgecolor="#222222", alpha=0.9, linewidth=0.6)
            )

    plt.title("Yunara Build Path Power Spike (1/2/3/4 Core)")
    plt.xlabel("Total Gold at Core Timing")
    plt.ylabel("DPS")
    plt.grid(True, alpha=0.3)
    plt.legend(loc="best", fontsize=9)
    plt.tight_layout()
    plt.show()


def main():
    print("\n=== Yunara Build Path Power Spike (1->2->3->4 Core) ===")
    ranked_data = rank_yunara_4core_paths()
    ranked = ranked_data["ranked"]
    best_control = ranked_data["best_control"]

    print(f"\nPower Spike Paths Simulated ({ranked_data['total_paths_simulated']} total, before same-combo dedup)")
    print(
        f"Best Control Baseline (Rel DPG 5:4:3:3): {best_control['rel_dpg_score']:.2f} "
        f"({best_control['label']})"
    )

    print_table(ranked, best_control, top_n=20)
    plot_graph(ranked, best_control)


if __name__ == "__main__":
    main()
