import csv
import json
from datetime import datetime

import matplotlib.pyplot as plt

from adc_sim.champion import Yunara, Target
from adc_sim.runes import LethalTempo, CutDown
from adc_sim.engine import run_simulation
from adc_sim.settings import get_result_export_settings
from adc_sim.data.items_registry import create_item_from_key
from adc_sim.data.items_data import (
    DORAN_OPTIONS, DORAN_SHORT, ADC_PACKAGES, pen_rule_ok,
)


def _build_yunara_4core_all_paths():
    """유나라 전용 4코어 후보 경로 풀 (AP 아이템 포함; 애쉬 풀과 분리).

    유나라는 AP 스케일링(Q온힛/패시브/W)이라 애쉬의 AD 전용 풀과 달리
    nashor/shadowflame/rabadon/void 등 AP 아이템을 후보에 포함한다.
    슬롯 구조(코어1~4 후보)는 유지하고 pen 배타 규칙을 반드시 적용한다.
    """
    core1_candidates = ["kraken", "yuntal25", "storm", "c44", "bot", "guinsoo", "terminus",
                        "nashor", "statikk"]
    core2_candidates = ["kraken", "yuntal25", "storm", "c44", "bot", "pd", "runaan", "terminus",
                        "guinsoo", "nashor", "statikk", "shadowflame"]
    core3_candidates = ["ie", "ldr", "guinsoo", "terminus", "shadowflame", "nashor", "rabadon",
                        "mortal", "void"]
    core4_candidates = ["ie", "ldr", "storm", "c44", "pd", "runaan", "kraken", "statikk", "guinsoo",
                        "terminus", "nashor", "shadowflame", "rabadon", "mortal", "void"]

    all_paths = []
    seen = set()
    for c1 in core1_candidates:
        for c2 in core2_candidates:
            if c2 == c1:
                continue
            for c3 in core3_candidates:
                if c3 in (c1, c2):
                    continue
                for c4 in core4_candidates:
                    if c4 in (c1, c2, c3):
                        continue
                    keys = (c1, c2, c3, c4)
                    if not pen_rule_ok(keys):
                        continue
                    if keys in seen:
                        continue
                    seen.add(keys)
                    all_paths.append(keys)

    # 윤탈 구매 타이밍 차이를 보기 위해 윤탈-크라켄 오프닝은 중복 규칙과 무관하게 항상 포함
    for c3 in core3_candidates:
        for c4 in core4_candidates:
            if c4 == c3 or c4 in {"yuntal25", "kraken"}:
                continue
            for opening in (("yuntal25", "kraken", c3, c4), ("kraken", "yuntal25", c3, c4)):
                if not pen_rule_ok(opening):
                    continue
                if opening in seen:
                    continue
                seen.add(opening)
                all_paths.append(opening)

    return all_paths


def build_ashe_like_core_report_meta(champion_name, full_path, core_tier):
    """코어 경로 리포트용 직렬화 메타(유나라 자체 정의; 애쉬 의존 제거)."""
    active_path = tuple(full_path[:core_tier])
    return {
        "champion": champion_name,
        "core_tier": core_tier,
        "full_path": list(full_path),
        "active_path": list(active_path),
        "build": "-".join(full_path),
        "active_build": "-".join(active_path),
    }


# === 유나라 전용 시뮬 설정 (애쉬 파일에서 분리; Ashe 가정에 의존하지 않음) ===
# 코어 단계별 고정 타깃 스탯 (유나라 자체 보유)
CORE_TARGET_STATS = {
    1: {"hp": 1700, "armor": 50, "mr": 25},
    2: {"hp": 1900, "armor": 70, "mr": 30},
    3: {"hp": 2400, "armor": 100, "mr": 50},
    4: {"hp": 2600, "armor": 120, "mr": 70},
    5: {"hp": 3000, "armor": 150, "mr": 90},
}

