# -*- coding: utf-8 -*-
"""유나라 타이밍별 결정 탐색기 데이터 — `docs/reports/yunara_explorer.json`.

실행: `python -m tools.yunara_explorer_data [출력경로]`  (repo 루트에서)

리포트의 탐색기는 "지금까지 산 코어(프리픽스)" 마다 **다음 코어 후보 전부**의 점수를
보여준다. 그래서 완성 트리 몇 개가 아니라 **노드별 후보 표**를 통째로 내보낸다.

── score 정의 (yunara._score_combo_half 와 동일) ──────────────────────────────
노드에서 미래를 하프·완성 번갈아 밟으며 **직전 상태 대비 마지널 DPG** 를 γ-할인해 더한다:

    score = Σ γ^(step/2) · (DPS_step − DPS_prev) / ((Gold_step − Gold_prev)/1000)

하프 한 칸이 √γ, 코어 하나가 γ(=0.8). 5코어 하프는 생략하되 step 은 그대로 증가시켜
뒤 항의 할인 지수를 흔들지 않는다(원본과 같은 규약).

원본 `solve_greedy_half` 는 미래를 **순열로 전수 열거**해 최대값을 찾는다. 여기서는 같은
값을 주는 **집합 단위 DP** 로 바꾼다 — 마지널 항이 장착 집합(+윤탈 구매시점)에만 의존하므로
순열까지 볼 필요가 없다:

    V(노드) = max_x [ half(노드,x) + √γ·full(노드,x) + γ·V(노드+x) ]
    후보 x 의 score = half + √γ·full + γ·V(노드+x)

`--verify` 로 원본 greedy 와 1코어 후보 점수·순위가 일치하는지 확인할 수 있다.

── 순위·전개 기준 (사용자 확정 2026-09-21) ──────────────────────────────────
**1차 = mDPG(이 한 칸의 골드 효율), 동률일 때만 score(미래 할인합)** — 한국 서버 챌린저
원딜 피드백. mDPG 차가 MDPG_TIE_PCT(0.5%) 안쪽이면 동률로 보고 그 묶음만 score 로 세운다.
score 는 여전히 같은 공식으로 계산·표기하되 정렬의 2차 키로 내려간다.

── 노드 전개 (사용자 확정 2026-09-16) ────────────────────────────────────────
· 각 노드에서 **위 순서 기준 상위 3개만 자식 노드로 전개**(tier="main"), 나머지는
  tier="minor" 로 점수만 싣는다. 탐색기는 minor 를 후보 열 아래 표로 보여주고 더
  파고들지 않는다.
· 그래서 노드 수가 1+3+9+27+81 = 121 개(상황 하나당)로 묶인다. 전개 안 된 가지는
  리포트에서 "미검증" 으로 표기된다.
"""
import json
import sys
from math import sqrt

from adc_sim.simulations import yunara as Y
from adc_sim.simulations.yunara import (
    CANDIDATES_BY_SLOT, GAMMA, HORIZON, MixedSimCache, SHARD_SCENARIOS, SimCache,
    _half_enabled_for_slot, sim_half, solve_greedy_half,
)
from adc_sim.data.items_data import ADC_PACKAGES_VIABLE, pen_rule_ok
from adc_sim.simulations.target_archetypes import TARGET_ARCHETYPES

PKG = [p for p in ADC_PACKAGES_VIABLE if p["label"] == "Bow+Glut"][0]   # 도란활+탐욕+민첩함
SHARD = SHARD_SCENARIOS["AS10%+AD5.4"]
MAIN_TOP_N = 3            # 자식 노드로 전개할 상위 후보 수 (나머지는 minor)
MDPG_TIE_PCT = 0.5        # mDPG 차가 이 % 안쪽이면 동률 — 그 묶음만 score 로 세운다


