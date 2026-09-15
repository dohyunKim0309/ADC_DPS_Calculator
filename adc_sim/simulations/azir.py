"""Azir 빌드 탐색 — 병사(W) 평타 대체 AP 지속딜 + Q/E/R 자동시전, 룬 2종(PtA·LT).

기본 = receding-horizon 1~5코어 탐색(γ=0.8, 미래 마지널 DPG 할인합; cogmaw/vayne 미러).
`legacy-ranking` = 4코어 전수 랭킹(집합 메모이즈, 컨트롤 nashor-shadowflame-rabadon-void 필수).
시작 = 도란의 반지 + 마법사의 신발 고정(ADC A/B 패키지 미사용). 코어 2 부터 미드 퀘스트 완료
[H-AZIR-4]: 3티어 신발 무료 승급 + AP/추가AD ×1.08.
spec: docs/superpowers/specs/2026-08-27-azir-design.md
실행: .venv/bin/python -m adc_sim.simulations.azir [gamma | legacy-ranking]  (표만, 헤드리스 안전)
"""
from adc_sim.champion import Azir, Target
from adc_sim.runes import LethalTempo, PressTheAttack, CutDown
from adc_sim.engine import run_simulation
from adc_sim.data.items_registry import create_item_from_key
from adc_sim.data.items_data import pen_rule_ok
from adc_sim.settings import CORE_WEIGHTS_LABEL, DEFAULT_DISCOUNT_GAMMA
from adc_sim.simulations.ranking_core import rank_builds

# 코어 단계별 고정 타겟 (Ashe/KaiSa/CogMaw 시뮬과 동일)
CORE_TARGET_STATS = {
    # 마저 +5 일괄 상향(25/30/50/70/90 → 30/35/55/75/95) — 원딜 마저 버프 반영, 사용자 확정 2026-08-31.
    1: {"hp": 1700, "armor": 50, "mr": 30},
    2: {"hp": 1900, "armor": 70, "mr": 35},
    3: {"hp": 2400, "armor": 100, "mr": 55},
    4: {"hp": 2600, "armor": 120, "mr": 75},
    5: {"hp": 3000, "armor": 150, "mr": 95},
}
CORE_AZIR_LEVELS = {1: {"level": 9}, 2: {"level": 11}, 3: {"level": 13},
                    4: {"level": 15}, 5: {"level": 17}}

# 미드 퀘스트 완료 코어 [H-AZIR-4]: 이 코어부터 3티어 신발 + AP/추가AD ×1.08
QUEST_COMPLETE_FROM_CORE = 2
# 2티어 → 3티어(미드 퀘스트 무료 승급) 대응표
TIER3_BOOTS = {"sorcerer": "spellslinger", "ionian": "crimson", "berserker": "gunmetal", "swift": "swiftmarch"}

RUNE_LABELS = {LethalTempo: "LT", PressTheAttack: "PtA"}
RUNE_LONG_LABELS = {LethalTempo: "치명적 속도 (Lethal Tempo)",
                    PressTheAttack: "집중 공격 (Press the Attack)"}

# 시작 패키지(단일): 도란의 반지 + 마법사의 신발. rank_builds 의 packages 인자 규약.
AZIR_PACKAGES = (
    {"key": "M", "label": "Ring+Sorc", "doran": "doranring", "boots": "sorcerer", "rune_as": 0.0},
)

AZIR_RESPAWN_TO_FULL_KILLS = 2


def build_target_for_core(core_tier):
    s = CORE_TARGET_STATS[core_tier]
    return Target(hp=s["hp"], armor=s["armor"], magic_resist=s["mr"],
                  bonus_hp=max(0, s["hp"] - 1600))


def _skill_levels_for_core(core_tier):
    """W>Q>E 선마, R 6/11/16. 코어 1~5(lv 9/11/13/15/17) → (q, w, e, r)
    = (3,5,1,1), (5,5,1,2), (5,5,3,2), (5,5,5,2), (5,5,5,3)."""
    lvl = CORE_AZIR_LEVELS[core_tier]["level"]
    # W 선마: lv1 W, lv2 Q, lv3 W(2)... 단순화: W 는 lv9 에 5. Q 는 lv9 3 → lv11 5. E 는 이후.
    w = 5
    q = 3 if lvl <= 9 else 5
    e = 1 if lvl <= 11 else (3 if lvl <= 13 else 5)
    r = 1 if lvl < 11 else (2 if lvl < 16 else 3)
    return q, w, e, r


