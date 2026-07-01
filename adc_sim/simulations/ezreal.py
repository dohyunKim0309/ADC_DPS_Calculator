from adc_sim.champion import Ezreal, Target
from adc_sim.engine import run_simulation
from adc_sim.runes import Conqueror, LethalTempo, CutDown
from adc_sim.settings import CORE_WEIGHTS_RAW, CORE_WEIGHTS_LABEL
from adc_sim.data.items_registry import create_item_from_key
from adc_sim.data.items_data import DORAN_OPTIONS, DORAN_SHORT
import matplotlib.pyplot as plt
import random


CORE_TARGET_STATS = {
    1: {"hp": 1700, "armor": 50, "mr": 25},
    2: {"hp": 1900, "armor": 70, "mr": 30},
    3: {"hp": 2400, "armor": 100, "mr": 50},
    4: {"hp": 2600, "armor": 120, "mr": 70},
}

CORE_LEVELS = {1: {"level": 9}, 2: {"level": 11}, 3: {"level": 13}, 4: {"level": 15}}

# Q 선마(코어별 스킬 레벨). R은 v1 미사용(데미지 제외)이라 r_level은 표기상 의미만. [H, 튜닝 가능]
EZREAL_SKILL_LEVELS = {
    1: {"q": 5, "w": 2, "e": 1, "r": 1},
    2: {"q": 5, "w": 4, "e": 1, "r": 2},
    3: {"q": 5, "w": 5, "e": 2, "r": 2},
    4: {"q": 5, "w": 5, "e": 4, "r": 3},
}


def build_target_for_core(core_tier):
    s = CORE_TARGET_STATS[core_tier]
    return Target(hp=s["hp"], armor=s["armor"], magic_resist=s["mr"], bonus_hp=max(0, s["hp"] - 1500))


def short_name(item_key):
    mapping = {
        "muramana": "Mura", "trinity": "Tri", "statikk": "Statikk", "kraken": "Krk",
        "guinsoo": "Gui", "storm": "Storm", "essence": "ER", "ie": "IE",
        "collector": "Collector", "yuntal": "Yun", "botrk": "BotRK", "bt": "BT",
        "terminus": "Terminus", "ldr": "LDR", "mortal": "Mortal", "pd": "PD",
        "runaan": "Runaan", "shieldbow": "Shieldbow", "rfc": "RFC", "nashor": "Nashor",
        "plated": "Plated", "berserker": "Berserker",
    }
    return mapping.get(item_key, item_key)


def create_rune_from_key(rune_key):
    if rune_key == "conq":
        return Conqueror()
    if rune_key == "lt":
        return LethalTempo()
    raise ValueError(f"Unknown rune key: {rune_key}")


def rune_short(rune_key):
    return {"conq": "Conq", "lt": "LT"}.get(rune_key, rune_key)


def simulate_ezreal_core_path(full_path, shoe_key, rune_key, core_tier, include_we=True, doran_key=None):
    """이즈리얼 DPS·총골드 시뮬. include_we=False면 랭킹용으로 W/E 데미지 제외."""
    target = build_target_for_core(core_tier)
    level_cfg = CORE_LEVELS[core_tier]
    skill_cfg = EZREAL_SKILL_LEVELS[core_tier]

    ez = Ezreal(level=level_cfg["level"], q_level=skill_cfg["q"], w_level=skill_cfg["w"],
                e_level=skill_cfg["e"], r_level=skill_cfg["r"])
    ez.set_rune(create_rune_from_key(rune_key))
    ez.set_sub_rune(CutDown())

    doran_items = [create_item_from_key(doran_key)] if doran_key else []
    items = doran_items + [create_item_from_key(shoe_key)]
    for idx, key in enumerate(full_path[:core_tier], start=1):
        if key == "yuntal":
            crit = 0.05 if idx == core_tier else 0.25
            items.append(create_item_from_key(key, yuntal_crit=crit))
        else:
            items.append(create_item_from_key(key))

    total_cost = 0
    for item in items:
        total_cost += item.cost
        ez.add_item(item)

    if include_we:
        skill_plan = {
            "manual_casts": [(0.0, "q"), (0.0, "w"), (0.0, "e")],
            "auto_cast": {"q": True, "w": True, "e": True},
            "auto_order": ["q", "w", "e"],
        }
    else:
        # 챔피언 간/랭킹 비교에서 W/E 버스트가 kill-time DPS를 왜곡하면 제외
        skill_plan = {
            "manual_casts": [(0.0, "q")],
            "auto_cast": {"q": True, "w": False, "e": False},
            "auto_order": ["q"],
        }

    _, dps, _ = run_simulation(ez, target, verbose=False, skill_plan=skill_plan, respawn_to_full_kills=2)
    return dps, total_cost


