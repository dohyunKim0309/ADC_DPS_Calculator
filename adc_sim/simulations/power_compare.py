import csv
import json
from datetime import datetime

import matplotlib.pyplot as plt

from adc_sim.settings import get_result_export_settings, CORE_WEIGHTS_RAW
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
from adc_sim.simulations.cogmaw import (
    simulate_cogmaw_core_path,
    get_cogmaw_powercompare_builds,
    build_cogmaw_core_report_meta,
)
from adc_sim.simulations.vayne import (
    simulate_vayne_core_path,
    get_vayne_powercompare_builds,
    build_vayne_core_report_meta,
)
from adc_sim.simulations.jinx import (
    simulate_jinx_core_path,
    get_jinx_powercompare_builds,
    build_jinx_core_report_meta,
    JINX_RANKING_Q_MODE,
)
from adc_sim.runes import LethalTempo
from adc_sim.data.items_data import DORAN_SHORT, ADC_PACKAGES


def _simulate_compare_stat(champ_name, cfg, core_tier):
    """Simulate one champion at one core tier and return serializable stats."""
    # Ashe/Yunara/KaiSa: 정배 패키지(A/B)로 도란+신발+공속룬을 함께 지정.
    # Corki: 패키지 제약 없음 → 도란만(신발/룬은 cfg.shoe/rune 자유 탐색값).
    pkg_kw = dict(
        doran_key=cfg.get("doran", "doranblade"),
        boots_key=cfg.get("boots", "berserker"),
        rune_as_bonus=cfg.get("rune_as", 0.0),
    )
    if champ_name == "Ashe":
        dps, gold = simulate_ashe_core_path(cfg["path"][:core_tier], core_tier, **pkg_kw)
        meta = build_ashe_like_core_report_meta("Ashe", cfg["path"], core_tier)
        choice = cfg.get("pkg_label", "Bld+Zerk")
    elif champ_name == "Yunara":
        # target_count: 비교에서 유나라를 몇 명 기준으로 볼지(1=단일, 2=2명 교전 유효 DPS). 기본 1.
        yunara_tc = cfg.get("target_count", 1)
        dps, gold = simulate_yunara_core_path(cfg["path"], core_tier, target_count=yunara_tc, **pkg_kw)
        meta = build_ashe_like_core_report_meta("Yunara", cfg["path"], core_tier)
        choice = cfg.get("pkg_label", "Bld+Zerk")
    elif champ_name == "KaiSa":
        dps, gold, w_cast_count, sustain = simulate_kaisa_core_path(
            cfg["path"],
            core_tier,
            bloodline_lifesteal=cfg.get("bloodline_lifesteal", 0.0),
            return_sustain=True,
            **pkg_kw,
        )
        meta = build_kaisa_core_report_meta(
            cfg["path"],
            core_tier,
            w_cast_count=w_cast_count,
            doran_key=pkg_kw["doran_key"],
            boots_key=pkg_kw["boots_key"],
            sustain=sustain,
        )
        choice = cfg.get("pkg_label", "Bld+Zerk")
    elif champ_name == "Corki":
        # 챔피언 간 비교에서는 코르키 W(발키리 트레일) 데미지 제외
        doran = cfg.get("doran", "doranblade")
        dps, gold = simulate_corki_core_path(cfg["path"], cfg["shoe"], cfg["rune"], core_tier, include_w=False, doran_key=doran)
        meta = build_corki_core_report_meta(cfg["path"], cfg["shoe"], cfg["rune"], core_tier)
        choice = DORAN_SHORT.get(doran, doran)
    elif champ_name == "CogMaw":
        # 코그모는 룬 의존(LT/PtA) → cfg.keystone_cls 로 키스톤 지정. 보조룬 CutDown 은 simulate 내부.
        keystone_cls = cfg.get("keystone_cls", LethalTempo)
        dps, gold = simulate_cogmaw_core_path(cfg["path"], core_tier, keystone_cls=keystone_cls, **pkg_kw)
        meta = build_cogmaw_core_report_meta(cfg["path"], core_tier)
        choice = f"{cfg.get('pkg_label', 'Bow+Glut')}/{cfg.get('rune_label', 'LT')}"
    elif champ_name == "Vayne":
        # 베인도 룬 의존(LT/PtA) — cfg.keystone_cls 로 키스톤 지정. 보조룬 CutDown 은 simulate 내부.
        vayne_keystone = cfg.get("keystone_cls", LethalTempo)
        dps, gold = simulate_vayne_core_path(cfg["path"], core_tier, keystone_cls=vayne_keystone, **pkg_kw)
        meta = build_vayne_core_report_meta(cfg["path"], core_tier)
        choice = f"{cfg.get('pkg_label', 'Bld+Zerk')}/{cfg.get('rune_label', 'LT')}"
    elif champ_name == "Jinx":
        q_mode = cfg.get("q_mode", JINX_RANKING_Q_MODE)
        dps, gold = simulate_jinx_core_path(cfg["path"], core_tier, q_mode=q_mode, **pkg_kw)
        meta = build_jinx_core_report_meta(cfg["path"], core_tier, q_mode=q_mode)
        choice = f"{cfg.get('pkg_label', 'Bld+Zerk')}/{q_mode}"
    else:
        raise ValueError(f"Unknown champion config: {champ_name}")

    meta.update({
        "champion": champ_name,
        "dps": dps,
        "gold": gold,
        "dpg": dps / (gold / 1000.0) if gold > 0 else 0.0,
        "choice": choice,
        # 적 챔피언 수(유나라만 2명 등으로 다를 수 있음; 나머지는 단일 대상=1)
        "target_count": cfg.get("target_count", 1),
    })
    return meta