# 코어 타이밍별 유나라 레벨/스킬 레벨 (Ashe 레벨표 참조 제거 — 자체 정의)
# [Hypothesis] 스킬오더: Q 선마 → W 차선마 → E, 궁(R) 6/11/16.
#   순수 맥스 오더로 도출 → 레벨 9/11/13/15/17 시점 W 레벨 3/4/5/5/5, 궁 레벨 1/2/2/2/3.
CORE_YUNARA_LEVELS = {
    1: {"level": 9,  "q_level": 3, "w_level": 3, "r_level": 1},
    2: {"level": 11, "q_level": 4, "w_level": 4, "r_level": 2},
    3: {"level": 13, "q_level": 5, "w_level": 5, "r_level": 2},
    4: {"level": 15, "q_level": 5, "w_level": 5, "r_level": 2},
    5: {"level": 17, "q_level": 5, "w_level": 5, "r_level": 3},
}


def build_target_for_core(core_tier):
    """코어 티어별 더미 타깃 생성 (유나라 시뮬 전용)."""
    stats = CORE_TARGET_STATS[core_tier]
    return Target(
        hp=stats["hp"],
        armor=stats["armor"],
        magic_resist=stats["mr"],
        bonus_hp=max(0, stats["hp"] - 1500),
    )


def simulate_yunara_reference_path(core_tier):
    """비교 기준 빌드(Krk→PD→IE→LDR)의 DPS/누적골드."""
    yunara_core_order = ["kraken", "pd", "ie", "ldr"]
    target = build_target_for_core(core_tier)
    level_cfg = CORE_YUNARA_LEVELS[core_tier]
    yunara = Yunara(level=level_cfg["level"], q_level=level_cfg["q_level"],
                    w_level=level_cfg["w_level"], r_level=level_cfg["r_level"])
    yunara.set_rune(LethalTempo())
    yunara.set_sub_rune(CutDown())

    core_items = [create_item_from_key(k) for k in yunara_core_order[:core_tier]]
    items = [create_item_from_key("berserker")] + core_items

    total_cost = 0
    for item in items:
        total_cost += item.cost
        yunara.add_item(item)

    # 로테이션(평타→궁→평타→W쿨마다)은 Yunara 모델 내부에서 처리.
    _, dps, _ = run_simulation(yunara, target, verbose=False, respawn_to_full_kills=2)
    return dps, total_cost


def simulate_yunara_core_path(core_item_keys, core_tier, doran_key=None, boots_key="berserker", rune_as_bonus=0.0, target_count=1):
    """Simulate Yunara DPS and total gold for the given core progression.

    doran_key: 시작 도란 아이템(검/활). None이면 미포함.
    boots_key: 신발(기본 광전사). rune_as_bonus: 공속 룬(민첩함 등)의 평타 공속 가산(골드 무료).
    target_count: 교전 중 적 수. 1이면 순수 단일 대상. 2+면 (Q 활성 시) 크라켄 추가발동·루난 확산
        업리프트가 1차 대상 기록값에 합산된다(=다대상 유효 DPS). 1차 대상 딜은 줄지 않는다.
    """
    target = build_target_for_core(core_tier)
    level_cfg = CORE_YUNARA_LEVELS[core_tier]
    yunara = Yunara(level=level_cfg["level"], q_level=level_cfg["q_level"],
                    w_level=level_cfg["w_level"], r_level=level_cfg["r_level"])
    yunara.set_rune(LethalTempo())
    yunara.set_sub_rune(CutDown())
    yunara.set_target_count(target_count)

    active_core_keys = list(core_item_keys[:core_tier])
    core_items = []
    for idx, key in enumerate(active_core_keys, start=1):
        if key == "yuntal25":
            current_tier = len(active_core_keys)
            purchase_tier = idx
            # [Hypothesis] 윤탈 치명타 누적 가정: 구매한 그 코어 시점=10%(전 코어 통일),
            # 다음 코어부터는 항상 25%. 실측이 아닌 스택 누적 속도에 대한 단순 가정.
            if current_tier == purchase_tier:
                yuntal_crit = 0.10
            else:
                yuntal_crit = 0.25
            core_items.append(create_item_from_key(key, yuntal_crit=yuntal_crit))
        else:
            core_items.append(create_item_from_key(key))

    doran_items = [create_item_from_key(doran_key)] if doran_key else []
    items = doran_items + [create_item_from_key(boots_key)] + core_items
    total_cost = 0
    for item in items:
        total_cost += item.cost
        yunara.add_item(item)
    yunara.bonus_as_percent += rune_as_bonus  # 공속 룬(민첩함): 골드 무료, 평타 공속 가산

    # 로테이션(평타→궁→평타→W쿨마다)은 Yunara 모델 내부에서 처리.
    _, dps, _ = run_simulation(yunara, target, verbose=False, respawn_to_full_kills=2)
    return dps, total_cost


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
    "mortal": "Mortal",
    "nashor": "Nashor",
    "shadowflame": "SF",
    "rabadon": "Deathcap",
    "void": "Void",
}

