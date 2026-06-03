import csv
import json
from datetime import datetime

import matplotlib.pyplot as plt

from adc_sim.settings import get_result_export_settings
from adc_sim.simulations.ashe import (
    simulate_yunara_core_path,
    _build_ashe_4core_all_paths,
    build_ashe_like_core_report_meta,
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
    """Return the short printable label for a Yunara item path."""
    return "-".join(ITEM_SHORT[k] for k in path)


def _calculate_dpg_values(dps_values, gold_values):
    """Return DPS-per-1000g values for aligned DPS/gold series."""
    return [
        dps_values[i] / (gold_values[i] / 1000.0) if gold_values[i] > 0 else 0.0
        for i in range(len(dps_values))
    ]


def _build_yunara_result_entry(path, dps_values, gold_values):
    """Build a serializable ranking entry before control-relative scoring."""
    meta = build_ashe_like_core_report_meta("Yunara", path, 4)
    is_control = tuple(sorted(path)) == CONTROL_COMBO
    return {
        "path": tuple(path),
        "label": _path_label(path),
        "x": list(gold_values),
        "y": list(dps_values),
        "path_meta": meta,
        "is_control": is_control,
        "control_label": CONTROL_LABEL if is_control else "",
    }


def rank_yunara_4core_paths():
    """Rank Yunara 4-core paths and keep the best order per 4-item set."""
    all_paths = _build_ashe_4core_all_paths()

    results = []
    for c1, c2, c3, c4 in all_paths:
        dps1, cost1 = simulate_yunara_core_path([c1], 1)
        dps2, cost2 = simulate_yunara_core_path([c1, c2], 2)
        dps3, cost3 = simulate_yunara_core_path([c1, c2, c3], 3)
        dps4, cost4 = simulate_yunara_core_path([c1, c2, c3, c4], 4)
        path = (c1, c2, c3, c4)
        results.append(_build_yunara_result_entry(path, [dps1, dps2, dps3, dps4], [cost1, cost2, cost3, cost4]))

    control_candidates = [row for row in results if row["is_control"]]
    if not control_candidates:
        raise RuntimeError("Control build not found: Krk-PD-IE-LDR")
    best_control = control_candidates[0]
    ctrl_dpg = _calculate_dpg_values(best_control["y"], best_control["x"])

    for row in results:
        row_dpg = _calculate_dpg_values(row["y"], row["x"])
        rel = [(row_dpg[i] / ctrl_dpg[i]) if ctrl_dpg[i] > 0 else 0.0 for i in range(4)]
        row["dpg"] = row_dpg
        row["rel_dpg_score"] = sum(CORE_WEIGHTS[i] * rel[i] for i in range(4)) * 100.0

    combo_best = {}
    for row in results:
        combo_key = tuple(sorted(row["path"]))
        prev = combo_best.get(combo_key)
        if prev is None or row["rel_dpg_score"] > prev["rel_dpg_score"]:
            combo_best[combo_key] = row

    deduped = list(combo_best.values())
    deduped.sort(key=lambda value: value["rel_dpg_score"], reverse=True)
    best_control_after = next(row for row in deduped if row["is_control"])

    return {
        "ranked": deduped,
        "best_control": best_control_after,
        "total_paths_simulated": len(all_paths),
    }


def get_yunara_4core_top1_build():
    """Return the cached Yunara 4-core top1 build summary."""
    global _YUNARA_4CORE_TOP1_CACHE
    if _YUNARA_4CORE_TOP1_CACHE is None:
        ranked_data = rank_yunara_4core_paths()
        top1 = ranked_data["ranked"][0]
        _YUNARA_4CORE_TOP1_CACHE = {
            "path": top1["path"],
            "score": top1["rel_dpg_score"],
            "control_path": ranked_data["best_control"]["path"],
            "total_paths_tested": ranked_data["total_paths_simulated"],
            "label": top1["label"],
        }
    return _YUNARA_4CORE_TOP1_CACHE


def _build_yunara_report_row(rank, row, best_control):
    """Flatten one ranked Yunara result into a CSV/JSON-friendly row."""
    ctrl_dps = best_control["y"]
    ctrl_costs = best_control["x"]
    ctrl_dpg = _calculate_dpg_values(ctrl_dps, ctrl_costs)
    dpgs = row.get("dpg") or _calculate_dpg_values(row["y"], row["x"])
    baseline = best_control["rel_dpg_score"]
    report_row = {
        "rank": rank,
        "champion": "Yunara",
        "build": "-".join(row["path"]),
        "label": row["label"],
        "path": list(row["path"]),
        "rel_dpg_score": row["rel_dpg_score"],
        "vs_control_pct": ((row["rel_dpg_score"] / baseline) - 1.0) * 100.0 if baseline > 0 else 0.0,
        "is_control": row["is_control"],
        "control_label": row["control_label"],
    }
    for index in range(4):
        core_no = index + 1
        dps_pct = ((row["y"][index] / ctrl_dps[index]) - 1.0) * 100.0 if ctrl_dps[index] > 0 else 0.0
        dpg_pct = ((dpgs[index] / ctrl_dpg[index]) - 1.0) * 100.0 if ctrl_dpg[index] > 0 else 0.0
        report_row[f"core{core_no}_gold"] = row["x"][index]
        report_row[f"core{core_no}_dps"] = row["y"][index]
        report_row[f"core{core_no}_dpg"] = dpgs[index]
        report_row[f"core{core_no}_delta_dps_pct"] = dps_pct
        report_row[f"core{core_no}_delta_dpg_pct"] = dpg_pct
    return report_row


def _build_yunara_report_rows(ranked, best_control, top_n):
    """Build the same row set used by console output and report export."""
    controls = [row for row in ranked if row["is_control"]]
    output_rows = ranked[:top_n] + controls
    return [
        _build_yunara_report_row(rank=index, row=row, best_control=best_control)
        for index, row in enumerate(output_rows, start=1)
    ]


def _resolve_report_base_path(report_name, generated_at):
    """Return the base path for a timestamped report name."""
    export_settings = get_result_export_settings()
    export_settings["export_dir"].mkdir(parents=True, exist_ok=True)
    timestamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
    return export_settings["export_dir"] / f"{report_name}_{timestamp}"


def _write_csv_rows(csv_path, rows):
    """Write flattened rows to CSV while preserving column order."""
    if not rows:
        return
    with csv_path.open("w", newline="", encoding="utf-8") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_json_payload(json_path, payload):
    """Write one JSON payload with UTF-8 encoding for report reuse."""
    with json_path.open("w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, ensure_ascii=False, indent=2)


def export_yunara_ranking_report(ranked_data, top_n=20):
    """Export Yunara ranking rows to CSV/JSON according to settings."""
    export_settings = get_result_export_settings()
    if not export_settings["enabled"]:
        return []

    generated_at = datetime.utcnow()
    rows = _build_yunara_report_rows(ranked_data["ranked"], ranked_data["best_control"], top_n)
    payload = {
        "report_type": "yunara_ranking",
        "generated_at": generated_at.isoformat() + "Z",
        "summary": {
            "best_build": list(ranked_data["ranked"][0]["path"]),
            "best_label": ranked_data["ranked"][0]["label"],
            "best_score": ranked_data["ranked"][0]["rel_dpg_score"],
            "control_build": list(ranked_data["best_control"]["path"]),
            "control_label": ranked_data["best_control"]["label"],
            "control_score": ranked_data["best_control"]["rel_dpg_score"],
            "total_paths_simulated": ranked_data["total_paths_simulated"],
            "top_n": top_n,
        },
        "rows": rows,
    }

    written_paths = []
    report_base = _resolve_report_base_path("yunara_ranking", generated_at)
    export_format = export_settings["format"]
    try:
        if export_format in ("csv", "both"):
            csv_path = report_base.with_suffix(".csv")
            _write_csv_rows(csv_path, rows)
            written_paths.append(csv_path)
        if export_format in ("json", "both"):
            json_path = report_base.with_suffix(".json")
            _write_json_payload(json_path, payload)
            written_paths.append(json_path)
    except OSError as exc:
        print(f"[Warn] Failed to export Yunara ranking report: {exc}")
        return []
    return written_paths


def print_table(ranked, best_control, top_n=20):
    """Print the Yunara ranking table from shared flattened report rows."""
    controls = [row for row in ranked if row["is_control"]]
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

    for row in _build_yunara_report_rows(ranked, best_control, top_n):
        cells = []
        for index in range(4):
            cells.append(
                f"{row[f'core{index + 1}_delta_dps_pct']:+5.1f}/{row[f'core{index + 1}_delta_dpg_pct']:+5.1f}"
            )
        label = row["label"] + (" [CTRL]" if row["is_control"] else "")
        print(
            f"{row['rank']:>2} | {label:<22} | "
            f"{row['core1_dps']:>6.1f}/{row['core1_dpg']:<6.1f} | {row['core2_dps']:>6.1f}/{row['core2_dpg']:<6.1f} | "
            f"{row['core3_dps']:>6.1f}/{row['core3_dpg']:<6.1f} | {row['core4_dps']:>6.1f}/{row['core4_dpg']:<6.1f} | "
            f"{row['rel_dpg_score']:>9.2f} | {row['vs_control_pct']:+8.2f}% | "
            f"{cells[0]:>14} | {cells[1]:>14} | {cells[2]:>14} | {cells[3]:>14}"
        )


def plot_graph(ranked, best_control):
    """Plot the top-ranked Yunara paths and control build on one graph."""
    top5 = ranked[:5]
    controls = [row for row in ranked if row["is_control"]]

    plt.figure(figsize=(15, 10))
    for row in ranked:
        if not row["is_control"]:
            plt.plot(row["x"], row["y"], color="#B0B7C3", alpha=0.15, linewidth=0.8, marker="o", markersize=2)

    top_colors = ["#E4572E", "#F3A712", "#2E86AB", "#3A7D44", "#A23B72"]
    for index, row in enumerate(top5):
        color = top_colors[index % len(top_colors)]
        plt.plot(
            row["x"], row["y"], color=color, linewidth=2.4, marker="D", markersize=5,
            label=f"Top{index + 1} {row['label']} (RelDPG:{row['rel_dpg_score']:.1f})"
        )
        for core_index in range(4):
            plt.annotate(
                f"{row['y'][core_index]:.0f}", (row["x"][core_index], row["y"][core_index]),
                textcoords="offset points", xytext=(8, 8 if core_index % 2 == 0 else -12),
                fontsize=7, color=color,
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor=color, alpha=0.85, linewidth=0.6)
            )

    for row in controls:
        plt.plot(
            row["x"], row["y"], color="#111111", linewidth=2.8, marker="o", markersize=7,
            label=f"{row['control_label']} ({row['label']})"
        )
        for core_index in range(4):
            plt.annotate(
                f"{row['y'][core_index]:.0f}", (row["x"][core_index], row["y"][core_index]),
                textcoords="offset points", xytext=(-16, 10 if core_index % 2 == 0 else -14),
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
    """Run the Yunara ranking workflow with optional report export."""
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
    report_paths = export_yunara_ranking_report(ranked_data, top_n=20)
    for report_path in report_paths:
        print(f"[Info] Saved Yunara report: {report_path}")
    plot_graph(ranked, best_control)


if __name__ == "__main__":
    main()
