"""폐기 예정 코드 보관소 — 유나라 (2026-09-15).

`adc_sim/simulations/yunara.py` 의 기본 모드가 "하프 티어 포함 receding-horizon" 으로
교체되면서 쓰이지 않게 된 것들을 지우지 않고 여기 모아둔다. **어디서도 import 하지 않는다.**

1) 4코어 전수 랭킹의 출력 계층 — 표/그래프/CSV·JSON 리포트
   (랭킹 엔진 자체인 rank_yunara_4core_paths / get_yunara_4core_top1_build 는 아직
    power_compare.py·ashe.py 가 쓰므로 yunara.py 에 남아 있다.)
2) 앵커 누적 점수식을 쓰던 비-하프 receding-horizon 경로
   — 각 티어의 마지널을 "직전 코어" 가 아니라 "탐색 시작 시점" 기준으로 재던 방식이라
     첫 아이템 기여가 모든 항에 중복 계상됐다. 하프 경로(_score_combo_half)는 스텝마다
     기준을 갱신하는 증분식이라 이 문제가 없다.
3) 혼합 지표 4코어 전수 랭킹(rank_yunara_4core_paths_mixed) — 호출처 없음.

복구하려면 이 파일에서 해당 함수를 yunara.py 로 되돌리고 필요한 import 를 같이 살리면 된다.
"""
import csv
import json
from datetime import datetime

import matplotlib.pyplot as plt

from adc_sim.settings import get_result_export_settings
from adc_sim.simulations.yunara import (
    ADC_PACKAGES, CORE_WEIGHTS_LABEL, CORE_WEIGHTS_RAW, GAMMA, HORIZON, ITEM_SHORT,
    _build_yunara_result_entry, _build_yunara_4core_all_paths, _calculate_dpg_values,
    _enumerate_future_combos, _path_label, pen_rule_ok, rank_yunara_4core_paths,
    simulate_yunara_core_path,
)
from adc_sim.simulations.ehp import format_survivability_cell

TARGET_MIX_WEIGHTS = ((1, 0.5), (2, 0.5))


def rank_yunara_4core_paths_mixed(mix=None):
    """혼합 DPS 기준 4코어 전수 랭킹. 반환 스키마는 rank_yunara_4core_paths 와 동일.

    mix: ((target_count, weight), ...). 코어별 DPS/DPG 는 혼합값으로 계산되고,
    rel_dpg_score 는 같은 혼합 기준의 컨트롤 대비 상대값이다. 골드는 tc 무관 동일.
    """
    mix = tuple(mix or TARGET_MIX_WEIGHTS)
    all_paths = _build_yunara_4core_all_paths()

    results = []
    for c1, c2, c3, c4 in all_paths:
        for pkg in ADC_PACKAGES:
            dps_mix = [0.0, 0.0, 0.0, 0.0]
            costs = [0, 0, 0, 0]
            for tc, w in mix:
                kw = dict(doran_key=pkg["doran"], boots_key=pkg["boots"],
                          rune_as_bonus=pkg["rune_as"], target_count=tc)
                for tier in range(1, 5):
                    d, g = simulate_yunara_core_path([c1, c2, c3, c4][:tier], tier, **kw)
                    dps_mix[tier - 1] += w * d
                    costs[tier - 1] = g
            results.append(_build_yunara_result_entry((c1, c2, c3, c4), dps_mix, costs, pkg))

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
        rel_dps = [(row["y"][i] / ctrl_dps[i]) if ctrl_dps[i] > 0 else 0.0 for i in range(4)]
        row["rel_dps_score"] = sum(CORE_WEIGHTS[i] * rel_dps[i] for i in range(4)) * 100.0

    combo_best = {}
    for row in results:
        key = tuple(sorted(row["path"]))
        prev = combo_best.get(key)
        if prev is None or row["rel_dpg_score"] > prev["rel_dpg_score"]:
            combo_best[key] = row
    deduped = sorted(combo_best.values(), key=lambda r: r["rel_dpg_score"], reverse=True)
    best_control_after = next(row for row in deduped if row["is_control"])
    return {"ranked": deduped, "best_control": best_control_after,
            "total_paths_simulated": len(all_paths), "mix": mix}


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


