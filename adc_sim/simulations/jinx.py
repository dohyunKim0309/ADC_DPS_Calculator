"""Jinx 4코어 빌드 랭킹 — 미니건(+130% 정상상태) 평타 + W(Zap!) 주기 넛지. K=2.

vayne.py 미러. 크리 ADC 라 Ashe 공유 인프라 재사용:
  · 후보 풀 = `_build_ashe_4core_all_paths()` (크리/공속 풀)
  · 컨트롤 = kraken-pd-ie-ldr (타 크리 ADC 와 일관; 탐색공간 필수)
  · 레벨표 = CORE_JINX_LEVELS (챔프 레벨만; 스킬레벨은 로컬 표준 선마)

모델 가정(사용자 합의 2026-07):
  · Q 로켓(Fishbones)은 단일 더미서 전략적 열세(미니건 스택 상실 + 20마나/발) → 미니건 고정.
  · Get Excited! 패시브 미모델(OFF) — 처치 조건이라 더미 시뮬엔 안 뜸. Jinx 실제 한타
    스노우볼 고점은 이 모델이 과소평가함(모델 밖 상방).
  · 공속캡: 엔진 3.0(실제 롤 2.5) — 전 챔프 공통, 별도 결정사항. Jinx 는 base/ratio 0.625 라
    현실 빌드서 ~2.5 근처에 머묾(캡 갭은 공속 과다 빌드서만 소폭).

Run: .venv/bin/python -m adc_sim.simulations.jinx
"""
from adc_sim.champion import Jinx, Target
import matplotlib.pyplot as plt
from adc_sim.runes import LethalTempo, CutDown
from adc_sim.engine import run_simulation
from adc_sim.data.items_registry import create_item_from_key
from adc_sim.data.items_data import ADC_PACKAGES
from adc_sim.settings import CORE_WEIGHTS_RAW, CORE_WEIGHTS_LABEL
from adc_sim.simulations.ashe import (
    build_ashe_like_core_report_meta, _build_ashe_4core_all_paths,
    CORE_JINX_LEVELS, build_target_for_core,
)


def _jinx_skill_levels_for_core(core_tier):
    """스킬 선마 R>Q>W>E (표준 징크스). Q 선마 → 미니건 +130% 조기 확보.
    C1(lvl9): q5/w2 · C2(11): q5/w3 · C3(13): q5/w5 · C4(15): q5/w5. E·R 미모델."""
    q = 5
    w = {1: 2, 2: 3, 3: 5, 4: 5}[core_tier]
    return q, w


def simulate_jinx_core_path(full_path, core_tier, doran_key="doranblade",
                            boots_key="berserker", rune_as_bonus=0.0):
    """Jinx DPS + total gold for a core timing. 미니건 정상상태 평타 + W 쿨마다(마나 바운드). K=2.

    full_path: 코어 키 리스트. core_tier: 1~4. doran/boots/rune_as: 패키지.
    반환: (dps, total_cost).
    """
    target = build_target_for_core(core_tier)
    lvl = CORE_JINX_LEVELS[core_tier]["level"]
    q, w = _jinx_skill_levels_for_core(core_tier)
    jinx = Jinx(level=lvl, q_level=q, w_level=w, minigun_stacks=3, q_mode="minigun")
    jinx.set_rune(LethalTempo())
    jinx.set_sub_rune(CutDown())

    items = ([create_item_from_key(doran_key)] if doran_key else []) + [create_item_from_key(boots_key)]
    for key in full_path[:core_tier]:
        # 윤탈 스택 가정: 구매 코어=10%, 다음 코어부터 25% (ashe.py 관례와 동일)
        if key == "yuntal25":
            idx = full_path.index(key) + 1
            yuntal_crit = 0.10 if idx == core_tier else 0.25
            items.append(create_item_from_key(key, yuntal_crit=yuntal_crit))
        else:
            items.append(create_item_from_key(key))
    total_cost = 0
    for it in items:
        total_cost += it.cost
        jinx.add_item(it)
    jinx.bonus_as_percent += rune_as_bonus

    skill_plan = {"auto_cast": {"w": True}}   # W 쿨마다(마나 게이트)
    _, dps, _ = run_simulation(jinx, target, verbose=False, skill_plan=skill_plan, respawn_to_full_kills=2)
    return dps, total_cost


# 컨트롤(베이스라인) = 크리 ADC 실전 빌드. 탐색공간에 반드시 존재해야 함.
CONTROL_PATH = ("kraken", "pd", "ie", "ldr")
_JINX_TOP1_CACHE = {}

ITEM_SHORT = {
    "kraken": "Krk", "yuntal25": "Yun", "storm": "Storm", "c44": "C44", "bot": "BotRK",
    "guinsoo": "Gui", "terminus": "Terminus", "pd": "PD", "runaan": "Runaan",
    "ie": "IE", "ldr": "LDR", "statikk": "Statikk",
}


