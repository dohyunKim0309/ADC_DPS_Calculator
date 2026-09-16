from adc_sim.champion import Yunara, Target
from adc_sim.runes import LethalTempo, CutDown
from adc_sim.engine import run_simulation
from adc_sim.data.items_registry import create_item_from_key
from adc_sim.data.recipe_states import half_core_candidates
from adc_sim.simulations import receding
from adc_sim.data.items_data import ADC_PACKAGES, ADC_PACKAGES_VIABLE, pen_rule_ok
from adc_sim.simulations.target_archetypes import (
    DEFAULT_ARCHETYPE, TARGET_ARCHETYPES, bonus_hp, core_target_stats, half_target_stats,
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
# 코어 단계별 고정 타깃 스탯 — 아키타입 모듈에서 파생(사용자 확정 2026-09-16).
#   딜러 / 브루저 / 탱커 3종을 `simulations/target_archetypes.py` 가 들고 있고,
#   여기서는 활성 아키타입 한 벌을 CORE_TARGET_STATS 로 펼쳐 쓴다(기존 소비처 모양 유지).
#   바꾸려면 `set_target_archetype("dealer"|"bruiser"|"tank")` 또는 CLI `target=<이름>`.
#   ⚠️ 타 챔피언 시뮬은 아직 각자 표를 쓴다 — 확장 시 그 모듈을 쓸 것(모듈 독스트링 참조).
ACTIVE_ARCHETYPE = DEFAULT_ARCHETYPE
CORE_TARGET_STATS = core_target_stats(ACTIVE_ARCHETYPE)


def set_target_archetype(name):
    """활성 타깃 아키타입 교체 — CORE_TARGET_STATS 를 제자리 갱신한다.

    완성 코어(build_target_for_core)와 하프 구간(_half_tier_target) 이 같은 표를 읽으므로
    이 함수 하나로 두 경로가 함께 바뀐다.
    """
    global ACTIVE_ARCHETYPE
    stats = core_target_stats(name)      # 미지의 이름이면 여기서 ValueError
    ACTIVE_ARCHETYPE = name
    CORE_TARGET_STATS.clear()
    CORE_TARGET_STATS.update(stats)
    return ACTIVE_ARCHETYPE


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


# 타깃 추가 체력(거인 학살자 증폭 판정) = max(0, 최대체력 − 1600) — 사용자 확정 2026-08-31,
# 전 챔피언 공통 규칙(기존 hp−1500 에서 하향). 이전의 유나라 전용 700 캡(같은 날 오전)은 폐기.
# 코어별: 100 / 300 / 800 / 1000 / 1400 → LDR 증폭 1 / 3 / 8 / 10 / 14 %.

# ── 스탯 파편(작은 룬) — 사용자 확정 2026-08-31 ──────────────────────────────
# 1줄: 공속 10% (공속/공격력5.6(AP9)/스킬가속8 중 택1 — ADC 정배 공속)
# 2줄: 적응형 공격력 +5.4 (공격력/이속2.5%/성장체력 중 택1) — 사용자 정정 2026-08-31(5.6 아님)
# 3줄: 방어(성장체력/고정체력/강인함·둔화저항) — 전부 DPS 0 → 미모델
# [H] 적응형은 유나라 정배가 AD 빌드라 AD 5.4 고정(AP 빌드에선 AP 9 이 정확하나 미세 차이).
YUNARA_SHARD_AS = 0.10
YUNARA_SHARD_AD = 5.4
# 파편 1줄 선택지(사용자 요청 2026-08-31): 공속10%+적응형5.4(기본) vs 적응형×2(AD 10.8, 공속 0)
SHARD_SCENARIOS = {
    "AS10%+AD5.4": {"shard_as": 0.10, "shard_ad": 5.4},
    "AD5.4x2":     {"shard_as": 0.0,  "shard_ad": 10.8},
}


def build_target_for_core(core_tier):
    """코어 티어별 더미 타깃 생성 (유나라 시뮬 전용)."""
    stats = CORE_TARGET_STATS[core_tier]
    return Target(
        hp=stats["hp"],
        armor=stats["armor"],
        magic_resist=stats["mr"],
        bonus_hp=bonus_hp(stats["hp"]),
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


def simulate_yunara_core_path(core_item_keys, core_tier, doran_key=None, boots_key="berserker",
                              rune_as_bonus=0.0, target_count=1, return_sustain=False,
                              shard_as=YUNARA_SHARD_AS, shard_ad=YUNARA_SHARD_AD):
    """Simulate Yunara DPS and total gold for the given core progression.

    doran_key: 시작 도란 아이템(검/활). None이면 미포함.
    boots_key: 신발(기본 광전사). rune_as_bonus: 공속 룬(민첩함 등)의 평타 공속 가산(골드 무료).
    target_count: 교전 중 적 수. 1이면 순수 단일 대상. 2+면 (Q 활성 시) 크라켄 추가발동·루난 확산
        업리프트가 1차 대상 기록값에 합산된다(=다대상 유효 DPS). 1차 대상 딜은 줄지 않는다.
    return_sustain=True 면 3번째 값으로 피흡 집계(engine.sustain_metrics)를 반환한다.
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
            # 윤탈 치명타 누적 (사용자 확정 2026-08-02): 구매한 그 코어 시점=0%(스택 미가공),
            # 다음 코어부터는 25%. Vayne 시뮬(d4351e6, 실 인게임 확인)과 일관.
            if current_tier == purchase_tier:
                yuntal_crit = 0.00
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
    yunara.bonus_as_percent += shard_as   # 스탯 파편 1줄 (기본 공속 10%; SHARD_SCENARIOS 로 교체 가능)
    yunara.bonus_ad += shard_ad           # 스탯 파편 2줄 적응형 (기본 5.4; 1줄도 적응형이면 10.8)

    # 로테이션(평타→궁→평타→W쿨마다)은 Yunara 모델 내부에서 처리.
    _, dps, _ = run_simulation(yunara, target, verbose=False, respawn_to_full_kills=2)
    if return_sustain:
        # 피흡 집계(engine 이 채운 이벤트 누적치). 카이사·베인 시뮬과 같은 규약.
        return dps, total_cost, dict(yunara.sustain_metrics)
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


# ── 적 수 혼합 랭킹 ──────────────────────────────────────────────────────────
# 템트리 선택 지표를 단일 tc 가 아니라 교전 시나리오 혼합으로: DPS_mix = Σ w·DPS_tc.
# **기본 = 적1 : 적2 : 적3 = 1 : 1 : 1** (사용자 변경 2026-09-16).
#   한 판에서 라인전(적1)·소규모 교전(적2)·한타(적3)를 모두 겪는다는 해석이라, 적3을
#   빼던 이전 규약(적1 0.5 : 적2 0.5, 2026-08-31)보다 통합 지표로 맞다는 판단.
#   ⚠️ 이 가중이 3코어 결론을 직접 지배한다 — 적3이 들어오면서 3코어 추천이
#   도미닉에서 루난으로 바뀌었다(적1 단독일 때만 도미닉).
TARGET_MIX_WEIGHTS = ((1, 1.0 / 3.0), (2, 1.0 / 3.0), (3, 1.0 / 3.0))


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


GAMMA = DEFAULT_DISCOUNT_GAMMA
HORIZON = 5
# receding-horizon 기본 모드가 훑는 교전 적 수 시나리오.
# 1=순수 단일 대상, 2=루난 서브타겟 1명, 3=루난 서브타겟 캡(2명) 완전 활용.
TARGET_COUNT_SCENARIOS = (1, 2, 3)
# ── 코어 후보 풀 (사용자 확정 2026-09-15) ────────────────────────────────────
# 1~5코어 전부 같은 합집합 풀을 쓰고, 예외는 아래 둘뿐이다. 슬롯마다 손으로 적던
# 옛 리스트(몰락 1~2코어 한정, 3코어에서 공속템 전면 제외 등)는 근거가 없어 폐기했다.
#   · 윤탈: 스택 아이템이라 1~2코어에서만 (SLOT_RESTRICTED 관례 유지)
#   · 1코어 제외 5종: 치확·공속 기반이 없는 시점에 첫 아이템으로 의미가 없다
# pen 배타(방관 ≤1 / 마관 ≤1)는 pen_rule_ok 로 별도 적용된다.
CORE_POOL = [
    "kraken", "yuntal25", "storm", "c44", "bot", "guinsoo", "terminus", "nashor",
    "statikk", "pd", "runaan", "shadowflame", "ie", "ldr", "rabadon", "mortal", "void",
]
YUNTAL_MAX_SLOT = 2
# 윤탈 구매 가능 최소 슬롯. 기본 1. 라인전이 힘들어 1코어 윤탈이 불가능한 판을 보려면
# 2 로 올린다(`late-yuntal` CLI 인자 / set_yuntal_min_slot). 윤탈은 스택 아이템이라
# 구매 코어의 치명타가 약하게 평가되므로, 늦게 살수록 그 손해를 늦게 치른다.
YUNTAL_MIN_SLOT = 1
CORE1_EXCLUDED = frozenset({"rabadon", "shadowflame", "void", "ldr", "mortal"})


def _slot_candidates(slot):
    """슬롯 제약만 적용한 후보 목록 (pen 배타는 탐색 쪽에서 별도 검사)."""
    keys = [k for k in CORE_POOL
            if not (k == "yuntal25" and not YUNTAL_MIN_SLOT <= slot <= YUNTAL_MAX_SLOT)]
    if slot == 1:
        keys = [k for k in keys if k not in CORE1_EXCLUDED]
    return keys


CANDIDATES_BY_SLOT = {slot: _slot_candidates(slot) for slot in range(1, HORIZON + 1)}


def set_yuntal_min_slot(slot):
    """윤탈 최소 구매 슬롯을 바꾸고 후보 맵을 다시 만든다(시나리오 전환용)."""
    global YUNTAL_MIN_SLOT
    YUNTAL_MIN_SLOT = slot
    CANDIDATES_BY_SLOT.update({s: _slot_candidates(s) for s in range(1, HORIZON + 1)})


class SimCache:
    """아이템 집합과 윤탈 구매 시점을 키로 유나라 DPS·골드를 메모이즈한다."""

    def __init__(self, package, target_count, shards=None):
        """시작 패키지·교전 적 수·파편 구성(shards={"shard_as","shard_ad"})을 고정한 캐시."""
        self.kw = {
            "doran_key": package["doran"],
            "boots_key": package["boots"],
            "rune_as_bonus": package["rune_as"],
            "target_count": target_count,
        }
        if shards:
            self.kw.update(shards)
        self.cache = {}
        self.hits = 0
        self.misses = 0

    def _key(self, items_tuple):
        """순서 무관 집합과 윤탈이 현재 구매 슬롯인지 여부를 캐시 키로 반환한다."""
        sorted_items = tuple(sorted(items_tuple))
        yuntal_last = bool(items_tuple) and "yuntal25" in sorted_items and items_tuple[-1] == "yuntal25"
        return sorted_items, yuntal_last

    def sim_half(self, done_tuple, next_key, comp_names):
        """하프 티어(next_key 의 하위템 comp_names 보유) DPS·총 골드."""
        return simulate_yunara_half_tier(list(done_tuple), next_key, comp_names, **self.kw)

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


class MixedSimCache:
    """적 수 시나리오 혼합 캐시 — sim() 이 TARGET_MIX_WEIGHTS 가중으로 tc별 DPS 를 합산.

    혼합 랭킹(rank_yunara_4core_paths_mixed)과 같은 지표를 receding-horizon 에서 쓰는 래퍼
    (사용자 확정 2026-09-16: 혼합 1:1:1 이 유나라 기본 선택 지표). 골드는 tc 무관 동일.
    """

    def __init__(self, package, mix=None, shards=None, caches=None):
        """caches 를 주면 그 SimCache 를 재사용한다 — MIX 가 TC 런의 시뮬을 공유해 공짜가 된다."""
        self.mix = tuple(mix or TARGET_MIX_WEIGHTS)
        self.caches = {tc: (caches or {}).get(tc) or SimCache(package, tc, shards=shards)
                       for tc, _ in self.mix}
        self.hits = 0
        self.misses = 0

    def sim_half(self, done_tuple, next_key, comp_names):
        """혼합 지표 하프 티어 — tc별 DPS 를 가중 합산(골드는 tc 무관 동일)."""
        dps, gold = 0.0, 0
        for tc, weight in self.mix:
            d, g = self.caches[tc].sim_half(done_tuple, next_key, comp_names)
            dps += weight * d
            gold = g
        return dps, gold

    def sim(self, items_tuple):
        dps, gold = 0.0, 0
        for tc, w in self.mix:
            d, g = self.caches[tc].sim(items_tuple)
            dps += w * d
            gold = g
        self.hits = sum(c.hits for c in self.caches.values())
        self.misses = sum(c.misses for c in self.caches.values())
        return dps, gold


# ── 하프 티어(코어 사이 하위템 구간) — 사용자 확정 2026-08-31 ─────────────────
# 각 코어 k 완성 전, 다음 코어의 조합식 하위템(합계 ≤1600G 중 시뮬 최적 부분집합)을 든
# 중간 지점을 시뮬해 receding-horizon 마지널 DPG 체인에 포함한다.
# 레벨 = 짝수 보간(코어 k 직전 = 8/10/12/14/16), 타깃 = 인접 코어 스탯 선형 보간.
# [H-HALF-1] 하프 시점 스킬레벨은 다음 코어 표를 사용(레벨 조건으로 R 랭크만 가드).
# [H-HALF-2] 윤탈이 이미 완성된 상태의 하프 시점 치명타는 25%(스택이 얼추 찼다고 가정).
# [H-HALF-DISCOUNT] 하프+풀 스텝은 γ^(s/2) (s=0,1,2,…) 로 할인 — 풀 코어 간 비율은 기존 γ 유지.
#
# 창 규칙 (사용자 확정 2026-09-15): 옛 전역 캡 1600 을 버리고 **아이템별** 예산창
# [ceil100(가격/2), +100] 안에서 고른다. 창이 비면 하단만 100 씩 완화하고 상단은
# 절대 넘지 않는다. 후보 열거·창 계산은 adc_sim/data/recipe_states.py 가 단일 출처.
# 선택 기준도 절대 DPS 가 아니라 **점수에 실제로 들어가는 스텝 마지널 DPG** 다.
HALF_TIER_LEVELS = {1: 8, 2: 10, 3: 12, 4: 14, 5: 16}
# 5코어 하프는 기본 생략 (사용자 확정 2026-09-15): 5코어 구매 시점엔 아이템 칸이 모자라
# 계획대로 사기 어렵고, 전체 시뮬 비용의 57% 를 먹으면서 가중은 γ^9 ≈ 0.36 에 불과하다.
HALF_INCLUDE_LAST_SLOT = False


def _half_tier_target(k):
    """코어 k 직전 하프 티어 타깃: 인접 코어 스탯 선형 보간(0.5코어는 코어1 그대로)."""
    st = half_target_stats(k, ACTIVE_ARCHETYPE)
    return Target(hp=st["hp"], armor=st["armor"], magic_resist=st["mr"],
                  bonus_hp=bonus_hp(st["hp"]))


def _half_component_options(next_key):
    """다음 코어의 하프 후보 구성들 — recipe_states 의 창 규칙 결과(재료 이름 튜플들)."""
    return tuple(names for _cost, names in half_core_candidates(next_key))


def build_spec(gamma=None, horizon=None, include_last_half=None):
    """현재 모듈 설정을 담은 공통 엔진용 RecedingSpec (탐색 로직은 receding.py)."""
    return receding.RecedingSpec(
        title="Yunara · 하프 티어 포함",
        candidates_by_slot=CANDIDATES_BY_SLOT,
        pen_rule_ok=pen_rule_ok,
        half_options=_half_component_options,
        gamma=GAMMA if gamma is None else gamma,
        item_short=ITEM_SHORT,
        horizon=HORIZON if horizon is None else horizon,
        include_last_half=(HALF_INCLUDE_LAST_SLOT if include_last_half is None
                           else include_last_half),
    )


def simulate_yunara_half_tier(done_keys, next_key, comp_names, doran_key=None,
                              boots_key="berserker", rune_as_bonus=0.0, target_count=1,
                              shard_as=YUNARA_SHARD_AS, shard_ad=YUNARA_SHARD_AD):
    """코어 done_keys 완성 + next_key 의 하위템 comp_names 를 든 하프 티어 DPS·총 골드."""
    from adc_sim.data.items_registry import create_catalog_item
    k = min(5, len(done_keys) + 1)
    level = HALF_TIER_LEVELS[k]
    cfg = CORE_YUNARA_LEVELS[k]
    r_guard = 1 if level < 11 else (2 if level < 16 else 3)
    yunara = Yunara(level=level, q_level=cfg["q_level"], w_level=cfg["w_level"],
                    r_level=min(cfg["r_level"], r_guard))
    yunara.set_rune(LethalTempo())
    yunara.set_sub_rune(CutDown())
    yunara.set_target_count(target_count)

    items = [create_item_from_key(doran_key)] if doran_key else []
    items.append(create_item_from_key(boots_key))
    for key in done_keys:
        if key == "yuntal25":
            items.append(create_item_from_key(key, yuntal_crit=0.25))   # [H-HALF-2]
        else:
            items.append(create_item_from_key(key))
    for name in comp_names:
        items.append(create_catalog_item(name, allow_unsupported=True))

    total_cost = 0
    for item in items:
        total_cost += item.cost
        yunara.add_item(item)
    yunara.bonus_as_percent += rune_as_bonus + shard_as
    yunara.bonus_ad += shard_ad

    target = _half_tier_target(k)
    _, dps, _ = run_simulation(yunara, target, verbose=False, respawn_to_full_kills=2)
    return dps, total_cost


def main(gamma=None, include_last_half=None):
    """기본 모드 — 하프 티어 포함 receding-horizon 전체 스윕.

    축 (사용자 확정 2026-09-15):
      신발·전설룬 패키지 4 (ADC_PACKAGES_VIABLE — 피흡 소스 ≥1, 광전사+민첩함 금지)
      × 룬 파편 2 (SHARD_SCENARIOS)
      × 교전 적 수 4 (TC1 / TC2 / TC3 / MIX 1:1:1)
    MIX 는 TC1~TC3 캐시를 그대로 재사용하므로 추가 시뮬 비용이 없다.
    """
    if gamma is None:
        gamma = GAMMA
    if include_last_half is not None:
        global HALF_INCLUDE_LAST_SLOT
        HALF_INCLUDE_LAST_SLOT = bool(include_last_half)
    spec = build_spec(gamma=gamma)
    for shard_label, shards in SHARD_SCENARIOS.items():
        for package in ADC_PACKAGES_VIABLE:
            caches = {tc: SimCache(package, tc, shards=shards) for tc in TARGET_COUNT_SCENARIOS}
            for tc in TARGET_COUNT_SCENARIOS:
                out = receding.solve(spec, caches[tc])
                receding.print_scenario(
                    spec, f"{package['label']} · TC{tc} · 파편 {shard_label}", out)
            mixed = MixedSimCache(package, shards=shards, caches=caches)
            out = receding.solve(spec, mixed)
            receding.print_scenario(
                spec, f"{package['label']} · MIX 1:1:1 · 파편 {shard_label}", out)


def run_cli(args=None):
    """유나라 CLI — 인자 없으면 기본 스윕. `half5`=5코어 하프 포함,
    `late-yuntal`=1코어 윤탈 금지(라인전 난항 케이스),
    `target=dealer|bruiser|tank`=상대 타깃 아키타입(기본 브루저), 숫자=γ 지정. 조합 가능."""
    import sys

    cli_args = list(sys.argv[1:] if args is None else args)
    include_last_half = False
    while cli_args and (cli_args[0] in ("half5", "late-yuntal")
                        or cli_args[0].startswith("target=")):
        if cli_args[0] == "half5":
            include_last_half = True
        elif cli_args[0].startswith("target="):
            name = cli_args[0].split("=", 1)[1]
            set_target_archetype(name)
            print(f"[scenario] 타깃 아키타입 = {TARGET_ARCHETYPES[name]['label']}({name})")
        else:
            set_yuntal_min_slot(2)
            print("[scenario] 1코어 윤탈 금지 — 윤탈은 2코어에서만 구매 가능")
        cli_args = cli_args[1:]
    gamma = GAMMA
    if cli_args:
        try:
            gamma = float(cli_args[0])
            if not 0.0 < gamma <= 1.0:
                raise ValueError
        except ValueError:
            print(f"[warn] gamma 인자 파싱 실패({cli_args[0]!r}) — 기본 {GAMMA} 사용")
            gamma = GAMMA
    main(gamma=gamma, include_last_half=include_last_half)


if __name__ == "__main__":
    run_cli()