def _row_survivability(row, target_count=1):
    """랭킹 행의 코어 1~4 생존성(유효체력 + 회복 환산)과 회복량을 반환한다.

    EHP 는 시뮬 무관 스탯 산술이지만 회복량은 전투 결과라 코어별로 시뮬을 한 번 더 돈다.
    반환: (surv_list, healing_list, ehp_list) — surv_list[i] = {physical, magic, true, ...}
    """
    survs, heals, ehps = [], [], []
    for tier in (1, 2, 3, 4):
        level_cfg = CORE_YUNARA_LEVELS[tier]
        ehp = core_timing_ehp(
            lambda level, lv=level_cfg: Yunara(
                level=lv["level"], q_level=lv["q_level"],
                w_level=lv["w_level"], r_level=lv["r_level"]),
            level_cfg["level"],
            ([row["doran"]] if row["doran"] else []) + [row["boots"]] + list(row["path"][:tier]),
        )
        _dps, _gold, sustain = simulate_yunara_core_path(
            list(row["path"]), tier, doran_key=row["doran"], boots_key=row["boots"],
            rune_as_bonus=row["rune_as"], target_count=target_count, return_sustain=True,
        )
        heals.append(sustain["total_healing"])
        ehps.append(ehp)
        survs.append(survivability(ehp, sustain["total_healing"]))
    return survs, heals, ehps


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
    print("각 빌드 아래 보조행 = 생존성(코어1~4) = 유효체력 + 회복 환산. 물리/마법/고정 세 축이며 "
          "괄호는 1000골드당 생존성. HEAL 은 기준 전투 누적 회복량(DPS 기반 근사).")
    header = (f"{'RK':>2} | {'BUILD':<36} | "
              f"{'1C':>6} {'2C':>6} {'3C':>6} {'4C':>6} | "
              f"{'1C':>6} {'2C':>6} {'3C':>6} {'4C':>6} | "
              f"{'GOLD':>6} | {'회복물리':>7} {'회복마법':>7} {'회복고정':>7} | "
              f"{'SCORE':>8} {'vs':>7} | {'SCORE':>8} {'vs':>7}")
    print(f"{'':>2} | {'':<36} | {'--- DPS (core 1->4) ---':^27} | "
          f"{'--- DPG (core 1->4) ---':^27} | {'':>6} | {'-- 4코어 회복(축별 EHP) --':^23} | "
          f"{'DPG (rank metric)':^16} | {'DPS':^16}")
    print(header)
    print("-" * len(header))

    def _row(tag, label, dpss, dpgs, survs, heals, golds, gold, score_dpg, score_dps, ehps):
        dps_s = " ".join(f"{dpss[i]:>6.0f}" for i in range(4))
        dpg_s = " ".join(f"{dpgs[i]:>6.1f}" for i in range(4))
        h4 = healing_effective(heals[3], ehps[3])     # 4코어 회복을 축별 유효체력으로
        print(f"{tag:>2} | {label:<36} | {dps_s} | {dpg_s} | {gold:>6.0f} | "
              f"{h4['physical']:>7.0f} {h4['magic']:>7.0f} {h4['true']:>7.0f} | "
              f"{score_dpg:>8.2f} {score_dpg - 100.0:>+7.2f} | {score_dps:>8.2f} {score_dps - 100.0:>+7.2f}")
        for axis, tag_ko in (("physical", "물리"), ("magic", "마법"), ("true", "고정")):
            cells = " ".join(
                f"{survs[i][axis]:>6.0f}({survivability_per_1000_gold(survs[i][axis], golds[i]):>5.1f})"
                for i in range(4)
            )
            print(f"{'':>2} | {'  ↳ 생존성 ' + tag_ko:<36} | {cells}")

    ctrl_surv, ctrl_heal, ctrl_ehp = _row_survivability(best_control, target_count)
    _row("C", best_control["label"] + " [CTRL]", best_control["y"], best_control["dpg"],
         ctrl_surv, ctrl_heal, best_control["x"], best_control["x"][3], 100.0, 100.0, ctrl_ehp)
    rank = 0
    for row in ranked:
        if row["is_control"]:
            continue
        rank += 1
        if rank > top_n:
            break
        row_surv, row_heal, row_ehp = _row_survivability(row, target_count)
        _row(str(rank), row["label"], row["y"], row["dpg"], row_surv, row_heal,
             row["x"], row["x"][3], row["rel_dpg_score"], row["rel_dps_score"], row_ehp)


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
