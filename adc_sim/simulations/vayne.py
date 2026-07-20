from adc_sim.champion import Vayne, Target
import matplotlib.pyplot as plt
from adc_sim.runes import LethalTempo, PressTheAttack, CutDown
from adc_sim.engine import run_simulation
from adc_sim.data.items_registry import create_item_from_key
from adc_sim.data.items_data import pen_rule_ok
from adc_sim.settings import CORE_WEIGHTS_LABEL
from adc_sim.simulations.ashe import build_ashe_like_core_report_meta
from adc_sim.simulations.ranking_core import rank_builds

# 코어 단계별 고정 타겟 (Ashe/KaiSa/CogMaw 시뮬과 동일)
CORE_TARGET_STATS = {
    1: {"hp": 1700, "armor": 50, "mr": 25},
    2: {"hp": 1900, "armor": 70, "mr": 30},
    3: {"hp": 2400, "armor": 100, "mr": 50},
    4: {"hp": 2600, "armor": 120, "mr": 70},
}
CORE_VAYNE_LEVELS = {1: {"level": 9}, 2: {"level": 11}, 3: {"level": 13}, 4: {"level": 15}}

# 룬 라벨(파워컴페어/출력용) — CogMaw 미러
RUNE_LABELS = {LethalTempo: "LT", PressTheAttack: "PtA"}
RUNE_LONG_LABELS = {LethalTempo: "치명적 속도 (Lethal Tempo)",
                    PressTheAttack: "집중공격 (Press the Attack)"}


def build_target_for_core(core_tier):
    s = CORE_TARGET_STATS[core_tier]
    return Target(hp=s["hp"], armor=s["armor"], magic_resist=s["mr"],
                  bonus_hp=max(0, s["hp"] - 1500))


def _skill_levels_for_core(core_tier):
    """스킬 선마 Q→W→E, R=lvl 기반. spec §6 포인트정합표. [H-VAYNE-SKILL]
    core1(lvl9): q5/w3/r1 · core2(11): q5/w4/r2 · core3(13): q5/w5/r2 · core4(15): q5/w5/e3/r2.
    (E 는 DPS 미모델 → e_level 은 배열색인 하한 1 로 floor.)"""
    lvl = CORE_VAYNE_LEVELS[core_tier]["level"]
    q = 5
    w = {1: 3, 2: 4, 3: 5, 4: 5}[core_tier]
    e = {1: 1, 2: 1, 3: 1, 4: 3}[core_tier]
    r = 1 if lvl < 11 else (2 if lvl < 16 else 3)
    return q, w, e, r


def simulate_vayne_core_path(full_path, core_tier, doran_key="doranblade",
                             boots_key="berserker", rune_as_bonus=0.0,
                             keystone_cls=LethalTempo):
    """Vayne DPS + total gold for a core timing. R@t=0, Q 쿨마다(마나 바운드). K=2.

    full_path: 코어 키 리스트. core_tier: 1~4. doran/boots/rune_as: 패키지.
    keystone_cls: 키스톤 룬 클래스(LethalTempo|PressTheAttack). 보조룬은 CutDown 고정.
    (PtA·CutDown·CoupDeGrace 의 8% 대미지증가는 `_last_damage_amp` 를 통해 은화살 고정딜에도 자동 적용.)
    반환: (dps, total_cost).
    """
    target = build_target_for_core(core_tier)
    lvl = CORE_VAYNE_LEVELS[core_tier]["level"]
    q, w, e, r = _skill_levels_for_core(core_tier)
    vayne = Vayne(level=lvl, q_level=q, w_level=w, e_level=e, r_level=r)
    vayne.set_rune(keystone_cls())
    vayne.set_sub_rune(CutDown())

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
        vayne.add_item(it)
    vayne.bonus_as_percent += rune_as_bonus

    skill_plan = {
        "manual_casts": [(0.0, "r")],          # R t=0 1회
        "auto_cast": {"q": True, "r": False},  # Q 쿨마다
        "auto_order": ["q"],
    }
    _, dps, _ = run_simulation(vayne, target, verbose=False, skill_plan=skill_plan, respawn_to_full_kills=2)
    return dps, total_cost


# 컨트롤(베이스라인) = 사용자 확정 실전 온힛+크리 빌드. 탐색공간에 반드시 존재해야 함.
CONTROL_PATH = ("botrk", "guinsoo", "terminus", "pd")
_VAYNE_TOP1_CACHE = {}  # (keystone_cls, rank_by) → top1 dict (룬·랭킹기준별 캐시)