CONTROL_COMBO = tuple(sorted(("kraken", "pd", "ie", "ldr")))
CONTROL_LABEL = "Control Krk-PD-IE-LDR"
from adc_sim.settings import (  # 코어 가중치 중앙 config(settings.py)
    CORE_WEIGHTS_RAW, CORE_WEIGHTS_LABEL, DEFAULT_DISCOUNT_GAMMA,
)
CORE_WEIGHTS = [w / sum(CORE_WEIGHTS_RAW) for w in CORE_WEIGHTS_RAW]
_YUNARA_4CORE_TOP1_CACHE = {}  # (target_count, rank_by) -> top1 build summary


def _path_label(path):
    """Return the short printable label for a Yunara item path."""
    return "-".join(ITEM_SHORT[k] for k in path)


def _calculate_dpg_values(dps_values, gold_values):
    """Return DPS-per-1000g values for aligned DPS/gold series."""
    return [
        dps_values[i] / (gold_values[i] / 1000.0) if gold_values[i] > 0 else 0.0
        for i in range(len(dps_values))
    ]


def _build_yunara_result_entry(path, dps_values, gold_values, pkg):
    """Build a serializable ranking entry before control-relative scoring."""
    meta = build_ashe_like_core_report_meta("Yunara", path, 4)
    is_control = tuple(sorted(path)) == CONTROL_COMBO
    return {
        "path": tuple(path),
        "doran": pkg["doran"],
        "boots": pkg["boots"],
        "rune_as": pkg["rune_as"],
        "pkg_label": pkg["label"],
        "label": f"{_path_label(path)} [{pkg['label']}]",  # 라벨에 패키지 표기(표/그래프 전파)
        "x": list(gold_values),
        "y": list(dps_values),
        "path_meta": meta,
        "is_control": is_control,
        "control_label": CONTROL_LABEL if is_control else "",
    }