def _best_pkg_cfg(champ_name, path):
    """주어진 (챔프, path)를 정배 패키지 A/B 중 4코어 weighted-DPG(1:1:1:1) 최적으로 평가해
    패키지 설정(doran/boots/rune_as/pkg_label) 반환. basic 비교를 개별 sim(컨트롤이 최적 패키지를
    고름)과 일치시키기 위함. Corki/CogMaw 는 자체 패키지 메커니즘이라 이 헬퍼를 쓰지 않는다."""
    weights = list(CORE_WEIGHTS_RAW)
    best_cfg, best_w = None, -1.0
    for pkg in ADC_PACKAGES:
        probe = {"path": path, "doran": pkg["doran"], "boots": pkg["boots"],
                 "rune_as": pkg["rune_as"], "pkg_label": pkg["label"],
                 "bloodline_lifesteal": pkg.get("bloodline_lifesteal", 0.0)}
        wsum = sum(weights[t - 1] * _simulate_compare_stat(champ_name, probe, t)["dpg"] for t in range(1, 5))
        if wsum > best_w:
            best_w = wsum
            best_cfg = {"doran": pkg["doran"], "boots": pkg["boots"],
                        "rune_as": pkg["rune_as"], "pkg_label": pkg["label"],
                        "bloodline_lifesteal": pkg.get("bloodline_lifesteal", 0.0)}
    return best_cfg


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
        # 챔피언 간 순위 기준: DPG(1000골드당 DPS, 골드효율)
        winner = max(stats.items(), key=lambda kv: kv[1]["dpg"])
        print(f"[{core} Core] Winner: {winner[0]} ({winner[1]['dpg']:.2f} DPG)")
        for champ_name, value in sorted(stats.items(), key=lambda kv: kv[1]["dpg"], reverse=True):
            evolution_text = ""
            if champ_name == "KaiSa":
                # 실제 4코어 하위 조합식을 따라 진화까지 쓴 최소 누적 골드를 표시한다.
                cells = []
                for skill_name in ("q", "w", "e"):
                    gold = value.get(f"{skill_name}_evolution_gold")
                    gold_text = "불가" if gold is None else f"{gold}g"
                    cells.append(f"{skill_name.upper()}:{gold_text}")
                evolution_text = " | Evo " + " ".join(cells)
                evolution_text += (
                    f" | Sustain T{value.get('sustain_tier', 0)} "
                    f"LS{value.get('lifesteal_rate', 0.0) * 100.0:.1f}% "
                    f"OV{value.get('omnivamp_rate', 0.0) * 100.0:.1f}% "
                    f"Heal {value.get('healing_per_second', 0.0):.1f}/s"
                )
            print(
                f"  - {champ_name:<6} DPG {value['dpg']:.2f} | DPS {value['dps']:.1f} | "
                f"Gold {value['gold']} | 적 {value['target_count']}명 | Opt {value['choice']}"
                f"{evolution_text}"
            )
        print()
    return rows