# 베인 전용 온힛+크리 풀 (spec §6). pen 배타 {ldr, mortal, terminus}.
CORE1_CANDIDATES = ["botrk", "guinsoo", "kraken", "terminus", "wit", "runaan", "pd",
                    "rfc", "statikk", "yuntal25", "c44", "storm", "collector"]
CORE2_CANDIDATES = ["botrk", "guinsoo", "kraken", "terminus", "wit", "runaan", "pd",
                    "ie", "rfc", "collector", "yuntal25", "statikk"]
CORE3_CANDIDATES = ["ie", "ldr", "guinsoo", "terminus", "pd", "collector", "wit", "kraken"]
CORE4_CANDIDATES = ["ie", "ldr", "pd", "runaan", "rfc", "collector", "kraken", "wit", "statikk", "terminus"]

ITEM_SHORT = {
    "botrk": "BotRK", "guinsoo": "Gui", "kraken": "Krk", "terminus": "Terminus",
    "wit": "Wit's", "runaan": "Runaan", "pd": "PD", "ie": "IE", "ldr": "LDR",
    "rfc": "RFC", "statikk": "Statikk", "yuntal25": "Yun", "c44": "C44",
    "storm": "Storm", "collector": "Collector",
}


def _build_all_paths():
    all_paths, seen = [], set()
    for c1 in CORE1_CANDIDATES:
        for c2 in CORE2_CANDIDATES:
            if len({c1, c2}) < 2:
                continue
            for c3 in CORE3_CANDIDATES:
                for c4 in CORE4_CANDIDATES:
                    if len({c1, c2, c3, c4}) < 4:
                        continue
                    if not pen_rule_ok((c1, c2, c3, c4)):
                        continue
                    path = (c1, c2, c3, c4)
                    if path in seen:
                        continue
                    seen.add(path)
                    all_paths.append(path)
    # 컨트롤이 풀에서 안 나오면 강제 삽입(순서 고정)
    if CONTROL_PATH not in seen:
        all_paths.append(CONTROL_PATH)
    return all_paths


def _rank_rows(all_paths, weights_raw=None, keystone_cls=LethalTempo):
    """전 (경로×패키지) 시뮬 → dedup → 컨트롤 정규화 RelDPG. (ranking_core 위임)
    keystone_cls: 키스톤 룬 클래스. LT 가 기본(기존 골든값 보존)."""
    def _sim(path, tier, doran_key, boots_key, rune_as_bonus):
        return simulate_vayne_core_path(path, tier, doran_key=doran_key,
                                        boots_key=boots_key, rune_as_bonus=rune_as_bonus,
                                        keystone_cls=keystone_cls)
    return rank_builds(_sim, all_paths, CONTROL_PATH, weights_raw=weights_raw)


def get_vayne_4core_top1_build(rank_by="dpg", keystone_cls=LethalTempo):
    """랭킹된 4코어 top1 빌드 + 컨트롤 메타 반환.
    rank_by: "dpg"(RelDPG) | "dps"(절대 가중DPS). keystone_cls: LT|PtA."""
    cache_key = (keystone_cls, rank_by)
    if cache_key in _VAYNE_TOP1_CACHE:
        return _VAYNE_TOP1_CACHE[cache_key]
    rows_dedup, best_control = _rank_rows(_build_all_paths(), keystone_cls=keystone_cls)
    sort_key = (lambda r: r["weighted_dps"]) if rank_by == "dps" else (lambda r: r["rel_dpg_score"])
    ranked = sorted(rows_dedup, key=sort_key, reverse=True)
    top1 = ranked[0]
    result = {
        "path": top1["path"], "doran": top1["doran"], "boots": top1["boots"],
        "rune_as": top1["rune_as"], "pkg_label": top1["pkg_label"],
        "score": top1["rel_dpg_score"], "weighted_dpg": top1["weighted_dpg"],
        "weighted_dps": top1["weighted_dps"],
        "keystone_cls": keystone_cls,
        "control_path": best_control["path"], "control_doran": best_control["doran"],
        "control_boots": best_control["boots"], "control_rune_as": best_control["rune_as"],
        "control_pkg": best_control["pkg_label"], "control_weighted_dpg": best_control["weighted_dpg"],
    }
    _VAYNE_TOP1_CACHE[cache_key] = result
    return result


def build_vayne_core_report_meta(full_path, core_tier):
    """직렬화용 리포트 메타(Ashe-like 공용 헬퍼 재사용)."""
    return build_ashe_like_core_report_meta("Vayne", full_path, core_tier)