def rank_yunara_4core_paths(target_count=1):
    """Rank Yunara 4-core paths and keep the best order per 4-item set.

    각 경로를 정배 패키지 A/B 두 경우로 평가(2배)하고, 4아이템 집합당 최고 1개만 유지
    → 빌드별 최적 패키지가 자동 선택된다. 컨트롤도 패키지 최적(가중 DPG 최대).

    target_count: 교전 적 수. 1=순수 단일 대상, 2+=다대상 유효 DPS(크라켄/루난 업리프트 포함).
        랭킹 지표(rel_dpg_score)는 같은 target_count의 컨트롤 대비 상대값이라 표끼리 직접 비교 가능.
    """
    all_paths = _build_yunara_4core_all_paths()

    results = []
    for c1, c2, c3, c4 in all_paths:
        for pkg in ADC_PACKAGES:
            kw = dict(doran_key=pkg["doran"], boots_key=pkg["boots"],
                      rune_as_bonus=pkg["rune_as"], target_count=target_count)
            dps1, cost1 = simulate_yunara_core_path([c1], 1, **kw)
            dps2, cost2 = simulate_yunara_core_path([c1, c2], 2, **kw)
            dps3, cost3 = simulate_yunara_core_path([c1, c2, c3], 3, **kw)
            dps4, cost4 = simulate_yunara_core_path([c1, c2, c3, c4], 4, **kw)
            path = (c1, c2, c3, c4)
            results.append(_build_yunara_result_entry(path, [dps1, dps2, dps3, dps4], [cost1, cost2, cost3, cost4], pkg))

    control_candidates = [row for row in results if row["is_control"]]
    if not control_candidates:
        raise RuntimeError("Control build not found: Krk-PD-IE-LDR")

    def _weighted_dpg(row):
        d = _calculate_dpg_values(row["y"], row["x"])
        return sum(CORE_WEIGHTS[i] * d[i] for i in range(4))
    best_control = max(control_candidates, key=_weighted_dpg)
    ctrl_dpg = _calculate_dpg_values(best_control["y"], best_control["x"])
    ctrl_dps = best_control["y"]

    for row in results:
        row_dpg = _calculate_dpg_values(row["y"], row["x"])
        rel = [(row_dpg[i] / ctrl_dpg[i]) if ctrl_dpg[i] > 0 else 0.0 for i in range(4)]
        row["dpg"] = row_dpg
        row["rel_dpg_score"] = sum(CORE_WEIGHTS[i] * rel[i] for i in range(4)) * 100.0
        # 절대 파워(DPS) 상대점수: 컨트롤 DPS 대비 가중합 (랭킹 지표는 아니고 표 표기용)
        rel_dps = [(row["y"][i] / ctrl_dps[i]) if ctrl_dps[i] > 0 else 0.0 for i in range(4)]
        row["rel_dps_score"] = sum(CORE_WEIGHTS[i] * rel_dps[i] for i in range(4)) * 100.0

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


def get_yunara_4core_top1_build(target_count=1, rank_by="dpg"):
    """Return the cached Yunara 4-core top1 build summary for the given target_count.

    target_count=1: 순수 단일 대상 Top1. 2+: 다대상 유효 DPS 기준 Top1(크라켄/루난 업리프트 반영).
    rank_by="dpg"(기본)=상대 골드효율 가중합 1위, "dps"=원시 DPS 가중합 1위.
    (target_count, rank_by)별로 별도 캐시한다.
    """
    cache_key = (target_count, rank_by)
    cached = _YUNARA_4CORE_TOP1_CACHE.get(cache_key)
    if cached is None:
        ranked_data = rank_yunara_4core_paths(target_count=target_count)
        ranked = ranked_data["ranked"]
        for row in ranked:
            row["weighted_dps"] = sum(CORE_WEIGHTS[i] * row["y"][i] for i in range(4))
        top1 = max(ranked, key=lambda row: row["weighted_dps"]) if rank_by == "dps" else ranked[0]
        cached = {
            "path": top1["path"],
            "doran": top1["doran"],
            "boots": top1["boots"],
            "rune_as": top1["rune_as"],
            "pkg_label": top1["pkg_label"],
            "score": top1["rel_dpg_score"],
            "weighted_dps": top1["weighted_dps"],
            "control_path": ranked_data["best_control"]["path"],
            "control_pkg": ranked_data["best_control"]["pkg_label"],
            "total_paths_tested": ranked_data["total_paths_simulated"],
            "label": top1["label"],
            "target_count": target_count,
        }
        _YUNARA_4CORE_TOP1_CACHE[cache_key] = cached
    return cached


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