def resolve_boots_for_core(boots_key, core_tier):
    """코어별 실제 신발 키: 퀘스트 완료 코어부터 3티어 승급(없으면 그대로)."""
    if core_tier >= QUEST_COMPLETE_FROM_CORE:
        return TIER3_BOOTS.get(boots_key, boots_key)
    return boots_key


def simulate_azir_core_path(full_path, core_tier, doran_key="doranring", boots_key="sorcerer",
                            rune_as_bonus=0.0, keystone_cls=LethalTempo, sub_rune_cls=CutDown,
                            return_sustain=False):
    """Azir DPS + total gold for a core timing. W/Q/E/R 쿨마다(마나 바운드, 시전 락아웃 순차), 벨트 t=0. K=2.

    full_path: 코어 키 리스트(1~5). doran/boots/rune_as: rank_builds 패키지 규약(아지르는 도란링+마관신).
    keystone_cls: LethalTempo|PressTheAttack. sub_rune_cls: 기본 CutDown(None=없음).
    'archangel' 은 구매 코어=대천사, 다음 코어부터 세라핀(마나무네 규약).
    반환: (dps, total_cost) [+ sustain dict].
    """
    target = build_target_for_core(core_tier)
    lvl = CORE_AZIR_LEVELS[core_tier]["level"]
    q, w, e, r = _skill_levels_for_core(core_tier)
    azir = Azir(level=lvl, q_level=q, w_level=w, e_level=e, r_level=r,
                quest_complete=(core_tier >= QUEST_COMPLETE_FROM_CORE))
    azir.set_rune(keystone_cls())
    if sub_rune_cls is not None:
        azir.set_sub_rune(sub_rune_cls())

    items = [create_item_from_key(doran_key)] if doran_key else []
    if boots_key:
        items.append(create_item_from_key(resolve_boots_for_core(boots_key, core_tier)))
    for idx, key in enumerate(full_path[:core_tier], start=1):
        if key == "archangel" and idx < core_tier:
            key = "seraph"
        items.append(create_item_from_key(key))
    total_cost = 0
    for it in items:
        total_cost += it.cost
        azir.add_item(it)
    azir.bonus_as_percent += rune_as_bonus

    # 시전 락아웃 때문에 t=0 동시 시전 불가 → W(0) → E(0.25) → R(0.55) → Q(1.05) 순차 [H-AZIR-3].
    # R 은 auto(쿨 90s+ → 사실상 1회). 벨트 액티브는 수동 t=0(락아웃 뒤 첫 기회에 시전).
    skill_plan = {
        "manual_casts": [(0.0, "belt")],
        "auto_cast": {"q": True, "w": True, "e": True, "r": True},
        "auto_order": ["w", "e", "r", "q"],
    }
    _, dps, _ = run_simulation(azir, target, verbose=False, skill_plan=skill_plan,
                               respawn_to_full_kills=AZIR_RESPAWN_TO_FULL_KILLS)
    if return_sustain:
        return dps, total_cost, dict(azir.sustain_metrics)
    return dps, total_cost


# 컨트롤(베이스라인) = 26.17 메타 빌드(내셔→그불→라바돈→공허). 탐색공간에 반드시 존재해야 함.
CONTROL_PATH = ("nashor", "shadowflame", "rabadon", "void")

# 후보 풀 — 딜 아이템은 전 슬롯, 유틸/방어(존야·밴시·라일라이·벨트·우추)는 3코어부터.
_DMG_EARLY = ["nashor", "liandry", "lichbane", "ludens", "blackfire", "stormsurge", "riftmaker",
              "shadowflame", "archangel", "dawn", "guinsoo", "horizon", "bloodletter", "malignance"]
_DMG_LATE = ["rabadon", "void", "cryptbloom", "wit"]
_UTIL = ["zhonya", "banshee", "rylai", "belt", "cosmic"]
AZIR_CORE_CANDIDATES = {
    1: list(_DMG_EARLY),
    2: list(_DMG_EARLY) + list(_DMG_LATE),
    3: list(_DMG_EARLY) + list(_DMG_LATE) + list(_UTIL),
    4: list(_DMG_EARLY) + list(_DMG_LATE) + list(_UTIL),
}
CORE5_CANDIDATES = sorted(set().union(*AZIR_CORE_CANDIDATES.values()))
CANDIDATES_BY_SLOT = {**AZIR_CORE_CANDIDATES, 5: CORE5_CANDIDATES}

