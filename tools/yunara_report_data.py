# -*- coding: utf-8 -*-
"""유나라 템트리 리포트용 파워 곡선 데이터 생성 — `docs/reports/yunara_curves.json`.

실행: `python -m tools.yunara_report_data [출력경로]`  (repo 루트에서, 약 2분)

빌드별로 **하프 코어(아이템 사이 하위템 구간)와 완성 코어**의 DPS·누적 골드를,
타깃 아키타입 3종 × 교전 시나리오 4종으로 전부 뽑아 JSON 한 벌로 만든다.
그 JSON 을 `tools.build_explorer_report` 가 템플릿에 주입해 배포용 HTML 을 만든다.

· 아키타입 표는 `adc_sim.simulations.target_archetypes` 에서 그대로 가져온다 —
  여기서 숫자를 다시 적지 말 것(리포트와 시뮬이 다른 표를 보게 된다).
· 패키지·파편은 S1(도란활+탐욕의 군화+민첩함)·공속10%+적응형AD5.4 고정. 룬은 치속+체력차 극복
  (`simulate_yunara_core_path` 기본값).
· 혼합(mix)은 적1:적2:적3 = 1:1:1 — 유나라 기본 선택 지표와 같은 규약.
"""
import json
import sys

from adc_sim.simulations import yunara as Y
from adc_sim.simulations.yunara import SimCache, sim_half, SHARD_SCENARIOS
from adc_sim.data.items_data import ADC_PACKAGES_VIABLE

PKG = [p for p in ADC_PACKAGES_VIABLE if p["label"] == "Bow+Glut"][0]  # 도란활+탐욕+민첩함
SHARD = SHARD_SCENARIOS["AS10%+AD5.4"]

BUILDS = [
    {"id": "opt_solo", "name": "윤탈-무한-도미닉-C44-크라켄",
     "path": ["yuntal25", "ie", "ldr", "c44", "kraken"], "kind": "opt", "group": "yun"},
    {"id": "opt_fight", "name": "윤탈-크라켄-도미닉-루난-무한",
     "path": ["yuntal25", "kraken", "ldr", "runaan", "ie"], "kind": "opt", "group": "yun"},
    {"id": "opt_run3", "name": "윤탈-크라켄-루난-도미닉-무한",
     "path": ["yuntal25", "kraken", "runaan", "ldr", "ie"], "kind": "opt", "group": "yun"},
    {"id": "meta_yun", "name": "윤탈-루난-무한-도미닉-C44",
     "path": ["yuntal25", "runaan", "ie", "ldr", "c44"], "kind": "meta", "group": "yun"},
    {"id": "late_solo", "name": "크라켄-윤탈-도미닉-무한-C44",
     "path": ["kraken", "yuntal25", "ldr", "ie", "c44"], "kind": "late", "group": "krk"},
    {"id": "late_run", "name": "크라켄-윤탈-루난-도미닉-C44",
     "path": ["kraken", "yuntal25", "runaan", "ldr", "c44"], "kind": "late", "group": "krk"},
    {"id": "meta_krk", "name": "크라켄-루난-무한-도미닉-C44",
     "path": ["kraken", "runaan", "ie", "ldr", "c44"], "kind": "meta", "group": "krk"},
]
W3 = 1.0 / 3.0
SCEN = [("tc1", {1: 1.0}), ("tc2", {2: 1.0}), ("tc3", {3: 1.0}),
        ("mix", {1: W3, 2: W3, 3: W3})]

# 타깃 아키타입 — 코어 1~5 시점(적 레벨 ≈ 9~17)의 체력/방어력/마저.
# standard 는 프로젝트 표준 티어표, 나머지는 방어템 보유 정도로 갈랐다.
from adc_sim.simulations.target_archetypes import TARGET_ARCHETYPES

ARCHETYPES = [
    {"id": key, "label": spec["label"], "desc": spec["desc"],
     "tiers": {tier: tuple(stats) for tier, stats in spec["tiers"].items()}}
    for key, spec in TARGET_ARCHETYPES.items()
]


def apply_archetype(arch):
    """yunara 모듈의 타깃 표를 제자리 교체 — 완성 코어와 하프(보간) 둘 다 이 표를 읽는다."""
    Y.CORE_TARGET_STATS.clear()
    for tier, (hp, ar, mr) in arch["tiers"].items():
        Y.CORE_TARGET_STATS[tier] = {"hp": hp, "armor": ar, "mr": mr}
SHORT = {"kraken": "크라켄", "yuntal25": "윤탈", "runaan": "루난", "ie": "무한", "ldr": "도미닉",
         "c44": "C44", "pd": "유령무희", "guinsoo": "구인수"}

out = {"package": "도란활 + 탐욕의 군화 + 민첩함", "shard": "공속10% + 적응형AD 5.4",
       "rune": "치명적 속도 + 체력차 극복", "builds": [], "scenarios": [s for s, _ in SCEN],
       "archetypes": [{k: a[k] for k in ("id", "label", "desc")} | {"tiers": a["tiers"]}
                      for a in ARCHETYPES]}

entries = {}
for b in BUILDS:
    e = {k: b[k] for k in ("id", "name", "kind", "group")}
    e["path_ko"] = [SHORT.get(k, k) for k in b["path"]]
    e["series"] = {}
    entries[b["id"]] = e
    out["builds"].append(e)

for arch in ARCHETYPES:
    apply_archetype(arch)
    caches = {tc: SimCache(PKG, tc, SHARD) for tc in (1, 2, 3)}

    def blend(weights, fn):
        dps, gold = 0.0, 0
        for tc, w in weights.items():
            d, g = fn(caches[tc], tc)
            dps += w * d
            gold = g
        return dps, gold

    for b in BUILDS:
        entry = entries[b["id"]]
        entry["series"][arch["id"]] = {}
        for sname, weights in SCEN:
            pts = []
            for tier in range(1, len(b["path"]) + 1):
                done = tuple(b["path"][:tier - 1])
                nxt = b["path"][tier - 1]
                if tier < 5:   # 5코어 하프는 프로젝트 기본대로 생략
                    hd, hg = blend(weights, lambda c, tc, d=done, n=nxt: sim_half(c, d, n)[:2])
                    comps = sim_half(caches[1], done, nxt)[2]
                    pts.append({"step": f"{tier}C-half", "tier": tier - 0.5, "gold": hg,
                                "dps": round(hd, 1), "dpg": round(hd / (hg / 1000.0), 1),
                                "label": f"{tier}코어 하프", "comps": list(comps)})
                fd, fg = blend(weights, lambda c, tc, p=tuple(b["path"][:tier]): c.sim(p))
                pts.append({"step": f"{tier}C", "tier": tier, "gold": fg,
                            "dps": round(fd, 1), "dpg": round(fd / (fg / 1000.0), 1),
                            "label": f"{tier}코어 {SHORT.get(nxt, nxt)}", "comps": []})
            entry["series"][arch["id"]][sname] = pts
    print("done arch", arch["id"])

DEFAULT_OUT = "docs/reports/yunara_curves.json"

dest = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT
with open(dest, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
    f.write("\n")
print(f"saved -> {dest}  (빌드 {len(out['builds'])} × 아키타입 {len(out['archetypes'])} × 시나리오 {len(SCEN)})")