def print_case_style_table(ranked, best_control, target_count, top_n=20):
    """Print the Yunara ranking in case_ranking.py table format (4코어).

    좌측 4열=DPS(코어1~4), 우측 4열=DPG(코어1~4), GOLD=4코어 총골드,
    그리고 컨트롤 대비 가중 상대점수를 DPG(랭킹 지표)·DPS(절대 파워) 둘 다 표기.
    """
    scenario = "단일 대상(적 1명)" if target_count == 1 else f"적 {target_count}명 교전(다대상 유효 DPS)"
    print(f"\n{'=' * 132}")
    print(f"[YUNARA] target_count={target_count}  ({scenario})  가중 1~4코어 {CORE_WEIGHTS_LABEL}")
    print("  제약: pen-exclusive≤1(terminus/ldr/mortal) | "
          "후보=YUNARA_CORE1~4_CANDIDATES(core1·2에 statikk 포함, 애쉬와 분리)")
    print("좌 4열=DPS(코어1~4), 우 4열=DPG(코어1~4), GOLD=4코어 총골드 | "
          "SCORE=컨트롤 대비 가중 상대(DPG=골드효율=랭킹지표, DPS=절대파워), vs=±%")
    print(f"{'':>2} | {'':<36} | {'----- DPS (core 1->4) -----':^27} | "
          f"{'----- DPG (core 1->4) -----':^27} | {'':>6} | {'DPG (rank metric)':^16} | {'DPS':^16}")
    header = (f"{'RK':>2} | {'BUILD':<36} | "
              f"{'1C':>6} {'2C':>6} {'3C':>6} {'4C':>6} | "
              f"{'1C':>6} {'2C':>6} {'3C':>6} {'4C':>6} | "
              f"{'GOLD':>6} | {'SCORE':>8} {'vs':>7} | {'SCORE':>8} {'vs':>7}")
    print(header)
    print("-" * len(header))

    def _row(tag, label, dpss, dpgs, gold, score_dpg, score_dps):
        dps_s = " ".join(f"{dpss[i]:>6.0f}" for i in range(4))
        dpg_s = " ".join(f"{dpgs[i]:>6.1f}" for i in range(4))
        print(f"{tag:>2} | {label:<36} | {dps_s} | {dpg_s} | {gold:>6.0f} | "
              f"{score_dpg:>8.2f} {score_dpg - 100.0:>+7.2f} | {score_dps:>8.2f} {score_dps - 100.0:>+7.2f}")

    _row("C", best_control["label"] + " [CTRL]", best_control["y"], best_control["dpg"],
         best_control["x"][3], 100.0, 100.0)
    rank = 0
    for row in ranked:
        if row["is_control"]:
            continue
        rank += 1
        if rank > top_n:
            break
        _row(str(rank), row["label"], row["y"], row["dpg"], row["x"][3],
             row["rel_dpg_score"], row["rel_dps_score"])


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


GAMMA = DEFAULT_DISCOUNT_GAMMA
HORIZON = 5
CORE1_CANDIDATES = [
    "kraken", "yuntal25", "storm", "c44", "bot", "guinsoo", "terminus", "nashor", "statikk",
]
CORE2_CANDIDATES = [
    "kraken", "yuntal25", "storm", "c44", "bot", "pd", "runaan", "terminus",
    "guinsoo", "nashor", "statikk", "shadowflame",
]
CORE3_CANDIDATES = [
    "ie", "ldr", "guinsoo", "terminus", "shadowflame", "nashor", "rabadon", "mortal", "void",
]
CORE4_CANDIDATES = [
    "ie", "ldr", "storm", "c44", "pd", "runaan", "kraken", "statikk", "guinsoo",
    "terminus", "nashor", "shadowflame", "rabadon", "mortal", "void",
]
# [Hypothesis] 유나라 전용 5코어 풀이 없으므로 베인 마이그레이션 관례대로 4코어 풀을 재사용한다.
CORE5_CANDIDATES = list(CORE4_CANDIDATES)
CANDIDATES_BY_SLOT = {
    1: CORE1_CANDIDATES,
    2: CORE2_CANDIDATES,
    3: CORE3_CANDIDATES,
    4: CORE4_CANDIDATES,
    5: CORE5_CANDIDATES,
}


