from champion import Corki, Target
from items import (
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
    Terminus,
    Plated_Steelcaps,
    BerserkerGreaves,
)
from engine import run_simulation


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


def create_item_from_key(item_key):
    if item_key == "muramana":
        # 1코어부터 무라마나 상태로 비교 요청
        item = Manamune()
        item.is_muramana = True
        item.name = "Muramana"
        item.mana_stacked = item.max_mana_stack
        return item
    if item_key == "trinity":
        return TrinityForce()
    if item_key == "statikk":
        return StatikkShiv()
    if item_key == "kraken":
        return KrakenSlayer()
    if item_key == "guinsoo":
        return GuinsoosRageblade()
    if item_key == "storm":
        return Stormrazor()
    if item_key == "essence":
        return EssenceReaver()
    if item_key == "ie":
        return InfinityEdge()
    if item_key == "collector":
        return TheCollector()
    if item_key == "yuntal5":
        return YunTalWildarrows(crit=0.05)
    if item_key == "botrk":
        return BladeOfRuinedKing()
    if item_key == "terminus":
        return Terminus()
    if item_key == "plated":
        return Plated_Steelcaps()
    if item_key == "berserker":
        return BerserkerGreaves()
    raise ValueError(f"Unknown item key: {item_key}")


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
        "yuntal5": "Yun(5)",
        "botrk": "BotRK",
        "terminus": "Terminus",
        "plated": "Plated",
        "berserker": "Berserker",
    }
    return mapping[item_key]


def simulate_corki_core_path(full_path, shoe_key, core_tier):
    target = build_target_for_core(core_tier)
    level_cfg = CORE_LEVELS[core_tier]
    skill_cfg = CORKI_SKILL_LEVELS[core_tier]

    corki = Corki(
        level=level_cfg["level"],
        q_level=skill_cfg["q"],
        e_level=skill_cfg["e"],
        r_level=skill_cfg["r"],
    )

    items = [create_item_from_key(shoe_key)]
    for key in full_path[:core_tier]:
        items.append(create_item_from_key(key))

    total_cost = 0
    for item in items:
        total_cost += item.cost
        corki.add_item(item)

    _, dps, _ = run_simulation(corki, target, verbose=False)
    return dps, total_cost


if __name__ == "__main__":
    print("\n=== Corki 2-Core Efficiency (DPG vs Control, 5:4) ===")

    core_candidates = [
        "muramana", "trinity", "statikk", "kraken", "guinsoo", "storm",
        "essence", "ie", "collector", "yuntal5", "botrk", "terminus",
    ]
    shoe_candidates = ["plated", "berserker"]

    # 대조군: 트포-무라마나 + 판금 장화
    control_path = ("trinity", "muramana")
    control_shoe = "plated"

    results = []
    for shoe in shoe_candidates:
        for c1 in core_candidates:
            for c2 in core_candidates:
                if c1 == c2:
                    continue

                path = (c1, c2)
                dps1, cost1 = simulate_corki_core_path(path, shoe, 1)
                dps2, cost2 = simulate_corki_core_path(path, shoe, 2)

                label = f"{short_name(c1)}-{short_name(c2)}-{short_name(shoe)}"
                is_control = (path == control_path and shoe == control_shoe)

                dpg1 = dps1 / (cost1 / 1000.0) if cost1 > 0 else 0.0
                dpg2 = dps2 / (cost2 / 1000.0) if cost2 > 0 else 0.0

                results.append({
                    "path": path,
                    "shoe": shoe,
                    "label": label,
                    "x": [cost1, cost2],
                    "y": [dps1, dps2],
                    "dpg": [dpg1, dpg2],
                    "is_control": is_control,
                })

    control_row = next((r for r in results if r["is_control"]), None)
    if control_row is None:
        raise RuntimeError("Control build not found.")

    ctrl_dpg1, ctrl_dpg2 = control_row["dpg"]
    w1, w2 = 5.0, 4.0
    wsum = w1 + w2

    for r in results:
        rel1 = ((r["dpg"][0] / ctrl_dpg1) * 100.0 - 100.0) if ctrl_dpg1 > 0 else 0.0
        rel2 = ((r["dpg"][1] / ctrl_dpg2) * 100.0 - 100.0) if ctrl_dpg2 > 0 else 0.0
        r["rel_dpg_core"] = [rel1, rel2]
        r["score"] = ((w1 * rel1) + (w2 * rel2)) / wsum

    ranked = sorted(results, key=lambda r: r["score"], reverse=True)

    print(
        f"Control: {control_row['label']} | "
        f"1C DPG {control_row['dpg'][0]:.2f}, 2C DPG {control_row['dpg'][1]:.2f}"
    )
    print(
        "\nTop 40 (rank by weighted relative DPG, 5:4)\n"
        "RK | BUILD                             | 1C DPS/ΔDPG% | 2C DPS/ΔDPG% | SCORE"
    )
    print("-" * 90)

    top_n = min(40, len(ranked))
    output_rows = ranked[:top_n]
    if not any(r["is_control"] for r in output_rows):
        output_rows.append(control_row)

    for i, r in enumerate(output_rows, start=1):
        y1, y2 = r["y"]
        d1, d2 = r["rel_dpg_core"]
        ctrl_tag = " [CTRL]" if r["is_control"] else ""
        c1 = f"{y1:.1f}/{d1:+.1f}%"
        c2 = f"{y2:.1f}/{d2:+.1f}%"
        print(f"{i:>2} | {(r['label'] + ctrl_tag):<33} | {c1:>12} | {c2:>12} | {r['score']:>6.2f}")
