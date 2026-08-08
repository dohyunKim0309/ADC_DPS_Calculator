"""코그모 1~5코어 receding-horizon 빌드 탐색 — 베인(vayne.py)과 동일 방법론.

각 코어 시점에서 "지금 살 아이템 + 상정 미래(5코어까지)"의 **코어별 마지널 DPG**를
γ-할인해 합산하고, 그 합이 최대인 조합의 **첫 아이템만 확정**한다. 다음 코어에서는
확정분을 기준으로 미래를 전부 다시 탐색한다(receding horizon). 공통 러너는
`simulations/receding_core.py` (vayne.py 구현과 동치 — tests/test_receding_core.py).

기존 `cogmaw.py`(1~4코어 가중 랭킹)와 `cogmaw_sequential.py`(코어 파워 레벨의 γ-할인합 DP)
는 그대로 둔다(AGENTS.md 5-4). 이 모듈은 "베인과 같은 척도"의 5코어 궤적을 추가로 준다.
  · cogmaw_sequential: power(집합) = 그 시점의 절대 DPS 또는 절대 DPG → 레벨(level) 기준
  · 이 모듈(=vayne 방식): 마지널 DPG = ΔDPS / (Δ골드/1000) → 증분(marginal) 기준

룬 2종(치명적 속도 / 집중공격) × ADC 패키지 A·B 각각 탐색한다(보조룬 CutDown 고정 —
simulate_cogmaw_core_path 내부 규약). 표만 출력하므로 헤드리스에서 안전하다.

실행: .venv/bin/python -m adc_sim.simulations.cogmaw_receding [gamma]
"""
import time

from adc_sim.data.items_data import ADC_PACKAGES
from adc_sim.runes import LethalTempo, PressTheAttack
from adc_sim.settings import DEFAULT_DISCOUNT_GAMMA
from adc_sim.simulations import receding_core
from adc_sim.simulations.cogmaw import (
    COGMAW_CORE_CANDIDATES,
    CONTROL_PATH,
    CONTROL2_PATH,
    CORE_COGMAW_LEVELS,
    simulate_cogmaw_core_path,
)

GAMMA = DEFAULT_DISCOUNT_GAMMA
HORIZON = 5

# 5코어 후보 = 4코어 후보 재사용(vayne.CORE5_CANDIDATES 관례와 동일).
# COGMAW_CORE_CANDIDATES[4] 는 후반 아이템 전부를 담고 있고, 빠진 것은 초반 전용
# (rfc/statikk/storm/yuntal)뿐이라 5코어 최적해에서 배제해도 실질 손실이 없다.
CANDIDATES_BY_SLOT = {
    1: list(COGMAW_CORE_CANDIDATES[1]),
    2: list(COGMAW_CORE_CANDIDATES[2]),
    3: list(COGMAW_CORE_CANDIDATES[3]),
    4: list(COGMAW_CORE_CANDIDATES[4]),
    5: list(COGMAW_CORE_CANDIDATES[4]),
}

RUNE_LABELS = {LethalTempo: "치속", PressTheAttack: "집공"}
RUNE_LONG_LABELS = {LethalTempo: "치명적 속도 (Lethal Tempo)",
                    PressTheAttack: "집중공격 (Press the Attack)"}

ITEM_SHORT = {
    "guinsoo": "Gui", "kraken": "Krk", "nashor": "Nashor", "terminus": "Terminus",
    "bot": "BotRK", "rfc": "RFC", "statikk": "Statikk", "storm": "Storm",
    "pd": "PD", "ie": "IE", "yuntal": "Yun", "shadowflame": "SF", "void": "Void",
    "dawn": "Dawn", "navori": "Navori", "wit": "Wit's", "c44": "C44",
    "ldr": "LDR", "mortal": "Mortal", "rabadon": "Rabadon",
}

REFERENCE_PATHS = (("CTRL", CONTROL_PATH), ("CTRL2", CONTROL2_PATH))