ITEM_SHORT = {
    "nashor": "Nashor", "shadowflame": "SF", "rabadon": "Rabadon", "void": "Void", "cryptbloom": "Crypt",
    "liandry": "Liandry", "lichbane": "Lich", "ludens": "Luden", "blackfire": "Blackfire",
    "stormsurge": "Stormsurge", "riftmaker": "Rift", "archangel": "Seraph", "dawn": "D&D", "guinsoo": "Gui",
    "horizon": "Horizon", "bloodletter": "Bloodlet", "malignance": "Malig", "wit": "Wit's",
    "zhonya": "Zhonya", "banshee": "Banshee", "rylai": "Rylai", "belt": "Belt", "cosmic": "Cosmic",
}

GAMMA = DEFAULT_DISCOUNT_GAMMA
HORIZON = 5


class SimCache:
    """아이템 '집합'을 키로 아지르 DPS·골드를 메모이즈(DPS 는 장착 집합에만 의존)."""

    def __init__(self, keystone_cls, package=None):
        pkg = package or AZIR_PACKAGES[0]
        self.kw = {"doran_key": pkg["doran"], "boots_key": pkg["boots"],
                   "rune_as_bonus": pkg["rune_as"], "keystone_cls": keystone_cls}
        self.cache = {}
        self.hits = 0
        self.misses = 0

    def sim(self, items_tuple):
        """완성 코어 집합의 현재 티어 DPS·총 골드. 대천사는 '집합' 안 위치 무관하게 마지막 코어일 때만 대천사."""
        items_tuple = tuple(items_tuple)
        # 대천사 resolved-key: 집합 키에 '마지막 코어가 대천사인가'를 포함(그 외엔 세라핀).
        last_is_arch = items_tuple and items_tuple[-1] == "archangel"
        key = (tuple(sorted(items_tuple)), bool(last_is_arch))
        if key in self.cache:
            self.hits += 1
            return self.cache[key]
        self.misses += 1
        # simulate 는 path 순서로 대천사/세라핀을 결정하므로, 집합 기준 정렬 시 대천사를 끝/앞에 둔다.
        ordered = [k for k in items_tuple if k != "archangel"]
        if "archangel" in items_tuple:
            ordered = ordered + ["archangel"] if last_is_arch else ["archangel"] + ordered
        result = simulate_azir_core_path(ordered, len(ordered), **self.kw)
        self.cache[key] = result
        return result


def _enumerate_future_combos(fixed, from_slot, horizon=HORIZON):
    """확정 코어 뒤에서 중복·관통 제약을 만족하는 미래 조합을 생성한다."""
    remaining = list(range(from_slot, horizon + 1))

    def rec(index, current):
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
    """미래 코어별 마지널 DPG 할인합."""
    full_path = list(fixed) + list(combo)
    score = 0.0
    for offset, tier in enumerate(range(from_slot, horizon + 1)):
        dps, gold = cache.sim(tuple(full_path[:tier]))
        delta_gold = gold - gold_prev
        marginal_dpg = (dps - dps_prev) / (delta_gold / 1000.0) if delta_gold > 0 else 0.0
        score += (gamma ** offset) * marginal_dpg
        dps_prev, gold_prev = dps, gold
    return score


def solve_greedy(cache, gamma=None, horizon=HORIZON, top_alt=3, initial_fixed=()):
    """매 슬롯에서 미래 할인 마지널 DPG 를 재탐색해 1~5코어 궤적을 반환(cogmaw/vayne 미러)."""
    if gamma is None:
        gamma = GAMMA
    fixed, steps = list(initial_fixed), []
    dps_prev, gold_prev = 0.0, 0.0
    if fixed:
        dps_prev, gold_prev = cache.sim(tuple(fixed))
    for slot in range(len(fixed) + 1, horizon + 1):
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
            "alternatives": [{"item": k, "score": s, "future_path": alternatives_path[k]} for k, s in ranked],
        })
        dps_prev, gold_prev = dps_now, gold_now
    return {"trajectory": fixed, "steps": steps}