def _build_all_paths():
    paths = list(_build_ashe_4core_all_paths())   # 크리/공속 풀 (Ashe 공유)
    if CONTROL_PATH not in set(paths):
        paths.append(CONTROL_PATH)
    return paths


def _rank_rows(all_paths):
    """전 (경로×패키지) 시뮬 → dedup(정렬 combo 최고점) → 컨트롤 정규화 RelDPG. rows 반환."""
    dedupe_weight_raw = list(CORE_WEIGHTS_RAW)
    core_weight_raw = list(CORE_WEIGHTS_RAW)
    weight_sum = sum(core_weight_raw)
    core_weights = [w / weight_sum for w in core_weight_raw]
    ctrl_combo = tuple(sorted(CONTROL_PATH))

    rows = []
    for path in all_paths:
        for pkg in ADC_PACKAGES:
            kw = dict(doran_key=pkg["doran"], boots_key=pkg["boots"], rune_as_bonus=pkg["rune_as"])
            dps_list, cost_list = [], []
            for tier in range(1, 5):
                d, c = simulate_jinx_core_path(path, tier, **kw)
                dps_list.append(d); cost_list.append(c)
            dpg = [dps_list[i] / (cost_list[i] / 1000.0) if cost_list[i] > 0 else 0.0 for i in range(4)]
            rows.append({
                "path": path, "doran": pkg["doran"], "boots": pkg["boots"],
                "rune_as": pkg["rune_as"], "pkg_label": pkg["label"],
                "x": cost_list, "y": dps_list, "dpg": dpg,
                "is_control": tuple(sorted(path)) == ctrl_combo,
                "dedupe_eff": sum(dedupe_weight_raw[i] * dpg[i] for i in range(4)),
            })

    dedupe_best = {}
    for r in rows:
        key = tuple(sorted(r["path"]))
        if key not in dedupe_best or r["dedupe_eff"] > dedupe_best[key]["dedupe_eff"]:
            dedupe_best[key] = r
    rows_dedup = list(dedupe_best.values())

    # 컨트롤은 정규 순서(CONTROL_PATH)로 고정
    rows_dedup = [r for r in rows_dedup if not r["is_control"]]
    ctrl_cands = [r for r in rows if tuple(r["path"]) == CONTROL_PATH]
    if ctrl_cands:
        rows_dedup.append(max(ctrl_cands, key=lambda r: r["dedupe_eff"]))

    for r in rows_dedup:
        r["weighted_dpg"] = sum(core_weights[i] * r["dpg"][i] for i in range(4))
        r["weighted_dps"] = sum(core_weights[i] * r["y"][i] for i in range(4))

    control_rows = [r for r in rows_dedup if r["is_control"]]
    if not control_rows:
        raise RuntimeError(
            f"Control build {CONTROL_PATH} not found in search space. "
            "Check Ashe crit pool contains kraken/pd/ie/ldr."
        )
    best_control = max(control_rows, key=lambda r: r["weighted_dpg"])
    baseline_dpg_4 = best_control["dpg"][:4]

    for r in rows_dedup:
        core_rel_pct = [
            (r["dpg"][i] / baseline_dpg_4[i] * 100.0 if baseline_dpg_4[i] > 0 else 0.0)
            for i in range(4)
        ]
        r["core_rel_delta_pct_4"] = [p - 100.0 for p in core_rel_pct]
        r["rel_dpg_score"] = sum(core_weights[i] * core_rel_pct[i] for i in range(4))

    return rows_dedup, best_control


def get_jinx_4core_top1_build(rank_by="dpg"):
    """랭킹된 4코어 top1 빌드 + 컨트롤 메타 반환. rank_by: "dpg"(RelDPG) | "dps"(절대 가중DPS)."""
    if rank_by in _JINX_TOP1_CACHE:
        return _JINX_TOP1_CACHE[rank_by]
    rows_dedup, best_control = _rank_rows(_build_all_paths())
    sort_key = (lambda r: r["weighted_dps"]) if rank_by == "dps" else (lambda r: r["rel_dpg_score"])
    ranked = sorted(rows_dedup, key=sort_key, reverse=True)
    top1 = ranked[0]
    result = {
        "path": top1["path"], "doran": top1["doran"], "boots": top1["boots"],
        "rune_as": top1["rune_as"], "pkg_label": top1["pkg_label"],
        "score": top1["rel_dpg_score"], "weighted_dpg": top1["weighted_dpg"],
        "weighted_dps": top1["weighted_dps"],
        "control_path": best_control["path"], "control_doran": best_control["doran"],
        "control_boots": best_control["boots"], "control_rune_as": best_control["rune_as"],
        "control_pkg": best_control["pkg_label"], "control_weighted_dpg": best_control["weighted_dpg"],
    }
    _JINX_TOP1_CACHE[rank_by] = result
    return result