# 리포트(공용 템플릿)가 그대로 쓰는 챔피언별 문구 — 템플릿에는 챔피언 이름이 없다.
COPY = {
    "champion": "유나라",
    "title": "유나라 코어 결정 탐색기",
    "lede": "지금까지 산 코어에서 다음 한 칸으로 뭘 올릴지, 상대 타깃과 교전 적 수에 따라 후보 전부의 점수를 비교한다.",
    "scenario_label": "교전 적 수",
    "scenarios": {
        "tc1": {"label": "적 1명", "note": "순수 단일 대상. 솔로킬·사이드 구도."},
        "tc2": {"label": "적 2명", "note": "둘이 붙은 교전. 크라켄 처형 가속과 루난 확산이 살아난다."},
        "tc3": {"label": "적 3명", "note": "루난 서브타겟 캡(2명)이 꽉 차는 한타 전제."},
        "mix": {"label": "혼합 1:1:1", "note": "적 1·2·3명을 같은 비중으로 섞은 통합 지표."},
    },
    "target_note": "여기 적힌 레벨·스탯은 상대 기준이다. 유나라 자신의 레벨은 아래 \"측정 방식\" 에 있다.",
    "method": [
        "유나라 레벨은 하프 8/10/12/14/16 · 완성 9/11/13/15/17. DPS 는 같은 체력바를 2회 처치하는 지속딜(K=2). "
        "시작은 도란활 + 탐욕의 군화 + 민첩함, 룬은 치명적 속도 + 체력차 극복, 파편은 공속 10% + 적응형 AD 5.4.",
        "후보 풀은 17종이며 관통 배타(방관·마관 각 1개)를 지킨다. 윤탈은 1~2코어에서만 살 수 있고, "
        "1코어에는 라바돈·그림자불꽃·공허·도미닉·징수의총이 빠져 12종만 뜬다.",
    ],
    "half_note": "<b>5코어 직전 하프는 재지 않는다</b>(아이템 칸이 모자라 계획대로 사기 어렵고 가중도 가장 낮다).",
    "caveats": [
        "적 2·3 값은 <b>메인 타깃에 꽂히는 DPS</b>다. 루난 볼트가 서브 타깃에 준 피해는 집계하지 않고, "
        "Q 확산이 메인으로 되돌린 분량만 더한다.",
        "윤탈 치명타는 <b>구매 코어 0% → 다음 코어 25%</b> 가정이다. 1~2코어 순서 결론을 직접 지배한다.",
    ],
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
SCENARIOS = [("tc1", 1), ("tc2", 2), ("tc3", 3), ("mix", None)]   # None = 1:1:1 혼합

ITEM_KO = {
    "kraken": "크라켄", "yuntal25": "윤탈", "runaan": "루난", "ie": "무한", "ldr": "도미닉",
    "c44": "C44", "pd": "유령무희", "guinsoo": "구인수", "terminus": "경계", "bot": "몰왕검",
    "storm": "폭풍갈퀴", "statikk": "스태틱", "nashor": "내셔", "shadowflame": "그림자불꽃",
    "rabadon": "라바돈", "void": "공허", "mortal": "징수의총",
}


def _legal_next(prefix, depth):
    """다음 슬롯(depth+1)에서 살 수 있는 아이템 — 슬롯 제약 + 관통 배타."""
    slot = depth + 1
    if slot > HORIZON:        # 5코어 도달 — 더 살 칸이 없다
        return []
    out = []
    for key in CANDIDATES_BY_SLOT[slot]:
        if key in prefix:
            continue
        if not pen_rule_ok(tuple(prefix) + (key,)):
            continue
        out.append(key)
    return out


def _marginal(cache, prefix, item):
    """(하프 항, 완성 항, 완성 시점 dps/gold, 하프 dps/gold) — 직전 상태 대비 마지널 DPG."""
    depth = len(prefix)
    d_prev, g_prev = cache.sim(tuple(prefix)) if prefix else (0.0, 0.0)
    half_dps = half_gold = None
    h_term = 0.0
    if _half_enabled_for_slot(depth + 1, HORIZON):
        half_dps, half_gold, _comps = sim_half(cache, tuple(prefix), item)
        d_gold = half_gold - g_prev
        if d_gold > 0:
            h_term = (half_dps - d_prev) / (d_gold / 1000.0)
        d_prev, g_prev = max(d_prev, half_dps), max(g_prev, half_gold)

    full_dps, full_gold = cache.sim(tuple(prefix) + (item,))
    d_gold = full_gold - g_prev
    f_term = (full_dps - d_prev) / (d_gold / 1000.0) if d_gold > 0 else 0.0
    return h_term, f_term, full_dps, full_gold, half_dps, half_gold


class Explorer:
    """노드별 후보 점수를 만드는 집합 단위 DP."""

    def __init__(self, cache, gamma=GAMMA):
        self.cache = cache
        self.gamma = gamma
        self.root_gamma = sqrt(gamma)
        self._v = {}
        self._cand = {}

    def _key(self, prefix):
        # DPS 는 장착 집합에만 의존하되, 윤탈은 "방금 산 코어"인지에 따라 치확이 갈린다.
        return tuple(sorted(prefix)), bool(prefix) and prefix[-1] == "yuntal25"

    def candidates(self, prefix):
        """프리픽스에서 고를 수 있는 후보 전부 — [{item, score, gold, dps, dpg, half_*}]."""
        key = self._key(prefix)
        if key in self._cand:
            return self._cand[key]
        prev_dps, prev_gold = self.cache.sim(tuple(prefix)) if prefix else (0.0, 0.0)
        rows = []
        for item in _legal_next(prefix, len(prefix)):
            h, f, dps, gold, h_dps, h_gold = _marginal(self.cache, prefix, item)
            score = h + self.root_gamma * f + self.gamma * self.value(tuple(prefix) + (item,))
            # 이 한 칸의 **마지널 DPG** — 직전 완성 상태 대비 늘어난 DPS 를 그 사이 쓴 골드로 나눈 값.
            # score 가 미래까지 본 할인합이라면 이쪽은 "지금 이 아이템이 산 골드효율"이다.
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
        self._v[key] = 0.0          # 재귀 진입 가드(같은 깊이에서 순환 없음)
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
            return out          # 5코어 도달 — 노드를 만들지 않는다(탐색기가 "후보 없음"으로 처리)
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
                # rel = 1차 지표(mDPG) 1위 대비. score 대비는 rel_score 로 따로 싣는다.
                "rel": round(100.0 * (r["mdpg"] / best_m - 1.0), 1) if best_m else 0.0,
                "rel_score": round(100.0 * (r["score"] / best_s - 1.0), 1) if best_s else 0.0,
                "tier": "main" if i < MAIN_TOP_N else "minor",
            }
            for i, r in enumerate(rows)
        }
        for r in rows[:MAIN_TOP_N]:
            self.walk(tuple(prefix) + (r["item"],), out)
        return out


