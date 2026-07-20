"""베인 LT(치속) vs PtA(집공) 비교 — 단일 top 10 + 레퍼런스(컨트롤),
각 빌드마다 두 룬의 전체 DPS/DPG(코어 1~4) 를 함께 표기.

Top 10 선정: 각 룬 별 전수 랭킹 후 max(LT weighted-DPG, PtA weighted-DPG) 4C 로 정렬.
같은 (경로 sorted-combo)에서 두 룬은 dedup 시 서로 다른 최적 패키지를 뽑았을 수
있으므로, 각 룬 행마다 그 룬 기준 최적 패키지를 함께 표기.

CLI: `-m adc_sim.simulations.vayne_rune_compare [top_n]` (기본 10).
"""
import sys
from adc_sim.runes import LethalTempo, PressTheAttack
from adc_sim.simulations.vayne import (
    _build_all_paths, _rank_rows, ITEM_SHORT, CORE_VAYNE_LEVELS,
)


def compare_lt_vs_pta(top_n=10):
    """반환: [{combo, path, lt_pkg, pta_pkg, is_control,
              lt_dps[4], lt_dpg[4], pta_dps[4], pta_dpg[4],
              lt_wdpg, pta_wdpg, max_wdpg}, ...]
    정렬: 컨트롤 제외 max(lt_wdpg, pta_wdpg) desc, top_n; 뒤에 컨트롤 append.
    """
    all_paths = _build_all_paths()
    lt_rows, _ = _rank_rows(all_paths, keystone_cls=LethalTempo)
    pta_rows, _ = _rank_rows(all_paths, keystone_cls=PressTheAttack)
    lt_by = {tuple(sorted(r["path"])): r for r in lt_rows}
    pta_by = {tuple(sorted(r["path"])): r for r in pta_rows}
    # all_paths·ADC_PACKAGES 동일 → 두 dict combo 집합이 완전 일치.
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


def _fmt_path(r):
    return "-".join(ITEM_SHORT.get(k, k) for k in r["path"])


def print_rows(rows, top_n):
    print(f"\n=== Vayne Top {top_n} + Reference — 룬(LT/PtA)별 전체 DPS/DPG ===")
    print("Top 선정: max(LT weighted-DPG, PtA weighted-DPG) 4C. 각 룬 행은 자기 룬 기준 최적 패키지.")
    lvl_note = " · ".join(f"C{t}=lvl{CORE_VAYNE_LEVELS[t]['level']}" for t in range(1, 5))
    print(f"레벨: {lvl_note}\n")

    col_rune, col_val = 4, 10
    header = (
        f"{'RUNE':>{col_rune}} | {'PKG':<9} | "
        f"{'1C DPS':>{col_val}} | {'1C DPG':>{col_val}} | "
        f"{'2C DPS':>{col_val}} | {'2C DPG':>{col_val}} | "
        f"{'3C DPS':>{col_val}} | {'3C DPG':>{col_val}} | "
        f"{'4C DPS':>{col_val}} | {'4C DPG':>{col_val}} | "
        f"{'wDPG':>{col_val}}"
    )

    for rank_idx, r in enumerate(rows, start=1):
        rk_cell = "[Reference]" if r["is_control"] else f"[Rank {rank_idx}]"
        print(f"{rk_cell} {_fmt_path(r)}")
        print(header)
        print("-" * len(header))
        for rune, pkg, dps, dpg, wdpg in [
            ("LT",  r["lt_pkg"],  r["lt_dps"],  r["lt_dpg"],  r["lt_wdpg"]),
            ("PtA", r["pta_pkg"], r["pta_dps"], r["pta_dpg"], r["pta_wdpg"]),
        ]:
            cells = " | ".join(
                f"{dps[i]:>{col_val}.1f} | {dpg[i]:>{col_val}.2f}" for i in range(4)
            )
            print(f"{rune:>{col_rune}} | {pkg:<9} | {cells} | {wdpg:>{col_val}.2f}")
        print()


if __name__ == "__main__":
    top_n = 10
    if len(sys.argv) > 1:
        try:
            top_n = max(1, int(sys.argv[1]))
        except ValueError:
            print(f"[warn] top_n 인자 파싱 실패({sys.argv[1]!r}) — 기본 10 사용")
    print(f"\n=== Vayne LT vs PtA — 두 룬 전수 랭킹 후 통합 Top {top_n} + Reference (≈1분) ===")
    rows = compare_lt_vs_pta(top_n=top_n)
    print_rows(rows, top_n)