def _fmt_items(seq):
    """내부 아이템 키 시퀀스를 출력용 약칭 문자열로 변환한다."""
    return "-".join(ITEM_SHORT.get(key, key) for key in seq)


def build_cache(keystone_cls, pkg):
    """룬·시작 패키지를 고정한 코그모 시뮬 캐시를 만든다."""
    return receding_core.SimCache(
        simulate_cogmaw_core_path,
        sim_kwargs=dict(doran_key=pkg["doran"], boots_key=pkg["boots"],
                        rune_as_bonus=pkg["rune_as"], keystone_cls=keystone_cls),
        stack_sensitive_keys=(),   # 코그모 풀의 yuntal 은 구매 시점 분기가 없다([H-KOG-6])
    )


def solve_scenario(keystone_cls, pkg, gamma=GAMMA, horizon=HORIZON,
                   candidates_by_slot=None):
    """룬×패키지 1조합의 자유 궤적과 레퍼런스 빌드 비교를 계산한다.

    반환 dict: free(궤적 결과) / realized_score(확정 궤적을 같은 척도로 재채점) /
    references[(태그, 5코어 확장 궤적, 점수)] / cache_stats / elapsed.
    """
    if candidates_by_slot is None:
        candidates_by_slot = CANDIDATES_BY_SLOT
    started_at = time.time()
    cache = build_cache(keystone_cls, pkg)

    free = receding_core.solve_greedy(cache, candidates_by_slot, gamma, horizon)
    realized_score, _ = receding_core.evaluate_fixed_path(
        cache, free["trajectory"], gamma, horizon)

    references = []
    for tag, path in REFERENCE_PATHS:
        # 레퍼런스는 4코어 고정 → 5코어째만 같은 방법론으로 최적 연계를 붙여 동일 척도 비교.
        locked = receding_core.solve_greedy(
            cache, candidates_by_slot, gamma, horizon, initial_fixed=tuple(path))
        score, _ = receding_core.evaluate_fixed_path(
            cache, locked["trajectory"], gamma, horizon)
        references.append({"tag": tag, "trajectory": locked["trajectory"],
                           "score": score, "steps": locked["steps"]})

    return {"keystone_cls": keystone_cls, "pkg": pkg, "free": free,
            "realized_score": realized_score, "references": references,
            "cache_stats": cache.stats, "elapsed": time.time() - started_at,
            "gamma": gamma, "horizon": horizon}


def print_scenario(out):
    """한 시나리오의 궤적·코어별 선택·대안·레퍼런스 비교를 표로 출력한다."""
    keystone_cls, pkg = out["keystone_cls"], out["pkg"]
    gamma, horizon = out["gamma"], out["horizon"]
    label = f"{RUNE_LONG_LABELS[keystone_cls]} · {pkg['label']}"
    print(f"\n{'=' * 26}  {label}  {'=' * 26}")
    print(f"γ={gamma}, horizon={horizon}. 마지널 DPG 할인합 최대화 그리디 (베인 방식).")
    lvl_note = " · ".join(f"C{tier}=lvl{CORE_COGMAW_LEVELS[tier]['level']}"
                          for tier in range(1, horizon + 1))
    print(f"레벨: {lvl_note}")
    stats = out["cache_stats"]
    total = stats["hits"] + stats["misses"]
    hit_rate = stats["hits"] / total * 100.0 if total else 0.0
    print(f"시뮬 캐시: {stats['hits']:>8} hits / {stats['misses']:>5} misses "
          f"({hit_rate:.1f}% hit) · {out['elapsed']:.1f}s")

    print(f"\n최종 궤적: {' → '.join(ITEM_SHORT.get(k, k) for k in out['free']['trajectory'])}")
    print(f"확정 궤적 점수(동일 척도 할인합): {out['realized_score']:.2f}")
    print()
    header = (f"{'Slot':>4} | {'Pick':<10} | {'DPS':>9} | {'Gold':>6} | {'ΔDPS':>9} | "
              f"{'ΔGold':>6} | {'MarginalDPG':>11} | {'Score':>8} | 대안(top3)")
    print(header)
    print("-" * 132)
    for step in out["free"]["steps"]:
        delta_dps = step["dps"] - step["baseline_dps_prev"]
        delta_gold = step["gold"] - step["baseline_gold_prev"]
        alternatives = " / ".join(
            f"{ITEM_SHORT.get(alt['item'], alt['item'])}:{alt['score']:.1f}"
            for alt in step["alternatives"])
        print(f"{step['slot']:>4} | {ITEM_SHORT.get(step['item'], step['item']):<10} | "
              f"{step['dps']:>9.1f} | {step['gold']:>6} | {delta_dps:>9.1f} | "
              f"{delta_gold:>6} | {step['marginal_dpg']:>11.2f} | {step['score']:>8.2f} | "
              f"{alternatives}")

    print("\n[각 슬롯 결정 시 상정한 미래 조합 (winner)]")
    for step in out["free"]["steps"]:
        future = step["future_path_winner"]
        rest = future[1:] if len(future) > 1 else ()
        rest_text = _fmt_items(rest) if rest else "(none)"
        print(f"  Slot {step['slot']} → {ITEM_SHORT.get(step['item'], step['item'])} "
              f"+ 상정 미래: {rest_text}")

    print("\n[레퍼런스 빌드 — 4코어 고정 + 5코어째만 같은 방법론으로 최적 연계]")
    for ref in out["references"]:
        gap = out["realized_score"] - ref["score"]
        print(f"  [{ref['tag']:<5}] {_fmt_items(ref['trajectory']):<44} "
              f"점수 {ref['score']:>7.2f}  (자유 궤적 대비 {-gap:+.2f})")


