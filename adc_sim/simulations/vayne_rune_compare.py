"""베인 LT(치속) vs PtA(집공) 비교 — top 10 + 컨트롤, 코어 타이밍별 DPS/DPG 나열.

각 룬 별로 전수 랭킹(_rank_rows) 수행 → 정렬키는 절대 weighted_dpg(4C).
같은 (경로 sorted-combo)에서 두 룬은 dedup 시 각자 최적 패키지를 골랐을 수 있으므로,
LT/PtA 각 컬럼에 자기 룬 기준 최적 패키지를 함께 표기(다를 때만 두 값).

원한다면 top_n 을 CLI 인자로 넘겨 조정: `... vayne_rune_compare 15`.
"""
import sys
from adc_sim.runes import LethalTempo, PressTheAttack
from adc_sim.simulations.vayne import (
    _build_all_paths, _rank_rows, ITEM_SHORT, CORE_VAYNE_LEVELS,
)


def compare_lt_vs_pta(top_n=10):
    """반환: [{combo, path, lt_pkg, pta_pkg, is_control, lt_dps[4], lt_dpg[4],
              pta_dps[4], pta_dpg[4], lt_wdpg, pta_wdpg}, ...]
    정렬: 컨트롤 제외 max(lt_wdpg, pta_wdpg) desc, top_n; 뒤에 컨트롤 append.
    """
    all_paths = _build_all_paths()
    lt_rows, _ = _rank_rows(all_paths, keystone_cls=LethalTempo)
    pta_rows, _ = _rank_rows(all_paths, keystone_cls=PressTheAttack)
    lt_by = {tuple(sorted(r["path"])): r for r in lt_rows}
    pta_by = {tuple(sorted(r["path"])): r for r in pta_rows}
    # all_paths·ADC_PACKAGES 동일 → 두 dict 는 combo 집합이 완전 일치.
    rows = []
    for combo, lt_r in lt_by.items():
        pta_r = pta_by[combo]
        rows.append({
            "combo": combo, "path": lt_r["path"],
            "lt_pkg": lt_r["pkg_label"], "pta_pkg": pta_r["pkg_label"],
            "is_control": lt_r["is_control"],
            "lt_dps": list(lt_r["y"]), "lt_dpg": list(lt_r["dpg"]),
            "pta_dps": list(pta_r["y"]), "pta_dpg": list(pta_r["dpg"]),
            "lt_wdpg": lt_r["weighted_dpg"],
            "pta_wdpg": pta_r["weighted_dpg"],
            "max_wdpg": max(lt_r["weighted_dpg"], pta_r["weighted_dpg"]),
        })
    non_ctrl = sorted([r for r in rows if not r["is_control"]],
                      key=lambda r: r["max_wdpg"], reverse=True)
    ctrl = [r for r in rows if r["is_control"]]
    return non_ctrl[:top_n] + ctrl


def _fmt_build_label(r, col_build):
    p = r["path"]
    body = "-".join(ITEM_SHORT.get(k, k) for k in p)
    if r["lt_pkg"] == r["pta_pkg"]:
        pkg = f"[{r['lt_pkg']}]"
    else:
        pkg = f"[LT:{r['lt_pkg']} / PtA:{r['pta_pkg']}]"
    label = f"{body} {pkg}"
    return label if len(label) <= col_build else label[:col_build - 3] + "..."


def _pct(a, b):
    """b 대비 a 변화율(%): (a-b)/b*100. b==0 이면 0."""
    return ((a - b) / b * 100.0) if b else 0.0


def print_compare(rows):
    print(f"\n=== Vayne LT vs PtA — Top {len([r for r in rows if not r['is_control']])} + Control, 코어 타이밍별 ===")
    print("정렬: max(LT weighted-DPG, PtA weighted-DPG). 각 룬은 자기 최적 패키지 사용.")
    print("우세(win) = 해당 코어 DPG 가 더 높은 룬. ΔDPS/ΔDPG = (PtA - LT) / LT × 100.")
    print()

    col_build, col_val = 40, 10
    header = (
        f"{'RK':>4} | {'BUILD':<{col_build}} | "
        f"{'LT DPS':>{col_val}} | {'PtA DPS':>{col_val}} | {'ΔDPS%':>{col_val}} | "
        f"{'LT DPG':>{col_val}} | {'PtA DPG':>{col_val}} | {'ΔDPG%':>{col_val}} | {'win':>4}"
    )

    n_top = len([r for r in rows if not r["is_control"]])
    for tier in range(1, 5):
        lvl = CORE_VAYNE_LEVELS[tier]["level"]
        print(f"[Core {tier} · lvl {lvl}]")
        print(header)
        print("-" * len(header))
        for rank_idx, r in enumerate(rows, start=1):
            lt_dps = r["lt_dps"][tier - 1]
            pta_dps = r["pta_dps"][tier - 1]
            lt_dpg = r["lt_dpg"][tier - 1]
            pta_dpg = r["pta_dpg"][tier - 1]
            d_dps = _pct(pta_dps, lt_dps)
            d_dpg = _pct(pta_dpg, lt_dpg)
            win = "PtA" if pta_dpg > lt_dpg else ("LT" if lt_dpg > pta_dpg else "=")
            if r["is_control"]:
                rk_cell = "[C]"
            else:
                rk_cell = f"{rank_idx}"
            label = _fmt_build_label(r, col_build)
            print(
                f"{rk_cell:>4} | {label:<{col_build}} | "
                f"{lt_dps:>{col_val}.2f} | {pta_dps:>{col_val}.2f} | {d_dps:>+{col_val - 1}.2f}% | "
                f"{lt_dpg:>{col_val}.2f} | {pta_dpg:>{col_val}.2f} | {d_dpg:>+{col_val - 1}.2f}% | {win:>4}"
            )
        print()

    # 요약: 4C weighted-DPG 절대 비교(dedup 결과 그대로)
    print("[Summary · 4C weighted-DPG (절대값, 룬간 직접 비교)]")
    sum_header = (
        f"{'RK':>4} | {'BUILD':<{col_build}} | "
        f"{'LT wDPG':>{col_val}} | {'PtA wDPG':>{col_val}} | {'ΔwDPG%':>{col_val}} | {'win':>4}"
    )
    print(sum_header); print("-" * len(sum_header))
    for rank_idx, r in enumerate(rows, start=1):
        d = _pct(r["pta_wdpg"], r["lt_wdpg"])
        win = "PtA" if r["pta_wdpg"] > r["lt_wdpg"] else ("LT" if r["lt_wdpg"] > r["pta_wdpg"] else "=")
        rk_cell = "[C]" if r["is_control"] else f"{rank_idx}"
        label = _fmt_build_label(r, col_build)
        print(
            f"{rk_cell:>4} | {label:<{col_build}} | "
            f"{r['lt_wdpg']:>{col_val}.2f} | {r['pta_wdpg']:>{col_val}.2f} | {d:>+{col_val - 1}.2f}% | {win:>4}"
        )


if __name__ == "__main__":
    top_n = 10
    if len(sys.argv) > 1:
        try:
            top_n = max(1, int(sys.argv[1]))
        except ValueError:
            print(f"[warn] top_n 인자 파싱 실패({sys.argv[1]!r}) — 기본 10 사용")
    print(f"\n=== Vayne LT vs PtA 비교 (top_n={top_n}) — 두 룬 전수 랭킹 실행(≈1분 소요) ===")
    all_paths = _build_all_paths()
    print(f"Total unique paths in search space: {len(all_paths)}")
    rows = compare_lt_vs_pta(top_n=top_n)
    print_compare(rows)
