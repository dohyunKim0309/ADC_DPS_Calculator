import csv
import json
from datetime import datetime

import matplotlib.pyplot as plt

from adc_sim.settings import get_result_export_settings
from adc_sim.simulations.ashe import (
    simulate_ashe_core_path,
    get_ashe_4core_top1_build,
    build_ashe_like_core_report_meta,
)
from adc_sim.simulations.yunara import simulate_yunara_core_path, get_yunara_4core_top1_build
from adc_sim.simulations.kaisa import (
    simulate_kaisa_core_path,
    get_kaisa_4core_top1_build,
    build_kaisa_core_report_meta,
)
from adc_sim.simulations.corki import (
    simulate_corki_core_path,
    get_corki_4core_top1_build,
    build_corki_core_report_meta,
)


def _simulate_compare_stat(champ_name, cfg, core_tier):
    """Simulate one champion at one core tier and return serializable stats."""
    if champ_name == "Ashe":
        dps, gold = simulate_ashe_core_path(cfg["path"][:core_tier], core_tier)
        meta = build_ashe_like_core_report_meta("Ashe", cfg["path"], core_tier)
    elif champ_name == "Yunara":
        dps, gold = simulate_yunara_core_path(cfg["path"], core_tier)
        meta = build_ashe_like_core_report_meta("Yunara", cfg["path"], core_tier)
    elif champ_name == "KaiSa":
        dps, gold, w_cast_count = simulate_kaisa_core_path(cfg["path"], core_tier)
        meta = build_kaisa_core_report_meta(cfg["path"], core_tier, w_cast_count=w_cast_count)
    elif champ_name == "Corki":
        # 챔피언 간 비교에서는 코르키 W(발키리 트레일) 데미지 제외
        dps, gold = simulate_corki_core_path(cfg["path"], cfg["shoe"], cfg["rune"], core_tier, include_w=False)
        meta = build_corki_core_report_meta(cfg["path"], cfg["shoe"], cfg["rune"], core_tier)
    else:
        raise ValueError(f"Unknown champion config: {champ_name}")

    meta.update({
        "champion": champ_name,
        "dps": dps,
        "gold": gold,
        "dpg": dps / (gold / 1000.0) if gold > 0 else 0.0,
    })
    return meta


def _print_compare_section(title, configs):
    """Print one compare section and return the structured per-core rows."""
    rows = []
    for core_tier in (1, 2, 3, 4):
        stats = {}
        for champ_name, cfg in configs.items():
            stats[champ_name] = _simulate_compare_stat(champ_name, cfg, core_tier)
        rows.append({"core": core_tier, "stats": stats})

    print(f"\n=== {title} ===")
    for row in rows:
        core = row["core"]
        stats = row["stats"]
        winner = max(stats.items(), key=lambda kv: kv[1]["dps"])
        print(f"[{core} Core] Winner: {winner[0]} ({winner[1]['dps']:.1f} DPS)")
        for champ_name, value in sorted(stats.items(), key=lambda kv: kv[1]["dps"], reverse=True):
            print(f"  - {champ_name:<6} DPS {value['dps']:.1f} | Gold {value['gold']} | DPG {value['dpg']:.2f}")
        print()
    return rows


def _build_compare_export_rows(rows, variant):
    """Flatten compare rows for file export and collect winner summaries."""
    flat_rows = []
    summary_rows = []
    for row in rows:
        winner = max(row["stats"].items(), key=lambda kv: kv[1]["dps"])[0]
        summary_rows.append({"variant": variant, "core": row["core"], "winner": winner})
        for champ_name, stat in row["stats"].items():
            flat_rows.append({
                "variant": variant,
                "core": row["core"],
                "champion": champ_name,
                "build": stat["build"],
                "active_build": stat["active_build"],
                "path": stat["full_path"],
                "active_path": stat["active_path"],
                "dps": stat["dps"],
                "gold": stat["gold"],
                "dpg": stat["dpg"],
                "winner": winner,
                "w_cast_count": stat.get("w_cast_count"),
                "w_evolved": stat.get("w_evolved"),
                "shoe": stat.get("shoe"),
                "rune": stat.get("rune"),
            })
    return flat_rows, summary_rows


