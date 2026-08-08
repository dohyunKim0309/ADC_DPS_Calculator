"""Jinx 4코어 빌드 랭킹 — 장거리 로켓(Fishbones) 평타 + W(Zap!) 주기 넛지. K=2.

vayne.py 미러. 크리 ADC 라 Ashe 공유 인프라 재사용:
  · 후보 풀 = `_build_ashe_4core_all_paths()` (크리/공속 풀)
  · 컨트롤 = kraken-pd-ie-ldr (타 크리 ADC 와 일관; 탐색공간 필수)
  · 레벨표 = CORE_JINX_LEVELS (챔프 레벨만; 스킬레벨은 로컬 표준 선마)

모델 가정(사용자 합의 2026-07):
  · 전용 랭킹과 챔피언 비교는 긴 사거리 Q 로켓(Fishbones) 고정.
    미니건 모드는 ``simulate_jinx_core_path(..., q_mode="minigun")``으로 비교 가능하게 보존.
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
from adc_sim.data.items_data import ADC_PACKAGES, pen_rule_ok
from adc_sim.settings import CORE_WEIGHTS_RAW, CORE_WEIGHTS_LABEL, DEFAULT_DISCOUNT_GAMMA
from adc_sim.simulations.ashe import (
    build_ashe_like_core_report_meta, _build_ashe_4core_all_paths,
    CORE_JINX_LEVELS, build_target_for_core,
    CORE1_CANDIDATES as ASHE_CORE1_CANDIDATES,
    CORE2_CANDIDATES as ASHE_CORE2_CANDIDATES,
    CORE3_CANDIDATES as ASHE_CORE3_CANDIDATES,
    CORE4_CANDIDATES as ASHE_CORE4_CANDIDATES,
    CORE5_CANDIDATES as ASHE_CORE5_CANDIDATES,
)


JINX_RANKING_Q_MODE = "fishbones"
JINX_Q_MODES = frozenset(("fishbones", "minigun"))


def _jinx_skill_levels_for_core(core_tier):
    """스킬 선마 R>Q>W>E (표준 징크스). Q 선마 → 미니건 +130% 조기 확보.
    C1(lvl9): q5/w2 · C2(11): q5/w3 · C3~5: q5/w5. E·R 미모델."""
    q = 5
    w = {1: 2, 2: 3, 3: 5, 4: 5, 5: 5}[core_tier]
    return q, w


def simulate_jinx_core_path(full_path, core_tier, doran_key="doranblade",
                            boots_key="berserker", rune_as_bonus=0.0,
                            q_mode=JINX_RANKING_Q_MODE):
    """Return Jinx DPS and gold for one core timing and selected Q weapon mode.

    ``q_mode`` defaults to the dedicated ranking's long-range Fishbones mode. Passing
    ``"minigun"`` preserves the previous fully-stacked minigun comparison behavior.
    ``full_path`` is the core path, and ``core_tier`` selects its active 1~5 prefix.
    반환: (dps, total_cost).
    """
    if q_mode not in JINX_Q_MODES:
        raise ValueError(f"Unknown Jinx Q mode: {q_mode}")
    target = build_target_for_core(core_tier)
    lvl = CORE_JINX_LEVELS[core_tier]["level"]
    q, w = _jinx_skill_levels_for_core(core_tier)
    minigun_stacks = 3 if q_mode == "minigun" else 0
    jinx = Jinx(level=lvl, q_level=q, w_level=w, minigun_stacks=minigun_stacks, q_mode=q_mode)
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
    "bt": "BT", "ga": "GA", "mercurial": "Mercurial",
}


def _build_all_paths():
    paths = list(_build_ashe_4core_all_paths())   # 크리/공속 풀 (Ashe 공유)
    if CONTROL_PATH not in set(paths):
        paths.append(CONTROL_PATH)
    return paths


def _rank_rows(all_paths, q_mode=JINX_RANKING_Q_MODE, dedupe_by="dpg"):
    """Simulate paths and retain each item combo's best package for the requested metric.

    ``dedupe_by`` is ``"dps"`` for a true maximum-DPS search and ``"dpg"`` for the
    legacy gold-efficiency ranking. Rows still contain both metrics and control-relative DPG.
    """
    if dedupe_by not in ("dps", "dpg"):
        raise ValueError(f"Unknown Jinx dedupe metric: {dedupe_by}")
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
                d, c = simulate_jinx_core_path(path, tier, q_mode=q_mode, **kw)
                dps_list.append(d); cost_list.append(c)
            dpg = [dps_list[i] / (cost_list[i] / 1000.0) if cost_list[i] > 0 else 0.0 for i in range(4)]
            rows.append({
                "path": path, "doran": pkg["doran"], "boots": pkg["boots"],
                "rune_as": pkg["rune_as"], "pkg_label": pkg["label"],
                "x": cost_list, "y": dps_list, "dpg": dpg,
                "is_control": tuple(sorted(path)) == ctrl_combo,
                "q_mode": q_mode,
                "dedupe_eff_dpg": sum(dedupe_weight_raw[i] * dpg[i] for i in range(4)),
                "dedupe_eff_dps": sum(dedupe_weight_raw[i] * dps_list[i] for i in range(4)),
            })

    dedupe_key = f"dedupe_eff_{dedupe_by}"
    dedupe_best = {}
    for r in rows:
        key = tuple(sorted(r["path"]))
        if key not in dedupe_best or r[dedupe_key] > dedupe_best[key][dedupe_key]:
            dedupe_best[key] = r
    rows_dedup = list(dedupe_best.values())

    # 컨트롤은 정규 순서(CONTROL_PATH)로 고정
    rows_dedup = [r for r in rows_dedup if not r["is_control"]]
    ctrl_cands = [r for r in rows if tuple(r["path"]) == CONTROL_PATH]
    if ctrl_cands:
        rows_dedup.append(max(ctrl_cands, key=lambda r: r[dedupe_key]))

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


def get_jinx_4core_top1_build(rank_by="dps", q_mode=JINX_RANKING_Q_MODE):
    """Return Jinx's top 4-core build for weighted DPS or relative DPG.

    The default is the highest weighted DPS under long-range Fishbones. The old minigun
    or DPG searches remain available through explicit ``q_mode`` and ``rank_by`` arguments.
    """
    if rank_by not in ("dps", "dpg"):
        raise ValueError(f"Unknown Jinx rank metric: {rank_by}")
    if q_mode not in JINX_Q_MODES:
        raise ValueError(f"Unknown Jinx Q mode: {q_mode}")
    cache_key = (rank_by, q_mode)
    if cache_key in _JINX_TOP1_CACHE:
        return _JINX_TOP1_CACHE[cache_key]
    rows_dedup, best_control = _rank_rows(_build_all_paths(), q_mode=q_mode, dedupe_by=rank_by)
    sort_key = (lambda r: r["weighted_dps"]) if rank_by == "dps" else (lambda r: r["rel_dpg_score"])
    ranked = sorted(rows_dedup, key=sort_key, reverse=True)
    top1 = ranked[0]
    result = {
        "path": top1["path"], "doran": top1["doran"], "boots": top1["boots"],
        "rune_as": top1["rune_as"], "pkg_label": top1["pkg_label"],
        "score": top1["rel_dpg_score"], "weighted_dpg": top1["weighted_dpg"],
        "weighted_dps": top1["weighted_dps"], "q_mode": q_mode, "rank_by": rank_by,
        "control_path": best_control["path"], "control_doran": best_control["doran"],
        "control_boots": best_control["boots"], "control_rune_as": best_control["rune_as"],
        "control_pkg": best_control["pkg_label"], "control_weighted_dpg": best_control["weighted_dpg"],
    }
    _JINX_TOP1_CACHE[cache_key] = result
    return result


def build_jinx_core_report_meta(full_path, core_tier, q_mode=JINX_RANKING_Q_MODE):
    """Return serializable Jinx report metadata including the selected Q mode."""
    meta = build_ashe_like_core_report_meta("Jinx", full_path, core_tier)
    meta["q_mode"] = q_mode
    return meta


def get_jinx_powercompare_builds():
    """power_compare 연동용 (best, meta).
    - best: 장거리 Fishbones 조건의 절대 weighted-DPS top1.
    - meta: 같은 Fishbones 조건의 컨트롤(kraken-pd-ie-ldr, DPS 최적 패키지).
    각 dict: path/doran/boots/rune_as/pkg_label/weighted_dpg.
    """
    best_src = get_jinx_4core_top1_build(rank_by="dps", q_mode=JINX_RANKING_Q_MODE)
    best = {
        "path": best_src["path"], "doran": best_src["doran"], "boots": best_src["boots"],
        "rune_as": best_src["rune_as"], "pkg_label": best_src["pkg_label"],
        "weighted_dpg": best_src["weighted_dpg"], "weighted_dps": best_src["weighted_dps"],
        "q_mode": best_src["q_mode"],
    }
    meta = {
        "path": best_src["control_path"], "doran": best_src["control_doran"],
        "boots": best_src["control_boots"], "rune_as": best_src["control_rune_as"],
        "pkg_label": best_src["control_pkg"], "weighted_dpg": best_src["control_weighted_dpg"],
        "q_mode": best_src["q_mode"],
    }
    return best, meta


GAMMA = DEFAULT_DISCOUNT_GAMMA
HORIZON = 5
# 징크스 전용 랭킹은 기존부터 애쉬 크리/공속 풀을 공유하므로 5코어도 애쉬 후보를 사용한다.
CANDIDATES_BY_SLOT = {
    1: list(ASHE_CORE1_CANDIDATES),
    2: list(ASHE_CORE2_CANDIDATES),
    3: list(ASHE_CORE3_CANDIDATES),
    4: list(ASHE_CORE4_CANDIDATES),
    5: list(ASHE_CORE5_CANDIDATES),
}


class SimCache:
    """아이템 집합과 윤탈 구매 시점을 키로 징크스 DPS·골드를 메모이즈한다."""

    def __init__(self, package, q_mode=JINX_RANKING_Q_MODE):
        """시작 패키지와 Q 무기 모드를 고정한 징크스 탐색 캐시를 초기화한다."""
        self.kw = {
            "doran_key": package["doran"],
            "boots_key": package["boots"],
            "rune_as_bonus": package["rune_as"],
            "q_mode": q_mode,
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
        result = simulate_jinx_core_path(list(items_tuple), len(items_tuple), **self.kw)
        self.cache[key] = result
        return result


def _enumerate_future_combos(fixed, from_slot, horizon=HORIZON):
    """확정 코어 뒤에서 중복·관통 제약을 만족하는 징크스 미래 조합을 생성한다."""
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
    """매 슬롯에서 미래 할인 마지널 DPG를 재탐색해 징크스 1~5코어 궤적을 반환한다."""
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


def print_scenario(label, out, cache, gamma=None):
    """징크스 receding-horizon 최종 궤적과 슬롯별 선택·대안을 출력한다."""
    if gamma is None:
        gamma = GAMMA
    print(f"\n{'=' * 22}  Jinx Fishbones · {label}  {'=' * 22}")
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
    """장거리 Fishbones 징크스의 두 ADC 패키지를 베인식 receding-horizon으로 탐색한다."""
    if gamma is None:
        gamma = GAMMA
    for package in ADC_PACKAGES:
        cache = SimCache(package)
        print_scenario(package["label"], solve_greedy(cache, gamma=gamma), cache, gamma=gamma)


def main_legacy_ranking():
    """교체 전 징크스 4코어 weighted-DPS 전수 랭킹·그래프를 실행한다."""
    print("\n=== Jinx Build Path Power Spike (long-range Fishbones AA + W auto, 1->4 Core) ===")
    all_paths = _build_all_paths()
    print(f"Total unique paths in search space: {len(all_paths)}")
    rows_dedup, best_control = _rank_rows(all_paths, q_mode=JINX_RANKING_Q_MODE, dedupe_by="dps")
    ranked = sorted(rows_dedup, key=lambda r: r["weighted_dps"], reverse=True)

    print(f"\nControl: {'-'.join(best_control['path'])} [{best_control['pkg_label']}] "
          f"| Weighted DPG {best_control['weighted_dpg']:.2f}")
    col_build, col_core, col_rep = 34, 18, 9
    header = (f"{'RK':>3} | {'BUILD(4C)':<{col_build}} | {'CTRL':>6} | "
              f"{'1C DPS/ΔDPG%':>{col_core}} | {'2C DPS/ΔDPG%':>{col_core}} | "
              f"{'3C DPS/ΔDPG%':>{col_core}} | {'4C DPS/ΔDPG%':>{col_core}} | "
              f"{'WtDPS':>{col_rep}} | {'RelDPG':>{col_rep}}")
    print(f"\nTop 30 + Control (rank by weighted DPS, {CORE_WEIGHTS_LABEL}; RelDPG shown for reference)")
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
        print(
            f"{rank:>3} | {label:<{col_build}} | {tag:>6} | {cells} | "
            f"{r['weighted_dps']:>{col_rep}.1f} | {r['rel_dpg_score']:>{col_rep}.2f}"
        )

    # 그래프: Top5 비컨트롤 + 컨트롤, 4코어 DPS 커브
    top5 = [r for r in ranked if not r["is_control"]][:5]
    plt.figure(figsize=(12, 8))
    colors = ["#E4572E", "#F3A712", "#54A24B", "#4C78A8", "#B279A2"]
    for i, r in enumerate(top5):
        lbl = f"Top{i+1} {_fmt_build(r)} (WtDPS {r['weighted_dps']:.1f})"
        plt.plot(r["x"], r["y"], color=colors[i % len(colors)], linewidth=2.4, marker="D", markersize=6, label=lbl)
    for r in ctrl_rows:
        lbl = f"[CTRL] {_fmt_build(r)} (WtDPS {r['weighted_dps']:.1f})"
        plt.plot(r["x"], r["y"], color="#111111", linewidth=2.8, marker="o", markersize=7, linestyle="--", label=lbl)
    plt.title("Jinx Fishbones Power Spike: 4-Core DPS Top5 + Control")
    plt.xlabel("Total Gold at Core Timing"); plt.ylabel("DPS (long-range Fishbones AA + W)")
    plt.grid(True, alpha=0.3); plt.legend(loc="best", fontsize=8); plt.tight_layout()
    plt.show()


def run_cli(args=None):
    """기본 receding-horizon 또는 `legacy-ranking` 호환 모드로 징크스 CLI를 실행한다."""
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
