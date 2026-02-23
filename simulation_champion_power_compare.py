import matplotlib.pyplot as plt

from simulation_ashe import (
    simulate_ashe_core_path,
    get_ashe_4core_top1_build,
)
from simulation_yunara import simulate_yunara_core_path, get_yunara_4core_top1_build
from simulation_kaisa import simulate_kaisa_core_path, get_kaisa_4core_top1_build
from simulation_corki import simulate_corki_core_path, get_corki_4core_top1_build


def _print_compare_section(title, configs):
    rows = []
    for core_tier in (1, 2, 3, 4):
        stats = {}
        for champ_name, cfg in configs.items():
            if champ_name == "Ashe":
                dps, gold = simulate_ashe_core_path(cfg["path"][:core_tier], core_tier)
            elif champ_name == "Yunara":
                dps, gold = simulate_yunara_core_path(cfg["path"], core_tier)
            elif champ_name == "KaiSa":
                dps, gold, _ = simulate_kaisa_core_path(cfg["path"], core_tier)
            elif champ_name == "Corki":
                dps, gold = simulate_corki_core_path(cfg["path"], cfg["shoe"], cfg["rune"], core_tier)
            else:
                raise ValueError(f"Unknown champion config: {champ_name}")
            stats[champ_name] = {"dps": dps, "gold": gold}
        rows.append({"core": core_tier, "stats": stats})

    print(f"\n=== {title} ===")
    for row in rows:
        core = row["core"]
        stats = row["stats"]
        winner = max(stats.items(), key=lambda kv: kv[1]["dps"])
        print(f"[{core} Core] Winner: {winner[0]} ({winner[1]['dps']:.1f} DPS)")
        for champ_name, v in sorted(stats.items(), key=lambda kv: kv[1]["dps"], reverse=True):
            dpg = v["dps"] / (v["gold"] / 1000.0) if v["gold"] > 0 else 0.0
            print(f"  - {champ_name:<6} DPS {v['dps']:.1f} | Gold {v['gold']} | DPG {dpg:.2f}")
        print()
    return rows


def _plot_combined_compare(top1_rows, basic_rows):
    # champion color fixed; top1/basic separated by line style
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
            xs = [r["stats"][champ]["gold"] for r in rows]
            ys = [r["stats"][champ]["dps"] for r in rows]
            c = champ_colors[champ]
            plt.plot(
                xs, ys,
                color=c,
                linestyle=linestyle,
                marker=marker,
                markersize=5,
                linewidth=2.2 if variant == "Top1" else 1.9,
                alpha=alpha,
                label=f"{champ} {variant}"
            )
            for i in range(len(xs)):
                xoff = 8 if variant == "Top1" else -30
                yoff = 8 if i % 2 == 0 else -12
                plt.annotate(
                    f"{ys[i]:.0f}",
                    (xs[i], ys[i]),
                    textcoords="offset points",
                    xytext=(xoff, yoff),
                    fontsize=7,
                    color=c,
                    bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="none", alpha=0.65),
                )

    plt.title("Cross-Champion Power Compare (Top1 + Basic, 1/2/3/4 Core)")
    plt.xlabel("Total Gold at Core Timing")
    plt.ylabel("DPS")
    plt.grid(True, alpha=0.25)
    plt.legend(loc="best", fontsize=9)
    plt.tight_layout()
    plt.show()


def compare_builds():
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

    # 각 챔피언 기본(대조군) 빌드 비교
    # Ashe/Yunara: Krk-PD-IE-LDR
    # KaiSa: simulation_kaisa의 baseline control top1 (CTRL1/CTRL2 중 weighted_dpg 최강)
    # Corki: 요청 반영 - Triforce -> Muramana -> Collector -> IE
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

    _plot_combined_compare(top1_rows, basic_rows)


if __name__ == "__main__":
    compare_builds()