# --- 탐색 후보 풀(Corki AD-캐리 풀 재사용; Q 비치명이라 크리는 평타에만 이득 → 랭킹이 반영) ---
CORE12_CANDIDATES = ["muramana", "trinity", "statikk", "kraken", "guinsoo", "storm",
                     "essence", "ie", "collector", "yuntal", "botrk", "terminus"]
CORE3_CANDIDATES = ["ldr", "ie", "mortal", "statikk", "pd", "runaan", "guinsoo", "terminus",
                    "botrk", "essence", "trinity", "muramana", "kraken", "shieldbow",
                    "collector", "rfc", "storm", "yuntal", "nashor"]
CORE4_CANDIDATES = ["ie", "ldr", "botrk", "bt", "kraken", "yuntal", "storm", "essence",
                    "trinity", "statikk", "nashor"]
SHOE_CANDIDATES = ["plated", "berserker"]
RUNE_CANDIDATES = ["conq", "lt"]
PEN_EXCLUSIVE = {"terminus", "ldr", "mortal"}

CONTROL_PATH = ("trinity", "muramana", "ie", "ldr")
CONTROL_SHOE = "berserker"
CONTROL_RUNE = "lt"


def _iter_paths():
    """유효 4코어 경로 생성(중복/상호배제 규칙 적용)."""
    for c1 in CORE12_CANDIDATES:
        for c2 in CORE12_CANDIDATES:
            if c1 == c2:
                continue
            if {"trinity", "essence"} == {c1, c2}:
                continue
            for c3 in CORE3_CANDIDATES:
                if c3 in (c1, c2):
                    continue
                for c4 in CORE4_CANDIDATES:
                    if c4 in (c1, c2, c3):
                        continue
                    quad = (c1, c2, c3, c4)
                    if "trinity" in quad and "essence" in quad:
                        continue
                    if sum(1 for k in quad if k in PEN_EXCLUSIVE) > 1:
                        continue
                    yield quad


# 참고: get_ezreal_4core_top1_build 는 power_compare 연계가 범위에 들어올 때
# corki.get_corki_4core_top1_build 패턴(prefix sim 캐시)으로 추가한다. v1은 YAGNI로 제외.