def _cache_for(tc):
    if tc is None:
        caches = {t: SimCache(PKG, t, SHARD) for t in (1, 2, 3)}
        return MixedSimCache(PKG, shards=SHARD, caches=caches)
    return SimCache(PKG, tc, SHARD)


def verify(archetype="bruiser", tc=2):
    """원본 greedy(순열 전수)와 1코어 후보 점수가 일치하는지 확인."""
    Y.set_target_archetype(archetype)
    cache = _cache_for(tc)
    ref = solve_greedy_half(cache, gamma=GAMMA)
    ref_alts = {a["item"]: a["score"] for a in ref["steps"][0]["alternatives"]}
    mine = {r["item"]: r["score"] for r in Explorer(cache).candidates(())}
    print(f"[verify] {archetype}/tc{tc} — greedy 1코어 궤적 {ref['trajectory'][0]}")
    ok = True
    for item, score in sorted(ref_alts.items(), key=lambda kv: -kv[1]):
        delta = mine[item] - score
        flag = "OK " if abs(delta) < 1e-6 else "DIFF"
        ok &= abs(delta) < 1e-6
        print(f"   {flag} {item:<10} greedy {score:9.3f}  dp {mine[item]:9.3f}  Δ{delta:+.6f}")
    print("[verify]", "일치" if ok else "불일치 — 점수식 재확인 필요")
    return ok


def build():
    out = {
        "meta": {
            "gamma": GAMMA, "horizon": HORIZON, "main_top_n": MAIN_TOP_N,
            "package": "도란활 + 탐욕의 군화 + 민첩함",
            "shard": "공속10% + 적응형AD 5.4",
            "rune": "치명적 속도 + 체력차 극복",
            "order": f"1차 mDPG, 차이 {MDPG_TIE_PCT}% 안쪽이면 동률로 보고 score 로 세운다.",
            "mdpg_tie_pct": MDPG_TIE_PCT,
            "score": "γ-할인 마지널 DPG 합(하프 √γ, 코어 γ). 미래 코어까지 본 값. 하프는 점수에만 반영.",
            "mdpg": "이 한 칸의 마지널 DPG — (늘어난 DPS) / (이 칸에 쓴 골드/1000). 미래를 보지 않는 즉시 효율.",
        },
        "copy": COPY,
        "items": ITEM_KO,
        "archetypes": [{"id": k, "label": v["label"], "desc": v["desc"],
                        "tiers": {str(t): list(s) for t, s in v["tiers"].items()}}
                       for k, v in TARGET_ARCHETYPES.items()],
        "scenarios": [s for s, _ in SCENARIOS],
        "nodes": {},
    }
    for arch in TARGET_ARCHETYPES:
        Y.set_target_archetype(arch)
        for scen, tc in SCENARIOS:
            explorer = Explorer(_cache_for(tc))
            out["nodes"][f"{arch}|{scen}"] = explorer.walk()
            print(f"  done {arch}/{scen}: 노드 {len(out['nodes'][f'{arch}|{scen}'])}")
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--verify" in args:
        raise SystemExit(0 if verify() else 1)
    dest = args[0] if args else "docs/reports/yunara_explorer.json"
    data = build()
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    total = sum(len(v) for v in data["nodes"].values())
    print(f"saved -> {dest}  (상황 {len(data['nodes'])} · 노드 {total})")