def build_jinx_core_report_meta(full_path, core_tier):
    """직렬화용 리포트 메타(Ashe-like 공용 헬퍼 재사용)."""
    return build_ashe_like_core_report_meta("Jinx", full_path, core_tier)


def get_jinx_powercompare_builds():
    """power_compare 연동용 (best, meta).
    - best: RelDPG top1(rank_by="dpg") — power_compare 가 DPG 비교라.
    - meta: 컨트롤(kraken-pd-ie-ldr, 최적 패키지) — 실전 기준.
    각 dict: path/doran/boots/rune_as/pkg_label/weighted_dpg.
    """
    best_src = get_jinx_4core_top1_build(rank_by="dpg")
    best = {
        "path": best_src["path"], "doran": best_src["doran"], "boots": best_src["boots"],
        "rune_as": best_src["rune_as"], "pkg_label": best_src["pkg_label"],
        "weighted_dpg": best_src["weighted_dpg"],
    }
    meta = {
        "path": best_src["control_path"], "doran": best_src["control_doran"],
        "boots": best_src["control_boots"], "rune_as": best_src["control_rune_as"],
        "pkg_label": best_src["control_pkg"], "weighted_dpg": best_src["control_weighted_dpg"],
    }
    return best, meta


if __name__ == "__main__":
    print("\n=== Jinx Build Path Power Spike (minigun AA + W auto, 1->4 Core) ===")
    all_paths = _build_all_paths()
    print(f"Total unique paths in search space: {len(all_paths)}")
    rows_dedup, best_control = _rank_rows(all_paths)
    ranked = sorted(rows_dedup, key=lambda r: r["rel_dpg_score"], reverse=True)

    print(f"\nControl: {'-'.join(best_control['path'])} [{best_control['pkg_label']}] "
          f"| Weighted DPG {best_control['weighted_dpg']:.2f}")
    col_build, col_core, col_rep = 34, 18, 9
    header = (f"{'RK':>3} | {'BUILD(4C)':<{col_build}} | {'CTRL':>6} | "
              f"{'1C DPS/ΔDPG%':>{col_core}} | {'2C DPS/ΔDPG%':>{col_core}} | "
              f"{'3C DPS/ΔDPG%':>{col_core}} | {'4C DPS/ΔDPG%':>{col_core}} | {'RelDPG':>{col_rep}}")
    print(f"\nTop 30 + Control (RelDPG = control-normalised weighted DPG ×100, {CORE_WEIGHTS_LABEL})")
    print(header); print("-" * len(header))

    def _fmt_build(r):
        p = r["path"]
        return f"{'-'.join(ITEM_SHORT.get(k, k) for k in p)} [{r['pkg_label']}]"

    top_rows = ranked[:30]
    ctrl_rows = [r for r in ranked if r["is_control"]]
    out_rows = top_rows + [r for r in ctrl_rows if r not in top_rows]
    for rank, r in enumerate(out_rows, start=1):
        y = r["y"]; d = r["core_rel_delta_pct_4"]
        tag = "[CTRL]" if r["is_control"] else ""
        label = _fmt_build(r)
        label = label if len(label) <= col_build else label[:col_build - 3] + "..."
        cells = " | ".join(f"{y[i]:.1f}/{d[i]:+.1f}%".rjust(col_core) for i in range(4))
        print(f"{rank:>3} | {label:<{col_build}} | {tag:>6} | {cells} | {r['rel_dpg_score']:>{col_rep}.2f}")

    # 그래프: Top5 비컨트롤 + 컨트롤, 4코어 DPS 커브
    top5 = [r for r in ranked if not r["is_control"]][:5]
    plt.figure(figsize=(12, 8))
    colors = ["#E4572E", "#F3A712", "#54A24B", "#4C78A8", "#B279A2"]
    for i, r in enumerate(top5):
        lbl = f"Top{i+1} {_fmt_build(r)} (RelDPG {r['rel_dpg_score']:.2f})"
        plt.plot(r["x"], r["y"], color=colors[i % len(colors)], linewidth=2.4, marker="D", markersize=6, label=lbl)
    for r in ctrl_rows:
        lbl = f"[CTRL] {_fmt_build(r)} (RelDPG {r['rel_dpg_score']:.2f})"
        plt.plot(r["x"], r["y"], color="#111111", linewidth=2.8, marker="o", markersize=7, linestyle="--", label=lbl)
    plt.title("Jinx Power Spike: 4-Core Ranked Top5 + Control")
    plt.xlabel("Total Gold at Core Timing"); plt.ylabel("DPS (minigun AA + W)")
    plt.grid(True, alpha=0.3); plt.legend(loc="best", fontsize=8); plt.tight_layout()
    plt.show()