def _plot_combined_compare(top1_rows, basic_rows):
    """Plot champion DPS curves for Top1 and Basic compare variants."""
    champ_colors = {
        "Ashe": "#1f77b4",
        "Yunara": "#7b61ff",
        "KaiSa": "#e4572e",
        "Corki": "#2ca02c",
    }

    plt.figure(figsize=(13, 8))

    for rows, variant, linestyle, marker, alpha in [
        (top1_rows, "Top1", "-", "o", 0.95),
        (basic_rows, "Basic", "--", "s", 0.9),
    ]:
        for champ in ("Ashe", "Yunara", "KaiSa", "Corki"):
            xs = [row["stats"][champ]["gold"] for row in rows]
            ys = [row["stats"][champ]["dps"] for row in rows]
            color = champ_colors[champ]
            plt.plot(
                xs, ys,
                color=color,
                linestyle=linestyle,
                marker=marker,
                markersize=5,
                linewidth=2.2 if variant == "Top1" else 1.9,
                alpha=alpha,
                label=f"{champ} {variant}"
            )
            for index in range(len(xs)):
                xoff = 8 if variant == "Top1" else -30
                yoff = 8 if index % 2 == 0 else -12
                plt.annotate(
                    f"{ys[index]:.0f}",
                    (xs[index], ys[index]),
                    textcoords="offset points",
                    xytext=(xoff, yoff),
                    fontsize=7,
                    color=color,
                    bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="none", alpha=0.65),
                )

    plt.title("Cross-Champion Power Compare (Top1 + Basic, 1/2/3/4 Core)")
    plt.xlabel("Total Gold at Core Timing")
    plt.ylabel("DPS")
    plt.grid(True, alpha=0.25)
    plt.legend(loc="best", fontsize=9)
    plt.tight_layout()
    plt.show()


