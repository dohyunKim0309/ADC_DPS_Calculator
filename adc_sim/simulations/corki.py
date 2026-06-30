from adc_sim.champion import Corki, Target
from adc_sim.items import (
    Manamune,
    TrinityForce,
    StatikkShiv,
    KrakenSlayer,
    GuinsoosRageblade,
    Stormrazor,
    EssenceReaver,
    InfinityEdge,
    TheCollector,
    YunTalWildarrows,
    BladeOfRuinedKing,
    Bloodthirster,
    Terminus,
    LordDominiksRegards,
    MortalReminder,
    PhantomDancer,
    RunaansHurricane,
    ImmortalShieldbow,
    RapidFirecannon,
    Plated_Steelcaps,
    BerserkerGreaves,
)
from adc_sim.engine import run_simulation
from adc_sim.runes import Conqueror, LethalTempo, CutDown
import matplotlib.pyplot as plt
import random


CORE_TARGET_STATS = {
    1: {"hp": 1700, "armor": 50, "mr": 25},
    2: {"hp": 1900, "armor": 70, "mr": 30},
    3: {"hp": 2400, "armor": 100, "mr": 50},
    4: {"hp": 2600, "armor": 120, "mr": 70},
    5: {"hp": 3000, "armor": 150, "mr": 90},
}

CORE_LEVELS = {
    1: {"level": 9},
    2: {"level": 11},
    3: {"level": 13},
    4: {"level": 15},
    5: {"level": 17},
}