def print_receding_scenario(label, out, cache, gamma=None):
    if gamma is None:
        gamma = GAMMA
    print(f"\n{'=' * 22}  Azir · {label}  {'=' * 22}")
    print(f"γ={gamma}, horizon={HORIZON} | 최종 궤적: "
          f"{' → '.join(ITEM_SHORT.get(k, k) for k in out['trajectory'])}")
    print(f"시뮬 캐시: {cache.hits} hits / {cache.misses} misses")
    for step in out["steps"]:
        alternatives = " / ".join(f"{ITEM_SHORT.get(a['item'], a['item'])}:{a['score']:.1f}"
                                  for a in step["alternatives"])
        print(f"  {step['slot']}C → {ITEM_SHORT.get(step['item'], step['item']):<10} | "
              f"DPS {step['dps']:>7.1f} | Gold {step['gold']:>5.0f} | "
              f"MarginalDPG {step['marginal_dpg']:>7.2f} | Score {step['score']:>7.2f} | {alternatives}")


def print_control_reference(cache):
    """컨트롤(메타) 빌드의 코어별 DPS/골드/DPG 를 같은 캐시 척도로 출력."""
    print(f"  [CTRL] {'-'.join(ITEM_SHORT.get(k, k) for k in CONTROL_PATH)}:")
    for tier in range(1, len(CONTROL_PATH) + 1):
        dps, gold = cache.sim(CONTROL_PATH[:tier])
        print(f"    {tier}C DPS {dps:>7.1f} | Gold {gold:>5.0f} | DPG {dps / (gold / 1000.0):>7.2f}")


def main(gamma=None):
    """두 키스톤(PtA·LT)으로 receding-horizon 탐색 + 컨트롤 레퍼런스 출력."""
    if gamma is None:
        gamma = GAMMA
    for keystone_cls in (PressTheAttack, LethalTempo):
        cache = SimCache(keystone_cls)
        out = solve_greedy(cache, gamma=gamma)
        print_receding_scenario(f"{RUNE_LABELS[keystone_cls]}+Ring+Sorc", out, cache, gamma=gamma)
        print_control_reference(cache)


# ── 4코어 전수 랭킹(legacy) + power_compare 연동 ─────────────────────────────
def _build_all_paths():
    """1~4코어 전수 경로(중복·관통 배타 제외)."""
    all_paths, seen = [], set()
    for c1 in AZIR_CORE_CANDIDATES[1]:
        for c2 in AZIR_CORE_CANDIDATES[2]:
            if c2 == c1:
                continue
            for c3 in AZIR_CORE_CANDIDATES[3]:
                if c3 in (c1, c2):
                    continue
                for c4 in AZIR_CORE_CANDIDATES[4]:
                    path = (c1, c2, c3, c4)
                    if len(set(path)) < 4 or not pen_rule_ok(path) or path in seen:
                        continue
                    seen.add(path)
                    all_paths.append(path)
    return all_paths


def _rank_rows(all_paths, keystone_cls=LethalTempo, weights_raw=None):
    """rank_builds 공통 러너 — 집합 메모이즈 simulate 로 전수 랭킹."""
    cache = SimCache(keystone_cls)

    def _sim(path, tier, doran_key=None, boots_key=None, rune_as_bonus=0.0):
        return cache.sim(tuple(path[:tier]))

    return rank_builds(_sim, all_paths, CONTROL_PATH, weights_raw=weights_raw,
                       packages=AZIR_PACKAGES)


_AZIR_TOP1_CACHE = {}


def get_azir_4core_top1_build(keystone_cls=LethalTempo, rank_by="dpg"):
    """4코어 전수 랭킹 top1(+컨트롤 메타). 컨트롤 부재 시 RuntimeError(rank_builds)."""
    if (keystone_cls, rank_by) in _AZIR_TOP1_CACHE:
        return _AZIR_TOP1_CACHE[(keystone_cls, rank_by)]
    all_paths = _build_all_paths()
    rows_dedup, best_control = _rank_rows(all_paths, keystone_cls=keystone_cls)
    sort_key = (lambda r: r["weighted_dps"]) if rank_by == "dps" else (lambda r: r["rel_dpg_score"])
    top1 = max(rows_dedup, key=sort_key)
    result = {
        "path": top1["path"], "doran": top1["doran"], "boots": top1["boots"], "rune_as": top1["rune_as"],
        "pkg_label": top1["pkg_label"], "score": top1["rel_dpg_score"],
        "weighted_dpg": top1["weighted_dpg"], "weighted_dps": top1["weighted_dps"],
        "keystone_cls": keystone_cls,
        "control_path": best_control["path"], "control_doran": best_control["doran"],
        "control_boots": best_control["boots"], "control_rune_as": best_control["rune_as"],
        "control_pkg": best_control["pkg_label"], "control_weighted_dpg": best_control["weighted_dpg"],
        "total_paths_tested": len(all_paths),
    }
    _AZIR_TOP1_CACHE[(keystone_cls, rank_by)] = result
    return result


