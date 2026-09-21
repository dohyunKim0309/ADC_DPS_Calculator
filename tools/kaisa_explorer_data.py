# -*- coding: utf-8 -*-
"""카이사 타이밍별 결정 탐색기 데이터 — `docs/reports/kaisa_explorer.json`.

실행: `python -m tools.kaisa_explorer_data [출력경로]`  (repo 루트에서, 수 분)

`tools/yunara_explorer_data.py` 의 미러다. 카이사에도 하프 코어 receding-horizon
(`solve_greedy_half_kaisa` / `_score_combo_half` / `kaisa_sim_half`)이 이미 있어서
점수식은 그대로 쓰고, 순열 전수 대신 **집합 단위 DP** 로 같은 값을 구한다:

    V(노드) = max_x [ half(노드,x) + √γ·full(노드,x) + γ·V(노드+x) ]
    후보 x 의 score = half + √γ·full + γ·V(노드+x)

유나라와 다른 점(카이사 고유):
· **하프 구간을 5코어에서도 잰다** — 카이사 `_score_combo_half` 규약 그대로(유나라는 생략).
· **적 수 축이 없다** — 카이사 시뮬은 단일 대상이라 시나리오는 `solo` 하나뿐이다.
· 슬롯별 후보 목록이 유나라보다 좁고(`CANDIDATES_BY_SLOT`), **2코어 스탯 하한**
  (AD 75·공속 65%) 필터가 추가로 걸린다. 윤탈 키는 `yuntal`(유나라는 `yuntal25`).
· γ 는 프로젝트 기본값(0.8) — 유나라만 0.7 예외다(`settings.RANKING_GAMMA_OVERRIDES`).

순위·전개 기준은 유나라와 같다: **1차 mDPG, 차이 0.5% 안쪽이면 동률로 보고 score 로**
세우며, 그 순서의 상위 3개만 자식 노드로 전개한다(나머지는 tier="minor").

`--verify` 로 원본 `solve_greedy_half_kaisa` 와 1코어 후보 점수가 맞는지 확인한다.
"""
import json
import sys
from math import sqrt

from adc_sim.simulations import kaisa as K
from adc_sim.simulations.kaisa import (
    CANDIDATES_BY_SLOT, GAMMA, HORIZON, KAISA_SHARD_SCENARIOS, SimCache,
    _kaisa_two_core_stats_ok, kaisa_sim_half, solve_greedy_half_kaisa,
)
from adc_sim.data.items_data import ADC_PACKAGES, pen_rule_ok
from adc_sim.simulations.target_archetypes import TARGET_ARCHETYPES

# 정배 패키지 A(도란검 + 광전사 + 핏빛길) · 파편 공속10%+AD5.4 · 치명적속도 + 체력차극복.
PKG = [p for p in ADC_PACKAGES if p["key"] == "A"][0]   # Bld+Zerk = 도란검+광전사+핏빛길
SHARD = KAISA_SHARD_SCENARIOS["AS10%+AD5.4"]
MAIN_TOP_N = 3            # 자식 노드로 전개할 상위 후보 수 (나머지는 minor)
MDPG_TIE_PCT = 0.5        # mDPG 차가 이 % 안쪽이면 동률 — 그 묶음만 score 로 세운다

ITEM_KO = {
    "kraken": "크라켄", "yuntal": "윤탈", "statikk": "스태틱", "guinsoo": "구인수",
    "terminus": "경계", "pd": "유령무희", "bot": "몰왕검", "nashor": "내셔",
    "ie": "무한", "c44": "C44", "ldr": "도미닉", "mortal": "징수의총",
    "storm": "폭풍갈퀴", "rabadon": "라바돈", "shadowflame": "그림자불꽃",
    "shieldbow": "방패검",
}


def _order_rows(rows):
    """1차 mDPG, 동률(0.5% 이내)일 때만 score — 리포트 표시 순서와 같은 규칙."""
    if not rows:
        return rows
    best = max(r["mdpg"] for r in rows)
    if best <= 0:
        return sorted(rows, key=lambda r: -r["score"])
    cut = best * (1.0 - MDPG_TIE_PCT / 100.0)
    tied = sorted((r for r in rows if r["mdpg"] >= cut), key=lambda r: -r["score"])
    rest = sorted((r for r in rows if r["mdpg"] < cut), key=lambda r: -r["mdpg"])
    return tied + rest


