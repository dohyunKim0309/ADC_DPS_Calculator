"""베인 LT(치속) vs PtA(집공) 비교 — 룬별 top 10 + 레퍼런스(컨트롤) 빌드의
코어 타이밍별 DPS/DPG 나열.

각 룬 별로 전수 랭킹(_rank_rows) 수행 → 자기 룬의 RelDPG 상위 10 + 컨트롤을
그대로 출력. 룬 간 직접 비교가 아니라, 룬별 어떤 빌드가 어떤 타이밍에
얼마의 DPS/DPG 를 내는지 그대로 뽑아 낸다.

CLI: `-m adc_sim.simulations.vayne_rune_compare [top_n]` (기본 10).
"""
import sys
from adc_sim.runes import LethalTempo, PressTheAttack
from adc_sim.simulations.vayne import (
    _build_all_paths, _rank_rows, ITEM_SHORT, CORE_VAYNE_LEVELS, RUNE_LONG_LABELS,
)


def _select_top(rows, top_n):
    """RelDPG 상위 top_n(컨트롤 제외) + 컨트롤 순서로 반환."""
    non_ctrl = sorted([r for r in rows if not r["is_control"]],
                      key=lambda r: r["rel_dpg_score"], reverse=True)
    ctrl = [r for r in rows if r["is_control"]]
    return non_ctrl[:top_n] + ctrl


def _fmt_build_label(r, col_build):
    p = r["path"]
    body = "-".join(ITEM_SHORT.get(k, k) for k in p)
    label = f"{body} [{r['pkg_label']}]"
    return label if len(label) <= col_build else label[:col_build - 3] + "..."


def print_rune_table(rune_label, rows, top_n):
    print(f"\n{'=' * 24}  {rune_label}  {'=' * 24}")
    print(f"Top {top_n} + Reference (RelDPG 상위 {top_n} + 컨트롤 BotRK-Gui-Terminus-PD).")
    print("코어 타이밍별 DPS 와 DPG (=DPS / (Gold/1000)) — 절대값.")
    lvl_note = " · ".join(f"C{t}=lvl{CORE_VAYNE_LEVELS[t]['level']}" for t in range(1, 5))
    print(f"레벨: {lvl_note}\n")

    col_build, col_val = 40, 9
    header = (
        f"{'RK':>4} | {'BUILD':<{col_build}} | "
        f"{'1C DPS':>{col_val}} | {'1C DPG':>{col_val}} | "
        f"{'2C DPS':>{col_val}} | {'2C DPG':>{col_val}} | "
        f"{'3C DPS':>{col_val}} | {'3C DPG':>{col_val}} | "
        f"{'4C DPS':>{col_val}} | {'4C DPG':>{col_val}} | "
        f"{'RelDPG':>{col_val}}"
    )
    print(header); print("-" * len(header))
    for rank_idx, r in enumerate(rows, start=1):
        rk_cell = "[C]" if r["is_control"] else f"{rank_idx}"
        label = _fmt_build_label(r, col_build)
        dps = r["y"]; dpg = r["dpg"]
        cells = " | ".join(
            f"{dps[i]:>{col_val}.1f} | {dpg[i]:>{col_val}.2f}" for i in range(4)
        )
        print(f"{rk_cell:>4} | {label:<{col_build}} | {cells} | {r['rel_dpg_score']:>{col_val}.2f}")


def run(top_n=10):
    all_paths = _build_all_paths()
    print(f"Total unique paths in search space: {len(all_paths)}")
    for keystone_cls, label in [(LethalTempo, RUNE_LONG_LABELS[LethalTempo]),
                                (PressTheAttack, RUNE_LONG_LABELS[PressTheAttack])]:
        rows, _ = _rank_rows(all_paths, keystone_cls=keystone_cls)
        selected = _select_top(rows, top_n)
        print_rune_table(label, selected, top_n)


if __name__ == "__main__":
    top_n = 10
    if len(sys.argv) > 1:
        try:
            top_n = max(1, int(sys.argv[1]))
        except ValueError:
            print(f"[warn] top_n 인자 파싱 실패({sys.argv[1]!r}) — 기본 10 사용")
    print(f"\n=== Vayne LT vs PtA — 룬별 Top {top_n} + Reference (≈1분 소요) ===")
    run(top_n=top_n)