def run_all(gamma=GAMMA, keystones=(LethalTempo, PressTheAttack), packages=None):
    """룬 × 패키지 전 시나리오를 탐색해 출력하고 결과 리스트를 반환한다."""
    if packages is None:
        packages = ADC_PACKAGES
    results = []
    for keystone_cls in keystones:
        for pkg in packages:
            out = solve_scenario(keystone_cls, pkg, gamma=gamma)
            print_scenario(out)
            results.append(out)
    print_summary(results)
    return results


def print_summary(results):
    """룬별 최적 패키지·궤적 요약표를 출력한다."""
    print(f"\n{'=' * 30}  요약: 룬별 최고 템트리  {'=' * 30}")
    header = (f"{'Rune':<6} | {'Pkg':<10} | {'Trajectory (1→5 core)':<48} | "
              f"{'Score':>7} | {'5C DPS':>8}")
    print(header)
    print("-" * len(header))
    best_by_rune = {}
    for out in results:
        rune = RUNE_LABELS[out["keystone_cls"]]
        final_dps = out["free"]["steps"][-1]["dps"]
        row = (rune, out["pkg"]["label"], _fmt_items(out["free"]["trajectory"]),
               out["realized_score"], final_dps)
        print(f"{row[0]:<6} | {row[1]:<10} | {row[2]:<48} | {row[3]:>7.2f} | {row[4]:>8.1f}")
        if rune not in best_by_rune or row[3] > best_by_rune[rune][3]:
            best_by_rune[rune] = row
    print("\n[룬별 최선 패키지]")
    for rune, row in best_by_rune.items():
        print(f"  {rune}: {row[2]}  [{row[1]}]  점수 {row[3]:.2f} · 5코어 DPS {row[4]:.1f}")


def run_cli(args=None):
    """CLI 진입점. 첫 인자로 γ(0<γ≤1)를 받는다."""
    import sys

    cli_args = list(sys.argv[1:] if args is None else args)
    gamma = GAMMA
    if cli_args:
        try:
            gamma = float(cli_args[0])
            if not (0.0 < gamma <= 1.0):
                raise ValueError
        except ValueError:
            print(f"[warn] gamma 인자 파싱 실패({cli_args[0]!r}) — 기본 {GAMMA} 사용")
            gamma = GAMMA
    run_all(gamma=gamma)


if __name__ == "__main__":
    run_cli()