class SimCache:
    """아이템 집합과 윤탈 구매 시점을 키로 유나라 DPS·골드를 메모이즈한다."""

    def __init__(self, package, target_count):
        """시작 패키지와 교전 적 수를 고정한 유나라 탐색 캐시를 초기화한다."""
        self.kw = {
            "doran_key": package["doran"],
            "boots_key": package["boots"],
            "rune_as_bonus": package["rune_as"],
            "target_count": target_count,
        }
        self.cache = {}
        self.hits = 0
        self.misses = 0

    def _key(self, items_tuple):
        """순서 무관 집합과 윤탈이 현재 구매 슬롯인지 여부를 캐시 키로 반환한다."""
        sorted_items = tuple(sorted(items_tuple))
        yuntal_last = bool(items_tuple) and "yuntal25" in sorted_items and items_tuple[-1] == "yuntal25"
        return sorted_items, yuntal_last

    def sim(self, items_tuple):
        """완성 코어 경로의 현재 티어 DPS와 총 골드를 반환한다."""
        key = self._key(items_tuple)
        if key in self.cache:
            self.hits += 1
            return self.cache[key]
        self.misses += 1
        result = simulate_yunara_core_path(list(items_tuple), len(items_tuple), **self.kw)
        self.cache[key] = result
        return result


def _enumerate_future_combos(fixed, from_slot, horizon=HORIZON):
    """확정 코어 뒤에서 중복·관통 제약을 만족하는 유나라 미래 조합을 생성한다."""
    remaining = list(range(from_slot, horizon + 1))

    def rec(index, current):
        """현재 슬롯 이후의 합법적인 아이템 조합을 재귀 생성한다."""
        if index == len(remaining):
            yield tuple(current)
            return
        for item_key in CANDIDATES_BY_SLOT[remaining[index]]:
            if item_key in fixed or item_key in current:
                continue
            candidate = tuple(fixed) + tuple(current) + (item_key,)
            if not pen_rule_ok(candidate):
                continue
            current.append(item_key)
            yield from rec(index + 1, current)
            current.pop()

    yield from rec(0, [])


def _score_combo(cache, fixed, combo, from_slot, dps_prev, gold_prev, gamma, horizon):
    """미래 코어별 마지널 DPG 할인합을 계산해 조합 점수로 반환한다."""
    full_path = list(fixed) + list(combo)
    score = 0.0
    for offset, tier in enumerate(range(from_slot, horizon + 1)):
        dps, gold = cache.sim(tuple(full_path[:tier]))
        delta_gold = gold - gold_prev
        marginal_dpg = (dps - dps_prev) / (delta_gold / 1000.0) if delta_gold > 0 else 0.0
        score += (gamma ** offset) * marginal_dpg
    return score


def solve_greedy(cache, gamma=None, horizon=HORIZON, top_alt=3):
    """매 슬롯에서 미래 할인 마지널 DPG를 재탐색해 유나라 1~5코어 궤적을 반환한다."""
    if gamma is None:
        gamma = GAMMA
    fixed, steps = [], []
    dps_prev, gold_prev = 0.0, 0.0
    for slot in range(1, horizon + 1):
        best_score, best_combo = None, None
        alternatives_by_item, alternatives_path = {}, {}
        for combo in _enumerate_future_combos(fixed, slot, horizon):
            score = _score_combo(cache, fixed, combo, slot, dps_prev, gold_prev, gamma, horizon)
            item_key = combo[0]
            if item_key not in alternatives_by_item or score > alternatives_by_item[item_key]:
                alternatives_by_item[item_key], alternatives_path[item_key] = score, combo
            if best_score is None or score > best_score:
                best_score, best_combo = score, combo
        if best_combo is None:
            break
        fixed.append(best_combo[0])
        dps_now, gold_now = cache.sim(tuple(fixed))
        delta_gold = gold_now - gold_prev
        marginal_dpg = (dps_now - dps_prev) / (delta_gold / 1000.0) if delta_gold > 0 else 0.0
        ranked = sorted(alternatives_by_item.items(), key=lambda pair: pair[1], reverse=True)[:top_alt]
        steps.append({
            "slot": slot, "item": best_combo[0], "score": best_score,
            "dps": dps_now, "gold": gold_now, "marginal_dpg": marginal_dpg,
            "future_path_winner": best_combo,
            "alternatives": [
                {"item": key, "score": score, "future_path": alternatives_path[key]}
                for key, score in ranked
            ],
        })
        dps_prev, gold_prev = dps_now, gold_now
    return {"trajectory": fixed, "steps": steps}