def _write_csv_rows(csv_path, rows):
    """Write one flat row collection to CSV."""
    if not rows:
        return
    with csv_path.open("w", newline="", encoding="utf-8") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_json_payload(json_path, payload):
    """Write one compare payload to JSON."""
    with json_path.open("w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, ensure_ascii=False, indent=2)


def _export_compare_report(report_name, generated_at, rows, summary_rows):
    """Export one compare variant in the configured formats."""
    export_settings = get_result_export_settings()
    export_settings["export_dir"].mkdir(parents=True, exist_ok=True)
    timestamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
    base_path = export_settings["export_dir"] / f"{report_name}_{timestamp}"
    export_format = export_settings["format"]
    written_paths = []

    if export_format in ("csv", "both"):
        csv_path = base_path.with_suffix(".csv")
        _write_csv_rows(csv_path, rows)
        written_paths.append(csv_path)
    if export_format in ("json", "both"):
        json_path = base_path.with_suffix(".json")
        _write_json_payload(json_path, {
            "report_type": report_name,
            "generated_at": generated_at.isoformat() + "Z",
            "winner_summary": summary_rows,
            "rows": rows,
        })
        written_paths.append(json_path)
    return written_paths


def export_compare_reports(top1_rows, basic_rows):
    """Export Top1/Basic compare rows and winner summaries."""
    export_settings = get_result_export_settings()
    if not export_settings["enabled"]:
        return []

    generated_at = datetime.utcnow()
    top1_flat, top1_summary = _build_compare_export_rows(top1_rows, "Top1")
    basic_flat, basic_summary = _build_compare_export_rows(basic_rows, "Basic")
    summary_rows = top1_summary + basic_summary
    written_paths = []

    try:
        written_paths.extend(_export_compare_report("champion_compare_top1", generated_at, top1_flat, top1_summary))
    except OSError as exc:
        print(f"[Warn] Failed to export Top1 champion comparison report: {exc}")

    try:
        written_paths.extend(_export_compare_report("champion_compare_basic", generated_at, basic_flat, basic_summary))
    except OSError as exc:
        print(f"[Warn] Failed to export Basic champion comparison report: {exc}")

    try:
        written_paths.extend(_export_compare_report("champion_compare_summary", generated_at, summary_rows, summary_rows))
    except OSError as exc:
        print(f"[Warn] Failed to export champion comparison summary: {exc}")

    return written_paths


def compare_builds():
    """Run cross-champion Top1/Basic comparisons and optionally export them."""
    print("[Info] Loading Ashe top1 from simulation_ashe 4-core ranking...")
    ashe_top1 = get_ashe_4core_top1_build()
    print("[Info] Loading Yunara top1 from simulation_yunara 4-core ranking...")
    yunara_top1 = get_yunara_4core_top1_build()
    ashe_path = ashe_top1["path"]
    yunara_path = yunara_top1["path"]
    print("[Info] Loading KaiSa top1 from simulation_kaisa 4-core ranking...")
    kaisa_top1 = get_kaisa_4core_top1_build()
    kaisa_path = kaisa_top1["path"]
    print("[Info] Loading Corki top1 from simulation_corki 4-core ranking (can take some time)...")
    corki_top1 = get_corki_4core_top1_build()
    corki_path = corki_top1["path"]
    corki_shoe = corki_top1["shoe"]
    corki_rune = corki_top1["rune"]

    print("\n=== Cross-Champion Power Compare (1~4 Core) ===")
    print("Configured Top1 builds:")
    print(
        f"- Ashe   : {'-'.join(ashe_path)} + Berserker / LT+CutDown "
        f"(Top1 from simulation_ashe, score {ashe_top1['score']:.2f})"
    )
    print(
        f"- Yunara : {'-'.join(yunara_path)} + Berserker / LT+CutDown (start Q active) "
        f"(Top1 from simulation_yunara, score {yunara_top1['score']:.2f})"
    )
    print(
        f"- KaiSa  : {'-'.join(kaisa_path)} + Berserker / LT+CutDown "
        f"(Top1 from simulation_kaisa, score {kaisa_top1['score']:.2f}; current KaiSa skill plan)"
    )
    print(
        f"- Corki  : {'-'.join(corki_path)} + {corki_shoe} / {corki_rune}+CutDown "
        f"(Top1 from simulation_corki, score {corki_top1['score']:.2f})"
    )
    print()

    top1_configs = {
        "Ashe": {"path": ashe_path},
        "Yunara": {"path": yunara_path},
        "KaiSa": {"path": kaisa_path},
        "Corki": {"path": corki_path, "shoe": corki_shoe, "rune": corki_rune},
    }
    top1_rows = _print_compare_section("Cross-Champion Top1 Compare (1~4 Core)", top1_configs)

    kaisa_basic_path = kaisa_top1.get("control_path", ("kraken", "guinsoo", "nashor", "terminus"))
    corki_basic_path = ("trinity", "muramana", "collector", "ie")
    corki_basic_shoe = "plated"
    corki_basic_rune = "conq"

    print("Configured Basic builds:")
    print("- Ashe   : kraken-pd-ie-ldr + Berserker / LT+CutDown")
    print("- Yunara : kraken-pd-ie-ldr + Berserker / LT+CutDown (start Q active)")
    print(f"- KaiSa  : {'-'.join(kaisa_basic_path)} + Berserker / LT+CutDown (Control from simulation_kaisa)")
    print(f"- Corki  : {'-'.join(corki_basic_path)} + {corki_basic_shoe} / {corki_basic_rune}+CutDown (requested base build)")
    print()

    basic_configs = {
        "Ashe": {"path": ("kraken", "pd", "ie", "ldr")},
        "Yunara": {"path": ("kraken", "pd", "ie", "ldr")},
        "KaiSa": {"path": kaisa_basic_path},
        "Corki": {"path": corki_basic_path, "shoe": corki_basic_shoe, "rune": corki_basic_rune},
    }
    basic_rows = _print_compare_section("Cross-Champion Basic Build Compare (1~4 Core)", basic_configs)

    for report_path in export_compare_reports(top1_rows, basic_rows):
        print(f"[Info] Saved champion comparison report: {report_path}")
    _plot_combined_compare(top1_rows, basic_rows)


if __name__ == "__main__":
    compare_builds()