def get_vayne_powercompare_builds():
    """power_compare 연동용 (best, meta).
    - best: 룬 무관 최강(LT·PtA top1 중 절대 weighted-DPG 우위) — CogMaw 방식과 동일.
    - meta: 컨트롤(botrk-guinsoo-terminus-pd, 최적 패키지) under 치속(LethalTempo) — 실전 기준.
    각 dict: path/doran/boots/rune_as/pkg_label/keystone_cls/rune_label/weighted_dpg.
    (LT·PtA 두 룬 전수 랭킹을 돌리므로 느리다 — 룬별 캐시됨.)
    """
    lt = get_vayne_4core_top1_build(rank_by="dpg", keystone_cls=LethalTempo)
    pta = get_vayne_4core_top1_build(rank_by="dpg", keystone_cls=PressTheAttack)
    src = lt if lt["weighted_dpg"] >= pta["weighted_dpg"] else pta
    best = {
        "path": src["path"], "doran": src["doran"], "boots": src["boots"],
        "rune_as": src["rune_as"], "pkg_label": src["pkg_label"],
        "keystone_cls": src["keystone_cls"],
        "rune_label": RUNE_LABELS[src["keystone_cls"]],
        "weighted_dpg": src["weighted_dpg"],
    }
    meta = {  # LT 결과의 control = 컨트롤(최적 패키지) — CogMaw meta 관례와 동일
        "path": lt["control_path"], "doran": lt["control_doran"],
        "boots": lt["control_boots"], "rune_as": lt["control_rune_as"],
        "pkg_label": lt["control_pkg"],
        "keystone_cls": LethalTempo, "rune_label": RUNE_LABELS[LethalTempo],
        "weighted_dpg": lt["control_weighted_dpg"],
    }
    return best, meta


def _run_vayne_ranking(keystone_cls, keystone_label, all_paths):
    """주어진 keystone(룬)으로 랭킹 표 1장 출력. 반환: (ranked, best_control)."""
    rows_dedup, best_control = _rank_rows(all_paths, keystone_cls=keystone_cls)
    ranked = sorted(rows_dedup, key=lambda r: r["rel_dpg_score"], reverse=True)

    print(f"\n{'=' * 28}  RUNE: {keystone_label}  {'=' * 28}")
    print(f"Control: {'-'.join(best_control['path'])} [{best_control['pkg_label']}] "
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

    return ranked, best_control


if __name__ == "__main__":
    print("\n=== Vayne Build Path Power Spike (W/Q auto + R@0, 1->4 Core) ===")
    all_paths = _build_all_paths()
    print(f"Total unique paths in search space: {len(all_paths)}")

    # 두 키스톤(치속·집공) 각각 랭킹 표 — CogMaw 미러. 보조룬 CutDown 은 simulate 내부 고정.
    # (PtA 8%·CutDown 8%·CoupDeGrace 8% 대미지증가는 은화살 고정딜에도 자동 적용 — _last_damage_amp 경유.)
    keystones = [(LethalTempo, RUNE_LONG_LABELS[LethalTempo]),
                 (PressTheAttack, RUNE_LONG_LABELS[PressTheAttack])]
    ranked_by_rune = []
    for _ks, _klabel in keystones:
        ranked, _ = _run_vayne_ranking(_ks, _klabel, all_paths)
        ranked_by_rune.append((ranked, _ks))

    # 그래프는 첫 룬(치속) 기준 1장 — CogMaw 관례와 동일.
    ranked, first_ks = ranked_by_rune[0]
    ctrl_rows = [r for r in ranked if r["is_control"]]

    def _fmt_build(r):
        p = r["path"]
        return f"{'-'.join(ITEM_SHORT.get(k, k) for k in p)} [{r['pkg_label']}]"

    top5 = [r for r in ranked if not r["is_control"]][:5]
    plt.figure(figsize=(12, 8))
    colors = ["#E4572E", "#F3A712", "#54A24B", "#4C78A8", "#B279A2"]
    for i, r in enumerate(top5):
        lbl = f"Top{i+1} {_fmt_build(r)} (RelDPG {r['rel_dpg_score']:.2f})"
        plt.plot(r["x"], r["y"], color=colors[i % len(colors)], linewidth=2.4, marker="D", markersize=6, label=lbl)
    for r in ctrl_rows:
        lbl = f"[CTRL] {_fmt_build(r)} (RelDPG {r['rel_dpg_score']:.2f})"
        plt.plot(r["x"], r["y"], color="#111111", linewidth=2.8, marker="o", markersize=7, linestyle="--", label=lbl)
    plt.title(f"Vayne Power Spike: 4-Core Ranked Top5 + Control ({RUNE_LABELS[first_ks]})")
    plt.xlabel("Total Gold at Core Timing"); plt.ylabel("DPS (AA + W silverbolts + Q, R@0)")
    plt.grid(True, alpha=0.3); plt.legend(loc="best", fontsize=8); plt.tight_layout()
    plt.show()