def _legal_next(prefix, depth):
    """다음 슬롯(depth+1) 후보 — 슬롯 제약 + 관통 배타 + 카이사 2코어 스탯 하한.

    **막다른 길은 뺀다**: 5코어 전인데 그걸 사면 다음 칸에 살 게 하나도 없는 아이템
    (예: 1코어 내셔·C44 — 2코어 스탯 하한 AD 75 를 둘이 합쳐 못 넘긴다)은 애초에
    완주 불가능한 빌드다. 원본 `_enumerate_future_combos` 도 그런 경로를 아예 만들지
    않으므로, 여기서 빼야 원본과 같은 후보 집합이 된다. (안 빼면 그 가지의 score 가
    미래 항 없이 잘려 나와 순위가 왜곡되고, 탐색기에서 눌러도 다음 칸이 비어 있다.)
    """
    slot = depth + 1
    if slot > HORIZON:        # 5코어 도달 — 더 살 칸이 없다
        return []
    out = []
    for key in CANDIDATES_BY_SLOT[slot]:
        if key in prefix:
            continue
        path = tuple(prefix) + (key,)
        if not pen_rule_ok(path):
            continue
        if not _kaisa_two_core_stats_ok(path):
            continue
        if slot < HORIZON and not _next_exists(path, slot):
            continue
        out.append(key)
    return out


def _next_exists(path, slot):
    """path 를 산 뒤 slot+1 에 살 수 있는 아이템이 하나라도 있는지(한 칸만 본다)."""
    for key in CANDIDATES_BY_SLOT[slot + 1]:
        if key in path:
            continue
        nxt = tuple(path) + (key,)
        if pen_rule_ok(nxt) and _kaisa_two_core_stats_ok(nxt):
            return True
    return False


def _marginal(cache, prefix, item):
    """(하프 항, 완성 항, 완성 dps/gold, 하프 dps/gold) — 직전 상태 대비 마지널 DPG."""
    d_prev, g_prev = cache.sim(tuple(prefix)) if prefix else (0.0, 0.0)
    half_dps, half_gold, _comps = kaisa_sim_half(cache, tuple(prefix), item)
    h_term = 0.0
    d_gold = half_gold - g_prev
    if d_gold > 0:
        h_term = (half_dps - d_prev) / (d_gold / 1000.0)
    d_prev, g_prev = max(d_prev, half_dps), max(g_prev, half_gold)

    full_dps, full_gold = cache.sim(tuple(prefix) + (item,))
    d_gold = full_gold - g_prev
    f_term = (full_dps - d_prev) / (d_gold / 1000.0) if d_gold > 0 else 0.0
    return h_term, f_term, full_dps, full_gold, half_dps, half_gold


class Explorer:
    """노드별 후보 점수를 만드는 집합 단위 DP (유나라 Explorer 미러)."""

    def __init__(self, cache, gamma=GAMMA):
        self.cache = cache
        self.gamma = gamma
        self.root_gamma = sqrt(gamma)
        self._v = {}
        self._cand = {}

    def _key(self, prefix):
        # DPS 는 장착 집합에만 의존하되, 윤탈은 "방금 산 코어"인지에 따라 치확이 갈린다.
        return tuple(sorted(prefix)), bool(prefix) and prefix[-1] == "yuntal"

    def candidates(self, prefix):
        key = self._key(prefix)
        if key in self._cand:
            return self._cand[key]
        prev_dps, prev_gold = self.cache.sim(tuple(prefix)) if prefix else (0.0, 0.0)
        rows = []
        for item in _legal_next(prefix, len(prefix)):
            h, f, dps, gold, h_dps, h_gold = _marginal(self.cache, prefix, item)
            score = h + self.root_gamma * f + self.gamma * self.value(tuple(prefix) + (item,))
            cost = gold - prev_gold
            ddps = dps - prev_dps
            rows.append({
                "item": item, "score": score, "gold": gold, "dps": dps,
                "dpg": dps / (gold / 1000.0) if gold else 0.0,
                "cost": cost, "ddps": ddps,
                "mdpg": (ddps / (cost / 1000.0)) if cost > 0 else 0.0,
                "half_dps": h_dps, "half_gold": h_gold,
                "half_dpg": (h_dps / (h_gold / 1000.0)) if h_dps and h_gold else None,
            })
        rows = _order_rows(rows)
        self._cand[key] = rows
        return rows

    def value(self, prefix):
        """V(노드) — 이 프리픽스에서 5코어까지 최적으로 이어갈 때의 할인 마지널 DPG 합."""
        if len(prefix) >= HORIZON:
            return 0.0
        key = self._key(prefix)
        if key in self._v:
            return self._v[key]
        self._v[key] = 0.0          # 재귀 진입 가드
        best = 0.0
        for item in _legal_next(prefix, len(prefix)):
            h, f, _dps, _gold, _hd, _hg = _marginal(self.cache, prefix, item)
            val = h + self.root_gamma * f + self.gamma * self.value(tuple(prefix) + (item,))
            best = max(best, val)
        self._v[key] = best
        return best

    def walk(self, prefix=(), out=None):
        """상위 MAIN_TOP_N 만 자식으로 전개하며 노드 표를 채운다."""
        out = {} if out is None else out
        node_id = "-".join(prefix)
        if node_id in out:
            return out
        rows = self.candidates(prefix)
        if not rows:
            return out          # 5코어 도달 — 노드를 만들지 않는다
        best_m = max(r["mdpg"] for r in rows) or 0.0
        best_s = max(r["score"] for r in rows) or 0.0
        out[node_id] = {
            r["item"]: {
                "score": round(r["score"], 2),
                "gold": r["gold"],
                "dps": round(r["dps"], 1),
                "dpg": round(r["dpg"], 1),
                "cost": r["cost"],
                "ddps": round(r["ddps"], 1),
                "mdpg": round(r["mdpg"], 1),
                "half_dps": round(r["half_dps"], 1) if r["half_dps"] else None,
                "half_gold": int(r["half_gold"]) if r["half_gold"] else None,
                "half_dpg": round(r["half_dpg"], 1) if r["half_dpg"] else None,
                "rel": round(100.0 * (r["mdpg"] / best_m - 1.0), 1) if best_m else 0.0,
                "rel_score": round(100.0 * (r["score"] / best_s - 1.0), 1) if best_s else 0.0,
                "tier": "main" if i < MAIN_TOP_N else "minor",
            }
            for i, r in enumerate(rows)
        }
        for r in rows[:MAIN_TOP_N]:
            self.walk(tuple(prefix) + (r["item"],), out)
        return out