def build_azir_core_report_meta(full_path, core_tier):
    active_path = tuple(full_path[:core_tier])
    return {
        "champion": "Azir", "core_tier": core_tier,
        "full_path": list(full_path), "active_path": list(active_path),
        "build": "-".join(full_path), "active_build": "-".join(active_path),
    }


def get_azir_powercompare_builds():
    """power_compare 용 (best, meta): best = PtA·LT top1 중 절대 weighted-DPG 우위,
    meta = 컨트롤(nashor-shadowflame-rabadon-void) under PtA(26.17 메타 룬)."""
    pta = get_azir_4core_top1_build(PressTheAttack)
    lt = get_azir_4core_top1_build(LethalTempo)
    src = pta if pta["weighted_dpg"] >= lt["weighted_dpg"] else lt
    best = {"path": src["path"], "keystone_cls": src["keystone_cls"], "doran": src["doran"],
            "boots": src["boots"], "rune_as": src["rune_as"], "pkg_label": src["pkg_label"],
            "rune_label": RUNE_LABELS[src["keystone_cls"]], "weighted_dpg": src["weighted_dpg"]}
    meta = {"path": pta["control_path"], "keystone_cls": PressTheAttack, "doran": pta["control_doran"],
            "boots": pta["control_boots"], "rune_as": pta["control_rune_as"], "pkg_label": pta["control_pkg"],
            "rune_label": "PtA", "weighted_dpg": pta["control_weighted_dpg"]}
    return best, meta


def _run_azir_ranking(keystone_cls, all_paths):
    rows_dedup, best_control = _rank_rows(all_paths, keystone_cls=keystone_cls)
    ranked = sorted(rows_dedup, key=lambda r: r["rel_dpg_score"], reverse=True)
    print(f"\n{'=' * 28}  RUNE: {RUNE_LONG_LABELS[keystone_cls]}  {'=' * 28}")
    print(f"Control: {'-'.join(best_control['path'])} | Weighted DPG {best_control['weighted_dpg']:.2f}")
    col_build, col_core, col_rep = 36, 18, 9
    header = (f"{'RK':>3} | {'BUILD(4C)':<{col_build}} | {'CTRL':>6} | "
              f"{'1C DPS/ΔDPG%':>{col_core}} | {'2C DPS/ΔDPG%':>{col_core}} | "
              f"{'3C DPS/ΔDPG%':>{col_core}} | {'4C DPS/ΔDPG%':>{col_core}} | {'RelDPG':>{col_rep}}")
    print(f"\nTop 30 + Control (RelDPG = control-normalised weighted DPG ×100, {CORE_WEIGHTS_LABEL})")
    print(header); print("-" * len(header))
    top_rows = ranked[:30]
    ctrl_rows = [r for r in ranked if r["is_control"]]
    out_rows = top_rows + [r for r in ctrl_rows if r not in top_rows]
    for rank, r in enumerate(out_rows, start=1):
        y = r["y"]; d = r["core_rel_delta_pct_4"]
        tag = "[CTRL]" if r["is_control"] else ""
        label = "-".join(ITEM_SHORT.get(k, k) for k in r["path"])
        label = label if len(label) <= col_build else label[:col_build - 3] + "..."
        cells = " | ".join(f"{y[i]:.1f}/{d[i]:+.1f}%".rjust(col_core) for i in range(4))
        print(f"{rank:>3} | {label:<{col_build}} | {tag:>6} | {cells} | {r['rel_dpg_score']:>{col_rep}.2f}")
    return ranked, best_control


def main_legacy_ranking():
    print("\n=== Azir Build Path Power Spike (W/Q/E auto, R t=0, 1→4 Core, Ring+Sorc) ===")
    all_paths = _build_all_paths()
    print(f"paths: {len(all_paths)}")
    for keystone_cls in (PressTheAttack, LethalTempo):
        _run_azir_ranking(keystone_cls, all_paths)


def run_cli(args=None):
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