if __name__ == "__main__":
    print(f"\n=== Ezreal 4-Core Efficiency (DPG vs Control, {CORE_WEIGHTS_LABEL}, W/E 제외) ===")
    w1, w2, w3, w4 = CORE_WEIGHTS_RAW
    wsum = w1 + w2 + w3 + w4
    results = []
    for rune_key in RUNE_CANDIDATES:
        for shoe in SHOE_CANDIDATES:
            for doran in DORAN_OPTIONS:
                for path in _iter_paths():
                    ys = []
                    xs = []
                    dpg = []
                    for tier in (1, 2, 3, 4):
                        dps, cost = simulate_ezreal_core_path(path, shoe, rune_key, tier, include_we=False, doran_key=doran)
                        ys.append(dps); xs.append(cost)
                        dpg.append(dps / (cost / 1000.0) if cost > 0 else 0.0)
                    label = (f"{short_name(path[0])}-{short_name(path[1])}-{short_name(path[2])}-{short_name(path[3])}-"
                             f"{short_name(shoe)}-{rune_short(rune_key)} [{DORAN_SHORT[doran]}]")
                    results.append({
                        "path": path, "shoe": shoe, "rune": rune_key, "doran": doran, "label": label,
                        "x": xs, "y": ys, "dpg": dpg,
                        "is_control": (path == CONTROL_PATH and shoe == CONTROL_SHOE and rune_key == CONTROL_RUNE),
                    })

    control_candidates = [r for r in results if r["is_control"]]
    if not control_candidates:
        raise RuntimeError("Control build not found.")
    control_row = max(control_candidates, key=lambda r: (w1 * r["dpg"][0] + w2 * r["dpg"][1] + w3 * r["dpg"][2] + w4 * r["dpg"][3]))
    cd = control_row["dpg"]

    for r in results:
        rel = [((r["dpg"][i] / cd[i]) * 100.0 - 100.0) if cd[i] > 0 else 0.0 for i in range(4)]
        r["rel_dpg_core"] = rel
        r["score"] = ((w1 * rel[0]) + (w2 * rel[1]) + (w3 * rel[2]) + (w4 * rel[3])) / wsum

    ranked = sorted(results, key=lambda r: r["score"], reverse=True)
    print(f"Control: {control_row['label']} | "
          f"1C {cd[0]:.2f}, 2C {cd[1]:.2f}, 3C {cd[2]:.2f}, 4C {cd[3]:.2f} DPG")
    print(f"\nTop 30 (rank by weighted relative DPG, {CORE_WEIGHTS_LABEL})")
    print("RK | BUILD                                                    | 1C DPS/ΔDPG% | 2C | 3C | 4C | SCORE")
    print("-" * 140)
    top_n = min(30, len(ranked))
    rows = ranked[:top_n]
    if not any(r["is_control"] for r in rows):
        rows.append(control_row)
    for i, r in enumerate(rows, start=1):
        y = r["y"]; d = r["rel_dpg_core"]
        tag = " [CTRL]" if r["is_control"] else ""
        cells = " | ".join(f"{y[k]:.0f}/{d[k]:+.1f}%" for k in range(4))
        print(f"{i:>2} | {(r['label'] + tag):<56} | {cells} | {r['score']:>6.2f}")

    # 그래프(상위5 강조 + 일부 샘플)
    top5 = ranked[:5]
    top5_keys = {(r["path"], r["shoe"], r["rune"]) for r in top5}
    plt.figure(figsize=(13, 8))
    non_top = [r for r in ranked if (r["path"], r["shoe"], r["rune"]) not in top5_keys]
    rng = random.Random(42)
    for r in (rng.sample(non_top, max(1, int(len(non_top) * 0.05))) if non_top else []):
        plt.plot(r["x"], r["y"], color="#A0A0A0", alpha=0.18, linewidth=1.0, marker="o", markersize=3, zorder=1)
    colors = ["#E4572E", "#4C78A8", "#54A24B", "#F3A712", "#B279A2"]
    for i, r in enumerate(top5):
        plt.plot(r["x"], r["y"], color=colors[i % 5], linewidth=2.8, marker="D", markersize=6, zorder=3,
                 label=f"Top{i+1} {r['label']} (Score {r['score']:.2f})")
    plt.plot(control_row["x"], control_row["y"], color="#111111", linewidth=2.6, marker="s", markersize=7,
             linestyle="--", zorder=4, label=f"CTRL {control_row['label']}")
    plt.title("Ezreal 4-Core DPS Power Spike (Top5 Highlighted, W/E excluded)")
    plt.xlabel("Invested Gold"); plt.ylabel("DPS")
    plt.grid(True, alpha=0.25); plt.legend(loc="best", fontsize=8); plt.tight_layout()
    plt.show()