def _cache():
    return SimCache(
        doran_key=PKG["doran"], boots_key=PKG["boots"], rune_as_bonus=PKG["rune_as"],
        bloodline_lifesteal=PKG["bloodline_lifesteal"], shard_as=SHARD["shard_as"],
        shard_ad=SHARD["shard_ad"],
    )


def verify():
    """원본 greedy(순열 전수)와 1코어 후보 score 가 같은지 확인한다."""
    K.set_target_archetype("bruiser")
    cache = _cache()
    ref = solve_greedy_half_kaisa(cache, gamma=GAMMA)
    ref_alts = {a["item"]: a["score"] for a in ref["steps"][0]["alternatives"]}
    mine = {r["item"]: r["score"] for r in Explorer(cache).candidates(())}
    ok = True
    print("[verify] 1코어 후보 score — greedy vs DP")
    for item, score in sorted(ref_alts.items(), key=lambda kv: -kv[1]):
        delta = mine[item] - score
        if abs(delta) > 1e-6:
            ok = False
        flag = "OK " if abs(delta) <= 1e-6 else "DIFF"
        print(f"   {flag} {item:<10} greedy {score:9.3f}  dp {mine[item]:9.3f}  Δ{delta:+.6f}")
    print("[verify]", "일치" if ok else "불일치")
    return ok


def build():
    out = {
        "champion": "kaisa",
        "meta": {
            "gamma": GAMMA, "horizon": HORIZON, "main_top_n": MAIN_TOP_N,
            "package": "도란검 + 광전사 + 핏빛길",
            "shard": "공속10% + 적응형AD 5.4",
            "rune": "치명적 속도 + 체력차 극복",
            "order": f"1차 mDPG, 차이 {MDPG_TIE_PCT}% 안쪽이면 동률로 보고 score 로 세운다.",
            "mdpg_tie_pct": MDPG_TIE_PCT,
            "score": "γ-할인 마지널 DPG 합(하프 √γ, 코어 γ). 카이사는 5코어 하프도 센다.",
            "mdpg": "이 한 칸의 마지널 DPG — (늘어난 DPS) / (이 칸에 쓴 골드/1000).",
            "note": "단일 대상 시뮬이라 교전 적 수 축이 없다.",
        },
        "items": ITEM_KO,
        "archetypes": [{"id": k, "label": v["label"], "desc": v["desc"],
                        "tiers": {str(t): list(s) for t, s in v["tiers"].items()}}
                       for k, v in TARGET_ARCHETYPES.items()],
        "scenarios": ["solo"],
        "nodes": {},
    }
    for arch in TARGET_ARCHETYPES:
        K.set_target_archetype(arch)
        explorer = Explorer(_cache())
        out["nodes"][f"{arch}|solo"] = explorer.walk()
        print(f"  done {arch}: 노드 {len(out['nodes'][f'{arch}|solo'])}")
    K.set_target_archetype("bruiser")
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--verify" in args:
        raise SystemExit(0 if verify() else 1)
    dest = args[0] if args else "docs/reports/kaisa_explorer.json"
    data = build()
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    total = sum(len(v) for v in data["nodes"].values())
    print(f"saved -> {dest}  (상황 {len(data['nodes'])} · 노드 {total})")