# 코어별 스킬 레벨 (요청값)
CORKI_SKILL_LEVELS = {
    1: {"q": 3, "e": 1, "r": 1},
    2: {"q": 4, "e": 2, "r": 1},
    3: {"q": 4, "e": 3, "r": 2},
    4: {"q": 5, "e": 4, "r": 2},
    5: {"q": 5, "e": 5, "r": 3},
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
# 윤탈 기본 crit: 과거 corki 는 0.05 였으나, 데미지 경로는 항상 명시적 crit 을 전달하므로
# 통합 기본값(0.25)으로 합쳐도 결과 불변(검증됨).
from adc_sim.data.items_registry import create_item_from_key
from adc_sim.data.items_data import DORAN_OPTIONS, DORAN_SHORT


def short_name(item_key):
    mapping = {
        "muramana": "Mura",
        "trinity": "Tri",
        "statikk": "Statikk",
        "kraken": "Krk",
        "guinsoo": "Gui",
        "storm": "Storm",
        "essence": "ER",
        "ie": "IE",
        "collector": "Collector",
        "yuntal": "Yun",
        "botrk": "BotRK",
        "bt": "BT",
        "terminus": "Terminus",
        "ldr": "LDR",
        "mortal": "Mortal",
        "pd": "PD",
        "runaan": "Runaan",
        "shieldbow": "Shieldbow",
        "rfc": "RFC",
        "plated": "Plated",
        "berserker": "Berserker",
    }
    return mapping[item_key]


def create_rune_from_key(rune_key):
    if rune_key == "conq":
        return Conqueror()
    if rune_key == "lt":
        return LethalTempo()
    raise ValueError(f"Unknown rune key: {rune_key}")


def rune_short(rune_key):
    if rune_key == "conq":
        return "Conq"
    if rune_key == "lt":
        return "LT"
    return rune_key


def simulate_corki_core_path(full_path, shoe_key, rune_key, core_tier, include_w=True, doran_key=None):
    """Simulate Corki DPS and total gold for the configured shoe/rune/path."""
    target = build_target_for_core(core_tier)
    level_cfg = CORE_LEVELS[core_tier]
    skill_cfg = CORKI_SKILL_LEVELS[core_tier]

    corki = Corki(
        level=level_cfg["level"],
        q_level=skill_cfg["q"],
        e_level=skill_cfg["e"],
        r_level=skill_cfg["r"],
    )
    corki.set_rune(create_rune_from_key(rune_key))
    corki.set_sub_rune(CutDown())

    doran_items = [create_item_from_key(doran_key)] if doran_key else []
    items = doran_items + [create_item_from_key(shoe_key)]
    for idx, key in enumerate(full_path[:core_tier], start=1):
        if key == "yuntal":
            # 윤탈 규칙:
            # 구매 코어 타이밍에는 5%, 그 다음 코어부터 25%
            crit = 0.05 if idx == core_tier else 0.25
            items.append(create_item_from_key(key, yuntal_crit=crit))
        else:
            items.append(create_item_from_key(key))

    total_cost = 0
    for item in items:
        total_cost += item.cost
        corki.add_item(item)

    # 스킬 시나리오를 simulation에서 정의하고 engine가 처리
    if include_w:
        skill_plan = {
            "manual_casts": [(0.0, "e"), (0.0, "q"), (0.0, "w"), (1.5, "r")],
            "auto_cast": {"e": True, "q": True, "w": True, "r": True},
            "auto_order": ["e", "q", "w", "r"],
        }
    else:
        # 챔피언 간 비교에서는 W(발키리 트레일) 제외
        skill_plan = {
            "manual_casts": [(0.0, "e"), (0.0, "q"), (1.5, "r")],
            "auto_cast": {"e": True, "q": True, "w": False, "r": True},
            "auto_order": ["e", "q", "r"],
        }

    _, dps, _ = run_simulation(corki, target, verbose=False, skill_plan=skill_plan, respawn_to_full_kills=2)
    return dps, total_cost


def build_corki_core_report_meta(full_path, shoe_key, rune_key, core_tier):
    """Build serializable metadata for Corki report rows."""
    active_path = tuple(full_path[:core_tier])
    return {
        "champion": "Corki",
        "core_tier": core_tier,
        "full_path": list(full_path),
        "active_path": list(active_path),
        "build": "-".join(full_path),
        "active_build": "-".join(active_path),
        "shoe": shoe_key,
        "rune": rune_key,
    }


def get_corki_4core_top1_build():
    """현재 simulation_corki 랭킹 기준(4코어, 5:4:3:3) top1 빌드 반환."""
    core12_candidates = [
        "muramana", "trinity", "statikk", "kraken", "guinsoo", "storm",
        "essence", "ie", "collector", "yuntal", "botrk", "terminus",
    ]
    core3_candidates = [
        "ldr", "ie", "mortal", "statikk", "pd", "runaan", "guinsoo", "terminus",
        "botrk", "essence", "trinity", "muramana", "kraken", "shieldbow",
        "collector", "rfc", "storm", "yuntal",
    ]
    core4_candidates = ["ie", "ldr", "botrk", "bt", "kraken", "yuntal", "storm", "essence", "trinity", "statikk"]
    shoe_candidates = ["plated", "berserker"]
    rune_candidates = ["conq", "lt"]
    pen_exclusive = {"terminus", "ldr", "mortal"}

    control_path = ("trinity", "muramana", "collector", "ldr")
    control_shoe = "plated"
    control_rune = "conq"

    results = []
    sim_cache = {}

    def sim_cached(path, shoe, rune_key, core_tier, doran):
        key = (tuple(path[:core_tier]), shoe, rune_key, core_tier, doran)
        if key not in sim_cache:
            sim_cache[key] = simulate_corki_core_path(path, shoe, rune_key, core_tier, include_w=False, doran_key=doran)
        return sim_cache[key]

    for rune_key in rune_candidates:
        for shoe in shoe_candidates:
            for doran in DORAN_OPTIONS:
                for c1 in core12_candidates:
                    for c2 in core12_candidates:
                        if c1 == c2:
                            continue
                        if {"trinity", "essence"} == {c1, c2}:
                            continue
                        for c3 in core3_candidates:
                            if c3 in (c1, c2):
                                continue
                            for c4 in core4_candidates:
                                if c4 in (c1, c2, c3):
                                    continue
                                if "trinity" in (c1, c2, c3, c4) and "essence" in (c1, c2, c3, c4):
                                    continue
                                pen_count = sum(1 for k in (c1, c2, c3, c4) if k in pen_exclusive)
                                if pen_count > 1:
                                    continue

                                path = (c1, c2, c3, c4)
                                dps1, cost1 = sim_cached(path, shoe, rune_key, 1, doran)
                                dps2, cost2 = sim_cached(path, shoe, rune_key, 2, doran)
                                dps3, cost3 = sim_cached(path, shoe, rune_key, 3, doran)
                                dps4, cost4 = sim_cached(path, shoe, rune_key, 4, doran)

                                dpg1 = dps1 / (cost1 / 1000.0) if cost1 > 0 else 0.0
                                dpg2 = dps2 / (cost2 / 1000.0) if cost2 > 0 else 0.0
                                dpg3 = dps3 / (cost3 / 1000.0) if cost3 > 0 else 0.0
                                dpg4 = dps4 / (cost4 / 1000.0) if cost4 > 0 else 0.0

                                results.append({
                                    "path": path,
                                    "shoe": shoe,
                                    "rune": rune_key,
                                    "doran": doran,
                                    "dps": [dps1, dps2, dps3, dps4],
                                    "cost": [cost1, cost2, cost3, cost4],
                                    "dpg": [dpg1, dpg2, dpg3, dpg4],
                                    "is_control": (path == control_path and shoe == control_shoe and rune_key == control_rune),
                                })

    w = [5.0, 4.0, 3.0, 3.0]
    wsum = sum(w)

    # 컨트롤도 도란검/도란활 중 가중 DPG 최대를 baseline 으로
    control_candidates = [r for r in results if r["is_control"]]
    if not control_candidates:
        raise RuntimeError("Control build not found for Corki 4-core ranking.")
    control_row = max(control_candidates, key=lambda r: sum(w[i] * r["dpg"][i] for i in range(4)))

    ctrl = control_row["dpg"]
    for r in results:
        rel = []
        for i in range(4):
            base = ctrl[i]
            rel.append(((r["dpg"][i] / base) * 100.0 - 100.0) if base > 0 else 0.0)
        r["rel_dpg_core"] = rel
        r["score"] = sum(w[i] * rel[i] for i in range(4)) / wsum

    ranked = sorted(results, key=lambda r: r["score"], reverse=True)
    return ranked[0]


if __name__ == "__main__":
    print("\n=== Corki 4-Core Efficiency (DPG vs Control, 5:4:3:3) ===")

    core12_candidates = [
        "muramana", "trinity", "statikk", "kraken", "guinsoo", "storm",
        "essence", "ie", "collector", "yuntal", "botrk", "terminus",
    ]
    core3_candidates = [
        "ldr", "ie", "mortal", "statikk", "pd", "runaan", "guinsoo", "terminus",
        "botrk", "essence", "trinity", "muramana", "kraken", "shieldbow",
        "collector",
        "rfc", "storm", "yuntal",
    ]
    core4_candidates = ["ie", "ldr", "botrk", "bt", "kraken", "yuntal", "storm", "essence", "trinity", "statikk"]
    shoe_candidates = ["plated", "berserker"]
    rune_candidates = ["conq", "lt"]
    pen_exclusive = {"terminus", "ldr", "mortal"}

    # 대조군: 트포-무라마나-징수-LDR + 판금 + 정복자/체력차극복
    control_path = ("trinity", "muramana", "collector", "ldr")
    control_shoe = "plated"
    control_rune = "conq"

    results = []
    for rune_key in rune_candidates:
        for shoe in shoe_candidates:
            for c1 in core12_candidates:
                for c2 in core12_candidates:
                    if c1 == c2:
                        continue
                    # 트포와 정수는 동시 구매 불가 (3코어 포함)
                    if {"trinity", "essence"} == {c1, c2}:
                        continue
                    for c3 in core3_candidates:
                        if c3 in (c1, c2):
                            continue
                        for c4 in core4_candidates:
                            if c4 in (c1, c2, c3):
                                continue
                            # 트포와 정수는 동시 구매 불가
                            if "trinity" in (c1, c2, c3, c4) and "essence" in (c1, c2, c3, c4):
                                continue
                            # 경계/LDR/필멸자는 셋 중 하나만
                            pen_count = sum(1 for k in (c1, c2, c3, c4) if k in pen_exclusive)
                            if pen_count > 1:
                                continue

                            for doran in DORAN_OPTIONS:
                                path = (c1, c2, c3, c4)
                                # W(발키리)는 즉발 5틱 버스트가 kill_time 기반 DPS를 왜곡(3C<2C)시켜 랭킹에서 제외
                                dps1, cost1 = simulate_corki_core_path(path, shoe, rune_key, 1, include_w=False, doran_key=doran)
                                dps2, cost2 = simulate_corki_core_path(path, shoe, rune_key, 2, include_w=False, doran_key=doran)
                                dps3, cost3 = simulate_corki_core_path(path, shoe, rune_key, 3, include_w=False, doran_key=doran)
                                dps4, cost4 = simulate_corki_core_path(path, shoe, rune_key, 4, include_w=False, doran_key=doran)

                                label = (
                                    f"{short_name(c1)}-{short_name(c2)}-{short_name(c3)}-{short_name(c4)}-"
                                    f"{short_name(shoe)}-{rune_short(rune_key)} [{DORAN_SHORT[doran]}]"
                                )
                                is_control = (
                                    path == control_path and shoe == control_shoe and rune_key == control_rune
                                )

                                dpg1 = dps1 / (cost1 / 1000.0) if cost1 > 0 else 0.0
                                dpg2 = dps2 / (cost2 / 1000.0) if cost2 > 0 else 0.0
                                dpg3 = dps3 / (cost3 / 1000.0) if cost3 > 0 else 0.0
                                dpg4 = dps4 / (cost4 / 1000.0) if cost4 > 0 else 0.0

                                results.append({
                                    "path": path,
                                    "shoe": shoe,
                                    "rune": rune_key,
                                    "doran": doran,
                                    "label": label,
                                    "x": [cost1, cost2, cost3, cost4],
                                    "y": [dps1, dps2, dps3, dps4],
                                    "dpg": [dpg1, dpg2, dpg3, dpg4],
                                    "is_control": is_control,
                                })

    w1, w2, w3, w4 = 5.0, 4.0, 3.0, 3.0
    wsum = w1 + w2 + w3 + w4

    # 컨트롤도 도란검/도란활 중 가중 DPG 최대를 baseline 으로
    control_candidates = [r for r in results if r["is_control"]]
    if not control_candidates:
        raise RuntimeError("Control build not found.")
    control_row = max(
        control_candidates,
        key=lambda r: (w1 * r["dpg"][0] + w2 * r["dpg"][1] + w3 * r["dpg"][2] + w4 * r["dpg"][3]),
    )

    ctrl_dpg1, ctrl_dpg2, ctrl_dpg3, ctrl_dpg4 = control_row["dpg"]

    for r in results:
        rel1 = ((r["dpg"][0] / ctrl_dpg1) * 100.0 - 100.0) if ctrl_dpg1 > 0 else 0.0
        rel2 = ((r["dpg"][1] / ctrl_dpg2) * 100.0 - 100.0) if ctrl_dpg2 > 0 else 0.0
        rel3 = ((r["dpg"][2] / ctrl_dpg3) * 100.0 - 100.0) if ctrl_dpg3 > 0 else 0.0
        rel4 = ((r["dpg"][3] / ctrl_dpg4) * 100.0 - 100.0) if ctrl_dpg4 > 0 else 0.0
        r["rel_dpg_core"] = [rel1, rel2, rel3, rel4]
        r["score"] = ((w1 * rel1) + (w2 * rel2) + (w3 * rel3) + (w4 * rel4)) / wsum

    ranked = sorted(results, key=lambda r: r["score"], reverse=True)

    print(
        f"Control: {control_row['label']} | "
        f"1C DPG {ctrl_dpg1:.2f}, 2C DPG {ctrl_dpg2:.2f}, 3C DPG {ctrl_dpg3:.2f}, 4C DPG {ctrl_dpg4:.2f}"
    )
    print(
        "\nTop 50 (rank by weighted relative DPG, 5:4:3:3)\n"
        "RK | BUILD                                                    | 1C DPS/ΔDPG% | 2C DPS/ΔDPG% | 3C DPS/ΔDPG% | 4C DPS/ΔDPG% | SCORE"
    )
    print("-" * 152)

    top_n = min(50, len(ranked))
    output_rows = ranked[:top_n]
    if not any(r["is_control"] for r in output_rows):
        output_rows.append(control_row)

    for i, r in enumerate(output_rows, start=1):
        y1, y2, y3, y4v = r["y"]
        d1, d2, d3, d4v = r["rel_dpg_core"]
        ctrl_tag = " [CTRL]" if r["is_control"] else ""
        c1 = f"{y1:.1f}/{d1:+.1f}%"
        c2 = f"{y2:.1f}/{d2:+.1f}%"
        c3 = f"{y3:.1f}/{d3:+.1f}%"
        c4 = f"{y4v:.1f}/{d4v:+.1f}%"
        print(f"{i:>2} | {(r['label'] + ctrl_tag):<56} | {c1:>12} | {c2:>12} | {c3:>12} | {c4:>12} | {r['score']:>6.2f}")

    # 요청 빌드 별도 출력
    wanted = next(
        (
            r for r in results
            if r["path"][:3] == ("trinity", "muramana", "ldr")
            and r["shoe"] == "plated"
            and r["rune"] == "conq"
        ),
        None,
    )
    wanted_alt = next(
        (
            r for r in results
            if r["path"][:3] == ("trinity", "muramana", "ldr")
            and r["shoe"] == "berserker"
            and r["rune"] == "conq"
        ),
        None,
    )
    if wanted:
        w1r, w2r, w3r, w4r = wanted["rel_dpg_core"]
        wy1, wy2, wy3, wy4 = wanted["y"]
        print("\nRequested Build:")
        print(
            f"{wanted['label']} | "
            f"1C {wy1:.1f}/{w1r:+.1f}% | "
            f"2C {wy2:.1f}/{w2r:+.1f}% | "
            f"3C {wy3:.1f}/{w3r:+.1f}% | "
            f"4C {wy4:.1f}/{w4r:+.1f}% | SCORE {wanted['score']:.2f}"
        )
    if wanted_alt:
        w1r, w2r, w3r, w4r = wanted_alt["rel_dpg_core"]
        wy1, wy2, wy3, wy4 = wanted_alt["y"]
        print(
            f"{wanted_alt['label']} | "
            f"1C {wy1:.1f}/{w1r:+.1f}% | "
            f"2C {wy2:.1f}/{w2r:+.1f}% | "
            f"3C {wy3:.1f}/{w3r:+.1f}% | "
            f"4C {wy4:.1f}/{w4r:+.1f}% | SCORE {wanted_alt['score']:.2f}"
        )

    # 그래프: x=투자 골드, y=DPS (상위5개 컬러 강조 + 나머지 흐릿)
    top5 = ranked[:5]
    top5_keys = {(r["path"], r["shoe"], r["rune"]) for r in top5}

    plt.figure(figsize=(13, 8))

    # 전체 빌드(흐릿) 중 5%만 랜덤 샘플링
    non_top_rows = []
    for r in ranked:
        key = (r["path"], r["shoe"], r["rune"])
        if key in top5_keys:
            continue
        non_top_rows.append(r)

    rng = random.Random(42)
    sample_count = max(1, int(len(non_top_rows) * 0.05))
    sampled_non_top = rng.sample(non_top_rows, sample_count) if non_top_rows else []

    for r in sampled_non_top:
        plt.plot(
            r["x"], r["y"],
            color="#A0A0A0",
            alpha=0.18,
            linewidth=1.0,
            marker="o",
            markersize=3,
            zorder=1,
        )

    # 상위 5개(강조)
    top_colors = ["#E4572E", "#4C78A8", "#54A24B", "#F3A712", "#B279A2"]
    for i, r in enumerate(top5):
        color = top_colors[i % len(top_colors)]
        plt.plot(
            r["x"], r["y"],
            color=color,
            linewidth=2.8,
            marker="D",
            markersize=6,
            zorder=3,
            label=f"Top{i+1} {r['label']} (Score {r['score']:.2f})"
        )

    # 대조군도 함께 표시
    plt.plot(
        control_row["x"], control_row["y"],
        color="#111111",
        linewidth=2.6,
        marker="s",
        markersize=7,
        linestyle="--",
        zorder=4,
        label=f"CTRL {control_row['label']}"
    )

    # 요청 빌드 강조
    if wanted is not None:
        plt.plot(
            wanted["x"], wanted["y"],
            color="#0F9D58",
            linewidth=2.6,
            marker="^",
            markersize=7,
            linestyle="-.",
            zorder=4,
            label=f"Requested {wanted['label']} (Score {wanted['score']:.2f})"
        )
    if wanted_alt is not None:
        plt.plot(
            wanted_alt["x"], wanted_alt["y"],
            color="#1B5E20",
            linewidth=2.6,
            marker="v",
            markersize=7,
            linestyle=":",
            zorder=4,
            label=f"Requested {wanted_alt['label']} (Score {wanted_alt['score']:.2f})"
        )

    # 상위 5개 점 라벨 겹침 완화 (코어별 분산 오프셋)
    label_points_by_core = {0: [], 1: [], 2: [], 3: []}
    for i, r in enumerate(top5):
        color = top_colors[i % len(top_colors)]
        for ci in range(4):
            label_points_by_core[ci].append({
                "x": r["x"][ci],
                "y": r["y"][ci],
                "text": f"{r['y'][ci]:.0f}",
                "color": color,
            })

    for core_idx, pts in label_points_by_core.items():
        pts_sorted = sorted(pts, key=lambda p: p["y"])
        n = len(pts_sorted)
        for j, p in enumerate(pts_sorted):
            # 가운데 기준으로 위/아래 분산
            y_off = (j - (n - 1) / 2.0) * 12.0
            x_off = -12 if core_idx == 0 else (8 if core_idx == 1 else (12 if core_idx == 2 else 14))
            plt.annotate(
                p["text"],
                (p["x"], p["y"]),
                textcoords="offset points",
                xytext=(x_off, y_off),
                fontsize=8,
                color=p["color"],
                fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.75),
                zorder=5,
            )

    plt.title("Corki 4-Core DPS Power Spike (Top5 Highlighted)")
    plt.xlabel("Invested Gold")
    plt.ylabel("DPS")
    plt.grid(True, alpha=0.25)
    plt.legend(loc="best", fontsize=8)
    plt.tight_layout()
    plt.show()