def _build_compare_export_rows(rows, variant):
    """Flatten compare rows for file export and collect winner summaries."""
    flat_rows = []
    summary_rows = []
    for row in rows:
        winner = max(row["stats"].items(), key=lambda kv: kv[1]["dpg"])[0]
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
                "target_count": stat.get("target_count", 1),
                "winner": winner,
                "w_cast_count": stat.get("w_cast_count"),
                "q_evolved": stat.get("q_evolved"),
                "q_evolution_possible": stat.get("q_evolution_possible"),
                "q_evolution_gold": stat.get("q_evolution_gold"),
                "w_evolved": stat.get("w_evolved"),
                "w_evolution_possible": stat.get("w_evolution_possible"),
                "w_evolution_gold": stat.get("w_evolution_gold"),
                "e_evolved": stat.get("e_evolved"),
                "e_evolution_possible": stat.get("e_evolution_possible"),
                "e_evolution_gold": stat.get("e_evolution_gold"),
                "sustain_tier": stat.get("sustain_tier"),
                "lifesteal_rate": stat.get("lifesteal_rate"),
                "omnivamp_rate": stat.get("omnivamp_rate"),
                "lifesteal_healing": stat.get("lifesteal_healing"),
                "omnivamp_healing": stat.get("omnivamp_healing"),
                "total_healing": stat.get("total_healing"),
                "healing_per_second": stat.get("healing_per_second"),
                "botrk_lifesteal_damage": stat.get("botrk_lifesteal_damage"),
                "shoe": stat.get("shoe"),
                "rune": stat.get("rune"),
                "choice": stat.get("choice"),
            })
    return flat_rows, summary_rows


def _setup_korean_font():
    """Hangul 폰트를 지정해 한글 라벨이 □(두부)로 깨지지 않게 한다.

    matplotlib 기본 폰트(DejaVu Sans)는 한글 글리프가 없어 □ 로 렌더된다.
    OS별 후보 중 설치된 첫 폰트를 font.family 로 지정(없으면 무변경).
    음수 기호(−)가 □ 로 깨지는 것도 axes.unicode_minus=False 로 함께 보정.
    """
    from matplotlib import font_manager
    candidates = ["AppleGothic", "Apple SD Gothic Neo", "Malgun Gothic",
                  "NanumGothic", "Noto Sans CJK KR", "Noto Sans KR"]
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in available:
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False