def print_scenario(label, out, cache, target_count, gamma=None):
    """유나라 receding-horizon 최종 궤적과 슬롯별 선택·대안을 출력한다."""
    if gamma is None:
        gamma = GAMMA
    print(f"\n{'=' * 22}  Yunara · TC{target_count} · {label}  {'=' * 22}")
    print(f"γ={gamma}, horizon={HORIZON} | 최종 궤적: "
          f"{' → '.join(ITEM_SHORT.get(key, key) for key in out['trajectory'])}")
    print(f"시뮬 캐시: {cache.hits} hits / {cache.misses} misses")
    for step in out["steps"]:
        alternatives = " / ".join(
            f"{ITEM_SHORT.get(alt['item'], alt['item'])}:{alt['score']:.1f}"
            for alt in step["alternatives"]
        )
        print(
            f"  {step['slot']}C → {ITEM_SHORT.get(step['item'], step['item']):<10} | "
            f"DPS {step['dps']:>7.1f} | Gold {step['gold']:>5.0f} | "
            f"MarginalDPG {step['marginal_dpg']:>7.2f} | Score {step['score']:>7.2f} | {alternatives}"
        )


def main(gamma=None):
    """유나라의 단일·2대상과 두 ADC 패키지를 베인식 receding-horizon으로 탐색한다."""
    if gamma is None:
        gamma = GAMMA
    for target_count in (1, 2):
        for package in ADC_PACKAGES:
            cache = SimCache(package, target_count)
            out = solve_greedy(cache, gamma=gamma)
            print_scenario(package["label"], out, cache, target_count, gamma=gamma)


def main_legacy_ranking():
    """교체 전 유나라 4코어 전수 랭킹·리포트·그래프를 실행한다."""
    """Run the Yunara ranking for 1-enemy and 2-enemy scenarios (case_ranking 표 포맷).

    상대 1명(순수 단일 대상)과 2명(다대상 유효 DPS) 각각으로 시뮬을 돌려 표 2개를 출력한다.
    리포트 export·그래프는 단일 대상(1명) 기준으로 유지한다.
    """
    print("\n=== Yunara Build Path Ranking: 단일 대상(1명) vs 2명 교전 ===")
    data_by_tc = {}
    for tc in (1, 2):
        data_by_tc[tc] = rank_yunara_4core_paths(target_count=tc)
        print(f"\n[Info] target_count={tc}: {data_by_tc[tc]['total_paths_simulated']} paths simulated (before same-combo dedup)")
        print_case_style_table(data_by_tc[tc]["ranked"], data_by_tc[tc]["best_control"], tc, top_n=20)

    report_paths = export_yunara_ranking_report(data_by_tc[1], top_n=20)
    for report_path in report_paths:
        print(f"[Info] Saved Yunara report: {report_path}")
    plot_graph(data_by_tc[1]["ranked"], data_by_tc[1]["best_control"])


def run_cli(args=None):
    """기본 receding-horizon 또는 `legacy-ranking` 호환 모드로 유나라 CLI를 실행한다."""
    import sys

    cli_args = list(sys.argv[1:] if args is None else args)
    if cli_args and cli_args[0] == "legacy-ranking":
        main_legacy_ranking()
        return
    gamma = GAMMA
    if cli_args:
        try:
            gamma = float(cli_args[0])
            if not 0.0 < gamma <= 1.0:
                raise ValueError
        except ValueError:
            print(f"[warn] gamma 인자 파싱 실패({cli_args[0]!r}) — 기본 {GAMMA} 사용")
            gamma = GAMMA
    main(gamma=gamma)


if __name__ == "__main__":
    run_cli()