def _plot_combined_compare(top1_rows, basic_rows):
    """Plot champion DPS curves for Top1 and Basic compare variants."""
    _setup_korean_font()
    champ_colors = {
        "Ashe": "#1f77b4",
        "Yunara": "#7b61ff",
        "KaiSa": "#e4572e",
        "Corki": "#2ca02c",
        "CogMaw": "#17becf",
        "Vayne": "#d62728",
        "Jinx": "#e377c2",
    }

    plt.figure(figsize=(13, 8))

    for rows, variant, linestyle, marker, alpha in [
        (top1_rows, "Top1", "-", "o", 0.95),
        (basic_rows, "Basic", "--", "s", 0.9),
    ]:
        for champ in ("Ashe", "Yunara", "KaiSa", "Corki", "CogMaw", "Vayne", "Jinx"):
            xs = [row["stats"][champ]["gold"] for row in rows]
            ys = [row["stats"][champ]["dps"] for row in rows]
            # 선택된 옵션(패키지 A/B 또는 코르키 도란) — variant 내 챔프당 고정이라 첫 행에서 취득
            choice = rows[0]["stats"][champ].get("choice", "") if rows else ""
            enemies = rows[0]["stats"][champ].get("target_count", 1) if rows else 1
            color = champ_colors[champ]
            plt.plot(
                xs, ys,
                color=color,
                linestyle=linestyle,
                marker=marker,
                markersize=5,
                linewidth=2.2 if variant == "Top1" else 1.9,
                alpha=alpha,
                label=f"{champ} {variant} ({choice}, 적{enemies}명)"
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
    print("[Info] Loading Yunara top1 from simulation_yunara 4-core ranking (단일 대상/tc=1 기준)...")
    yunara_top1 = get_yunara_4core_top1_build(target_count=1)
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

    corki_doran = DORAN_SHORT.get(corki_top1.get("doran"), "Blade")

    print("[Info] Loading Cog'Maw rune-agnostic best + meta build (LT·PtA 두 룬 전수 랭킹 — 시간 걸림)...")
    cogmaw_best, cogmaw_meta = get_cogmaw_powercompare_builds()
    print("[Info] Loading Vayne top1/meta from simulation_vayne (can take some time)...")
    vayne_best, vayne_meta = get_vayne_powercompare_builds()
    print("[Info] Loading Jinx top1/meta from simulation_jinx (can take some time)...")
    jinx_best, jinx_meta = get_jinx_powercompare_builds()

    print("\n=== Cross-Champion Power Compare (1~4 Core) ===")
    print("Configured Top1 builds (Ashe/Yunara/KaiSa: 정배 패키지 A=Bld+Zerk+핏빛길 / B=Bow+Glut+민첩함 중 최적):")
    print("  ※ 전 챔프 단일 대상(tc=1) 대칭 비교. (유나라 멀티타깃 가치는 모델 외 — 별도 고려)")
    print(
        f"- Ashe   : [{ashe_top1.get('pkg_label','?')}] {'-'.join(ashe_path)} / LT+CutDown "
        f"(Top1 from simulation_ashe, score {ashe_top1['score']:.2f})"
    )
    print(
        f"- Yunara : [{yunara_top1.get('pkg_label','?')}] {'-'.join(yunara_path)} / LT+CutDown (start Q active) "
        f"(Top1 from simulation_yunara @단일 대상/tc=1, score {yunara_top1['score']:.2f})"
    )
    print(
        f"- KaiSa  : [{kaisa_top1.get('pkg_label','?')}] {'-'.join(kaisa_path)} / LT+CutDown "
        f"(Top1 from simulation_kaisa, score {kaisa_top1['score']:.2f}; current KaiSa skill plan)"
    )
    print(
        f"- Corki  : Doran's {corki_doran} + {'-'.join(corki_path)} + {corki_shoe} / {corki_rune}+CutDown "
        f"(Top1 from simulation_corki, score {corki_top1['score']:.2f}; 패키지 제약 없음)"
    )
    print(
        f"- CogMaw : [{cogmaw_best.get('pkg_label','?')}] {'-'.join(cogmaw_best['path'])} / {cogmaw_best['rune_label']}+CutDown "
        f"(룬 무관 최강; LT·PtA 중 절대 weighted-DPS 우위)"
    )
    print(
        f"- Vayne  : [{vayne_best.get('pkg_label','?')}] {'-'.join(vayne_best['path'])} / {vayne_best['rune_label']}+CutDown "
        f"(룬 무관 최강; LT·PtA 중 절대 weighted-DPG 우위)"
    )
    print(
        f"- Jinx   : [{jinx_best.get('pkg_label','?')}] {'-'.join(jinx_best['path'])} / LT+CutDown "
        f"(long-range Fishbones + W nuke; top1 by weighted DPS)"
    )
    print()

    def _pkg_cfg(top1, extra=None):
        cfg = {
            "doran": top1.get("doran", "doranblade"),
            "boots": top1.get("boots", "berserker"),
            "rune_as": top1.get("rune_as", 0.0),
            "bloodline_lifesteal": top1.get("bloodline_lifesteal", 0.0),
            "pkg_label": top1.get("pkg_label", "Bld+Zerk"),
        }
        if "q_mode" in top1:
            cfg["q_mode"] = top1["q_mode"]
        if extra:
            cfg.update(extra)
        return cfg

    top1_configs = {
        "Ashe": {"path": ashe_path, **_pkg_cfg(ashe_top1)},
        # 유나라도 단일 대상(tc=1) 기준 — 전 챔프 대칭 비교(멀티타깃 가치는 모델 외).
        "Yunara": {"path": yunara_path, **_pkg_cfg(yunara_top1)},
        "KaiSa": {"path": kaisa_path, **_pkg_cfg(kaisa_top1)},
        "Corki": {"path": corki_path, "shoe": corki_shoe, "rune": corki_rune, "doran": corki_top1.get("doran", "doranblade")},
        # 코그모 = 룬 무관 최강 빌드(LT·PtA 중 우위)
        "CogMaw": {"path": cogmaw_best["path"],
                   **_pkg_cfg(cogmaw_best, {"keystone_cls": cogmaw_best["keystone_cls"], "rune_label": cogmaw_best["rune_label"]})},
        # 베인 = 룬 무관 최강 빌드(LT·PtA 중 우위)
        "Vayne": {"path": vayne_best["path"],
                  **_pkg_cfg(vayne_best, {"keystone_cls": vayne_best["keystone_cls"], "rune_label": vayne_best["rune_label"]})},
        # 징크스 = 장거리 Fishbones 조건의 절대 weighted-DPS top1; Get Excited OFF
        "Jinx": {"path": jinx_best["path"], **_pkg_cfg(jinx_best)},
    }
    top1_rows = _print_compare_section("Cross-Champion Top1 Compare (1~4 Core)", top1_configs)

    kaisa_basic_path = kaisa_top1.get("control_path", ("kraken", "guinsoo", "nashor", "terminus"))
    corki_basic_path = ("trinity", "muramana", "collector", "ie")
    corki_basic_shoe = "plated"
    corki_basic_rune = "conq"

    ashe_basic_path = ("kraken", "pd", "ie", "ldr")
    yunara_basic_path = ("kraken", "pd", "ie", "ldr")
    # basic 빌드도 개별 파일처럼 정배 A/B 중 최적 패키지로 평가(개별 sim 컨트롤과 일치). Corki/CogMaw 는 자체 패키지.
    basic_configs = {
        "Ashe": {"path": ashe_basic_path, **_best_pkg_cfg("Ashe", ashe_basic_path)},
        "Yunara": {"path": yunara_basic_path, **_best_pkg_cfg("Yunara", yunara_basic_path)},
        "KaiSa": {"path": kaisa_basic_path, **_best_pkg_cfg("KaiSa", kaisa_basic_path)},
        "Corki": {"path": corki_basic_path, "shoe": corki_basic_shoe, "rune": corki_basic_rune},
        # 코그모 = 실전 메타 빌드(guinsoo-navori-terminus-wit) under 치속(LethalTempo)
        "CogMaw": {"path": cogmaw_meta["path"],
                   **_pkg_cfg(cogmaw_meta, {"keystone_cls": cogmaw_meta["keystone_cls"], "rune_label": cogmaw_meta["rune_label"]})},
        # 베인 = 컨트롤(botrk-guinsoo-terminus-pd, 최적 패키지) under 치속(LethalTempo)
        "Vayne": {"path": vayne_meta["path"],
                  **_pkg_cfg(vayne_meta, {"keystone_cls": vayne_meta["keystone_cls"], "rune_label": vayne_meta["rune_label"]})},
        # 징크스 = Fishbones 컨트롤(kraken-pd-ie-ldr, DPS 최적 패키지)
        "Jinx": {"path": jinx_meta["path"], **_pkg_cfg(jinx_meta)},
    }

    print("Configured Basic builds (Ashe/Yunara/KaiSa: 정배 A/B 중 최적 — 개별 파일 기준과 일치):")
    for _c in ("Ashe", "Yunara", "KaiSa"):
        _cfg = basic_configs[_c]
        _note = " (start Q active)" if _c == "Yunara" else ""
        print(f"- {_c:<6} : [{_cfg.get('pkg_label','?')}] {'-'.join(_cfg['path'])} + {_cfg.get('boots','berserker')} / LT+CutDown{_note}")
    print(f"- Corki  : {'-'.join(corki_basic_path)} + {corki_basic_shoe} / {corki_basic_rune}+CutDown (requested base build)")
    print(f"- CogMaw : {'-'.join(cogmaw_meta['path'])} + {cogmaw_meta.get('boots','glutton')} / {cogmaw_meta['rune_label']}+CutDown (실전 메타 빌드 / 치속)")
    print(f"- Vayne  : [{vayne_meta.get('pkg_label','?')}] {'-'.join(vayne_meta['path'])} + {vayne_meta.get('boots','berserker')} / {vayne_meta['rune_label']}+CutDown (control botrk-guinsoo-terminus-pd)")
    print(f"- Jinx   : [{jinx_meta.get('pkg_label','?')}] {'-'.join(jinx_meta['path'])} + {jinx_meta.get('boots','berserker')} / LT+CutDown (Fishbones control kraken-pd-ie-ldr)")
    print()
    basic_rows = _print_compare_section("Cross-Champion Basic Build Compare (1~4 Core)", basic_configs)

    for report_path in export_compare_reports(top1_rows, basic_rows):
        print(f"[Info] Saved champion comparison report: {report_path}")
    _plot_combined_compare(top1_rows, basic_rows)


if __name__ == "__main__":
    compare_builds()
