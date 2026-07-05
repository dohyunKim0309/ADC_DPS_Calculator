# 관통 배타 전역화 + 점수 모드 + 통일 러너 Phase 1(베인) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ① void+terminus 마관 배타를 전 시뮬에 적용(게임 규칙), ② 점수 방식(weighted/discounted)을 settings에서 선택 가능하게, ③ 공통 랭킹 러너 `ranking_core.rank_builds`를 만들어 베인을 첫 이관(동작 보존 검증 포함), ④ 기본 모드를 discounted γ=0.9로 전환.

**Architecture:** 배타 규칙은 `items_data.py`(아이템 속성 단일 출처)의 세트 2개+`pen_rule_ok()`로 중앙화. 가중치는 `settings.RANKING_SCORING`에서 `CORE_WEIGHTS_RAW`를 파생(소비처 무변경). 러너는 vayne `_rank_rows`의 파라미터화(시뮬fn·경로·컨트롤·가중 주입). 이관 검증은 소형 경로셋 골든 테스트(이관 전 캡처→이관 후 동일).

**Tech Stack:** Python 3.10 (`.venv`), pytest. 스펙: `docs/superpowers/specs/2026-07-06-ranking-core-design.md`

## Global Constraints

- 인터프리터 `.venv/bin/python`, repo 루트 `-m` 실행. 브랜치 feat/ranking-core.
- **태스크 순서 고정**: A(배타)→B(설정, mode="weighted" 초기값=동작보존)→C(러너)→D(베인 이관+골든)→E(discounted 전환+문서). D까지 랭킹 수치 불변이 원칙(A의 코그모 void+terminus 제거만 예외 — 의도된 규칙 수정).
- 외부 인터페이스 불변: `simulate_vayne_core_path`/`get_vayne_4core_top1_build`/`get_vayne_powercompare_builds`/`build_vayne_core_report_meta`(power_compare가 import), 각 시뮬의 `__main__` 출력 형식.
- 마관 배타 정의(게임 규칙, 사용자 확정): 방관 {ldr, mortal, terminus} ≤1 **AND** 마관 {void, terminus} ≤1. ldr+void는 합법, terminus+void/terminus+ldr 불법.
- 커밋: 한국어 conventional + 트레일러 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task A: 관통 배타 전역화

**Files:**
- Modify: `adc_sim/data/items_data.py` (상수 2개+헬퍼, `DORAN_SHORT` 위쪽에)
- Modify: `adc_sim/simulations/{ashe,kaisa,corki,ezreal,vayne,cogmaw,cogmaw_sequential,yunara,sim_settings}.py` (로컬 배타 상수/체크 교체)
- Test: `tests/test_pen_rule.py` (신규)

**Interfaces:**
- Produces: `items_data.ARMOR_PEN_EXCLUSIVE: frozenset`, `MAGIC_PEN_EXCLUSIVE: frozenset`, `pen_rule_ok(keys) -> bool` — 이후 전 시뮬·러너가 사용.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_pen_rule.py`:

```python
"""관통 배타 게임 규칙: 방관 ≤1 AND 마관 ≤1 (terminus 양쪽 겸비)."""
from adc_sim.data.items_data import (
    ARMOR_PEN_EXCLUSIVE, MAGIC_PEN_EXCLUSIVE, pen_rule_ok,
)


def test_exclusive_sets():
    assert ARMOR_PEN_EXCLUSIVE == frozenset({"ldr", "mortal", "terminus"})
    assert MAGIC_PEN_EXCLUSIVE == frozenset({"void", "terminus"})


def test_pen_rule_ok_cases():
    assert pen_rule_ok(("guinsoo", "nashor", "pd", "ie"))
    assert pen_rule_ok(("ldr", "void", "pd", "ie"))          # 방관1+마관1(다른 아이템) 합법
    assert pen_rule_ok(("terminus", "guinsoo", "pd", "ie"))
    assert not pen_rule_ok(("terminus", "void", "pd", "ie"))  # terminus 는 마관 겸비 → void 와 불법
    assert not pen_rule_ok(("terminus", "ldr", "pd", "ie"))
    assert not pen_rule_ok(("ldr", "mortal", "pd", "ie"))
    assert pen_rule_ok(("void", "pd"))                        # 부분 빌드도 판정 가능
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_pen_rule.py -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: 구현(1/2)** — `adc_sim/data/items_data.py`의 `DORAN_OPTIONS` 정의 위에 추가:

```python
# 관통 배타 — 게임 규칙(챔피언 무관): 방관 1개 + 마관 1개, terminus 는 양쪽 겸비.
ARMOR_PEN_EXCLUSIVE = frozenset({"ldr", "mortal", "terminus"})
MAGIC_PEN_EXCLUSIVE = frozenset({"void", "terminus"})


def pen_rule_ok(keys):
    """빌드(부분 포함) 내 방관 ≤1 AND 마관 ≤1. [사용자 확정 2026-07-06: 게임 자체 규칙]"""
    armor = sum(1 for k in keys if k in ARMOR_PEN_EXCLUSIVE)
    magic = sum(1 for k in keys if k in MAGIC_PEN_EXCLUSIVE)
    return armor <= 1 and magic <= 1
```

- [ ] **Step 4: 구현(2/2) — 소비처 교체.** 각 파일에서 로컬 배타 상수 정의를 삭제하고 `from adc_sim.data.items_data import pen_rule_ok`(필요 시 상수도) import 후, 기존 카운트 체크를 `pen_rule_ok`로 교체. 교체 규칙: `sum(1 for k in KEYS if k in <armor세트>) > 1 → continue/skip` 패턴은 `not pen_rule_ok(KEYS) → continue/skip`으로. 사이트 목록(정확 위치는 grep으로 재확인 — 라인은 이동됐을 수 있음):
  - `vayne.py`: `PEN_EXCLUSIVE` 상수(≈87행) 삭제, `_build_all_paths`의 체크(≈107행) 교체.
  - `ezreal.py`: `PEN_EXCLUSIVE`(≈111행)/체크(≈135행).
  - `cogmaw.py`: 두 곳 — `get_cogmaw_4core_top1_build` 내 `pen_exclusive`(≈101/114행), `__main__`(≈448/469행).
  - `cogmaw_sequential.py`: `PEN_EXCLUSIVE` 상수(≈16행) 삭제, `legal_next_items`를:
    ```python
    def legal_next_items(owned, slot, candidates_map):
        out = []
        for k in candidates_map[slot]:
            if k in owned:
                continue
            if not pen_rule_ok(tuple(owned) + (k,)):
                continue
            out.append(k)
        return out
    ```
    (기존 armor-only 증분 체크의 상위집합 — 마관 규칙 추가.)
  - `kaisa.py`: 두 곳(≈183/206, ≈362/387 — 5키 변형 포함).
  - `corki.py`: 두 곳(≈200/232, ≈298/325).
  - `ashe.py`: 두 곳(≈142/155/172, ≈650/663/684 — 케이스5 빌더 포함).
  - `yunara.py`: 자체 `ARMOR_PEN_EXCLUSIVE`/`MAGIC_PEN_EXCLUSIVE`(≈18-19행) 삭제 → items_data에서 import, 4곳 체크(≈51-53/66-68)를 `pen_rule_ok`로 교체(동작 동일 — 유나라는 이미 두 규칙 적용 중).
  - `sim_settings.py`: `PEN_EXCLUSIVE_KEYS = ("ldr", "terminus", "mortal")`(≈59행) → `PEN_EXCLUSIVE_KEYS = tuple(sorted(ARMOR_PEN_EXCLUSIVE))`(import 추가). case_ranking의 hc/mortal 강제 로직 의미 불변(방관 세트만 참조).
  - `cogmaw_sequential.py`의 기존 테스트 `test_legal_next_items_pen_exclusive_and_dup`는 그대로 통과해야 함(armor 케이스만 사용).

- [ ] **Step 5: 통과 확인 + 전체 스위트**

Run: `.venv/bin/python -m pytest tests/test_pen_rule.py tests/test_cogmaw_sequential.py -v`
Expected: 신규 2 + 기존 8 전부 통과.
Run: `.venv/bin/python -m pytest tests/ -q`
Expected: **96 passed** (94+2). 실패 시 원인 조사(특히 랭킹 형태 테스트) 후 보고.

- [ ] **Step 6: 커밋**

```bash
git add tests/test_pen_rule.py adc_sim/data/items_data.py adc_sim/simulations/ashe.py adc_sim/simulations/kaisa.py adc_sim/simulations/corki.py adc_sim/simulations/ezreal.py adc_sim/simulations/vayne.py adc_sim/simulations/cogmaw.py adc_sim/simulations/cogmaw_sequential.py adc_sim/simulations/yunara.py adc_sim/simulations/sim_settings.py
git commit -m "feat(items): 관통 배타 중앙화 + void/terminus 마관 배타 전역 적용(게임 규칙)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task B: 점수 모드 설정 (파생, 초기 mode="weighted" = 동작 보존)

**Files:**
- Modify: `adc_sim/settings.py` (`CORE_WEIGHTS_RAW` 블록 교체)
- Test: `tests/test_ranking_scoring.py` (신규)

**Interfaces:**
- Produces: `settings.RANKING_SCORING: dict`, `settings.derive_core_weights(scoring, n=4) -> list[float]`; `CORE_WEIGHTS_RAW`/`CORE_WEIGHTS_LABEL`은 파생값(소비처 ~30곳 무변경).

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_ranking_scoring.py`:

```python
from adc_sim.settings import (
    RANKING_SCORING, derive_core_weights, CORE_WEIGHTS_RAW, CORE_WEIGHTS_LABEL,
)


def test_weighted_mode_derivation():
    w = derive_core_weights({"mode": "weighted", "fixed_raw": [4, 4, 3, 3], "gamma": 0.9})
    assert w == [4, 4, 3, 3]


def test_discounted_mode_derivation():
    w = derive_core_weights({"mode": "discounted", "fixed_raw": [4, 4, 3, 3], "gamma": 0.9})
    assert all(abs(a - b) < 1e-12 for a, b in zip(w, [0.9, 0.81, 0.729, 0.6561]))


def test_n_cores_slicing():
    w3 = derive_core_weights({"mode": "discounted", "fixed_raw": [4, 4, 3, 3], "gamma": 0.5}, n=3)
    assert all(abs(a - b) < 1e-12 for a, b in zip(w3, [0.5, 0.25, 0.125]))


def test_globals_are_derived_and_consistent():
    assert CORE_WEIGHTS_RAW == derive_core_weights(RANKING_SCORING)
    assert isinstance(CORE_WEIGHTS_LABEL, str) and len(CORE_WEIGHTS_LABEL) > 0
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_ranking_scoring.py -v`
Expected: FAIL — ImportError (`RANKING_SCORING`/`derive_core_weights` 없음).

- [ ] **Step 3: 구현** — `settings.py`의 기존 블록:

```python
CORE_WEIGHTS_RAW = [4.0, 4.0, 3.0, 3.0]
# 출력 라벨용(예: "1:1:1:1") — CORE_WEIGHTS_RAW 에서 자동 생성되니 가중치 바꾸면 라벨도 따라감.
CORE_WEIGHTS_LABEL = ":".join(f"{w:g}" for w in CORE_WEIGHTS_RAW)
```
→ 교체:
```python
# 점수 방식 선택 [사용자 확정 2026-07-06]: "weighted"=고정 가중합 / "discounted"=γ-할인합.
# 할인합은 코어별 가중 [γ^1..γ^n] 과 동치라 기존 rel-DPG 파이프라인을 그대로 쓴다.
RANKING_SCORING = {
    "mode": "weighted",           # Task E 에서 "discounted" 로 전환 예정
    "fixed_raw": [4.0, 4.0, 3.0, 3.0],
    "gamma": 0.9,
}


def derive_core_weights(scoring, n=4):
    """RANKING_SCORING → 코어별 raw 가중 벡터(길이 n)."""
    if scoring["mode"] == "discounted":
        g = scoring["gamma"]
        return [g ** k for k in range(1, n + 1)]
    return list(scoring["fixed_raw"][:n])


CORE_WEIGHTS_RAW = derive_core_weights(RANKING_SCORING)
_mode_tag = "" if RANKING_SCORING["mode"] == "weighted" else f" (disc γ={RANKING_SCORING['gamma']:g})"
CORE_WEIGHTS_LABEL = ":".join(f"{w:g}" for w in CORE_WEIGHTS_RAW) + _mode_tag
```

- [ ] **Step 4: 통과 확인 + 동작 보존 스팟체크**

Run: `.venv/bin/python -m pytest tests/test_ranking_scoring.py -v` → 4 passed.
Run: `.venv/bin/python -c "from adc_sim.settings import CORE_WEIGHTS_RAW, CORE_WEIGHTS_LABEL; print(CORE_WEIGHTS_RAW, CORE_WEIGHTS_LABEL)"`
Expected: `[4.0, 4.0, 3.0, 3.0] 4:4:3:3` (기존과 동일 — 동작 보존).

- [ ] **Step 5: 커밋**

```bash
git add tests/test_ranking_scoring.py adc_sim/settings.py
git commit -m "feat(settings): RANKING_SCORING 점수 모드(weighted/discounted γ) + CORE_WEIGHTS 파생

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task C: 공통 랭킹 러너 `ranking_core.py`

**Files:**
- Create: `adc_sim/simulations/ranking_core.py`
- Test: `tests/test_ranking_core.py` (신규)

**Interfaces:**
- Consumes: `settings.CORE_WEIGHTS_RAW`(기본 가중), `items_data.ADC_PACKAGES`.
- Produces: `rank_builds(simulate_fn, all_paths, control_path, weights_raw=None, packages=None, n_cores=4, pinned_paths=()) -> (rows_dedup, best_control)` — 행 스키마는 vayne `_rank_rows`와 동일(path/doran/boots/rune_as/pkg_label/x/y/dpg/is_control/dedupe_eff/weighted_dpg/weighted_dps/core_rel_delta_pct_4/rel_dpg_score) + `pinned_tag`(기본 None).

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_ranking_core.py`:

```python
"""공통 랭킹 러너 — 합성 simulate_fn 으로 수계산 검증(시뮬 무의존)."""
from adc_sim.simulations.ranking_core import rank_builds

# 합성 세계: DPS = 앞 tier개 아이템 가치 합, gold = 1000×tier.
VALUE = {"a": 100.0, "b": 90.0, "c": 80.0, "x": 70.0, "y": 60.0}
PKGS = ({"key": "T", "label": "T", "doran": None, "boots": "berserker", "rune_as": 0.0},)


def _sim(path, tier, doran_key=None, boots_key=None, rune_as_bonus=0.0):
    return sum(VALUE[k] for k in path[:tier]), 1000.0 * tier


PATHS = [("a", "b", "x", "y"), ("b", "a", "x", "y"), ("c", "x", "y", "a"),
         ("x", "y", "a", "b")]  # 컨트롤 = ("x","y","a","b")


def test_rank_builds_dedup_control_and_scores():
    rows, best_ctrl = rank_builds(_sim, PATHS, ("x", "y", "a", "b"),
                                  weights_raw=[1, 1, 1, 1], packages=PKGS)
    # {a,b,x,y} 집합은 3개 순서 중 최고 dedupe_eff 하나 + 컨트롤 정규순서 고정 →
    # 컨트롤 집합은 컨트롤 순서 행만 잔존, {c,x,y,a} 1행 → 총 2행.
    assert len(rows) == 2
    assert best_ctrl["path"] == ("x", "y", "a", "b") and best_ctrl["is_control"]
    # 컨트롤 rel_dpg_score == 100 (자기 자신 baseline)
    assert abs(best_ctrl["rel_dpg_score"] - 100.0) < 1e-9
    # 수계산: {c,x,y,a} 경로 c-x-y-a 의 tier별 DPS = 80,150,210,310 / dpg = 80,75,70,77.5
    # 컨트롤 x-y-a-b: 70,130,230,320 → dpg 70,65,76.667,80
    other = next(r for r in rows if not r["is_control"])
    rel = [80 / 70, 75 / 65, 70 / (230 / 3), 77.5 / 80]
    expected = sum(r * 100 for r in rel) / 4
    assert abs(other["rel_dpg_score"] - expected) < 1e-9


def test_rank_builds_default_weights_from_settings():
    from adc_sim.settings import CORE_WEIGHTS_RAW
    rows, _ = rank_builds(_sim, PATHS, ("x", "y", "a", "b"), packages=PKGS)
    r = rows[0]
    w = [x / sum(CORE_WEIGHTS_RAW) for x in CORE_WEIGHTS_RAW]
    assert abs(r["weighted_dpg"] - sum(w[i] * r["dpg"][i] for i in range(4))) < 1e-9


def test_rank_builds_missing_control_raises():
    import pytest
    with pytest.raises(RuntimeError):
        rank_builds(_sim, [("a", "b", "x", "y")], ("c", "x", "y", "a"), packages=PKGS)


def test_rank_builds_pinned_paths_kept_and_tagged():
    rows, _ = rank_builds(_sim, PATHS, ("x", "y", "a", "b"), packages=PKGS,
                          pinned_paths=(("PIN1", ("c", "x", "y", "a")),))
    pinned = [r for r in rows if r.get("pinned_tag") == "PIN1"]
    assert len(pinned) == 1 and pinned[0]["path"] == ("c", "x", "y", "a")
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_ranking_core.py -v`
Expected: FAIL — ModuleNotFoundError.

- [ ] **Step 3: 구현** — `adc_sim/simulations/ranking_core.py` 생성 (vayne `_rank_rows`의 파라미터화 — 동작 동일이 목표):

```python
"""챔피언 공통 랭킹 파이프라인 — 경로×패키지 시뮬 → sorted-combo dedup → 컨트롤/고정행
canonical 고정 → 가중 DPG/DPS → 컨트롤 baseline 상대 점수(rel_dpg_score).

가중은 settings.CORE_WEIGHTS_RAW(RANKING_SCORING 파생)가 기본, weights_raw 인자로 오버라이드
(사용자 요구: 통일 러너 + 인자로 점수 방식 결정). Phase 1: vayne 이관.
spec: docs/superpowers/specs/2026-07-06-ranking-core-design.md
"""
from adc_sim import settings
from adc_sim.data.items_data import ADC_PACKAGES


def rank_builds(simulate_fn, all_paths, control_path, weights_raw=None,
                packages=None, n_cores=4, pinned_paths=()):
    """공통 랭킹. 반환 (rows_dedup, best_control) — 행 스키마는 기존 챔피언 시뮬과 동일.

    simulate_fn(path, tier, doran_key=, boots_key=, rune_as_bonus=) -> (dps, gold).
    pinned_paths: ((태그, 경로), ...) — 컨트롤처럼 지정 순서로 고정·항상 잔존(표시 전용).
    """
    if weights_raw is None:
        weights_raw = list(settings.CORE_WEIGHTS_RAW[:n_cores])
    if packages is None:
        packages = ADC_PACKAGES
    dedupe_weight_raw = list(weights_raw)
    weight_sum = sum(weights_raw)
    core_weights = [w / weight_sum for w in weights_raw]
    ctrl_combo = tuple(sorted(control_path))
    pinned_combos = {tuple(sorted(p)): (tag, tuple(p)) for tag, p in pinned_paths}

    rows = []
    for path in all_paths:
        for pkg in packages:
            kw = dict(doran_key=pkg["doran"], boots_key=pkg["boots"],
                      rune_as_bonus=pkg["rune_as"])
            dps_list, cost_list = [], []
            for tier in range(1, n_cores + 1):
                d, c = simulate_fn(path, tier, **kw)
                dps_list.append(d)
                cost_list.append(c)
            dpg = [dps_list[i] / (cost_list[i] / 1000.0) if cost_list[i] > 0 else 0.0
                   for i in range(n_cores)]
            combo = tuple(sorted(path))
            rows.append({
                "path": tuple(path), "doran": pkg["doran"], "boots": pkg["boots"],
                "rune_as": pkg["rune_as"], "pkg_label": pkg["label"],
                "x": cost_list, "y": dps_list, "dpg": dpg,
                "is_control": combo == ctrl_combo,
                "pinned_tag": pinned_combos[combo][0] if combo in pinned_combos else None,
                "dedupe_eff": sum(dedupe_weight_raw[i] * dpg[i] for i in range(n_cores)),
            })

    dedupe_best = {}
    for r in rows:
        key = tuple(sorted(r["path"]))
        if key not in dedupe_best or r["dedupe_eff"] > dedupe_best[key]["dedupe_eff"]:
            dedupe_best[key] = r
    rows_dedup = list(dedupe_best.values())

    # 컨트롤·pinned 는 지정 순서(canonical)로 고정
    rows_dedup = [r for r in rows_dedup
                  if not r["is_control"] and r["pinned_tag"] is None]
    ctrl_cands = [r for r in rows if tuple(r["path"]) == tuple(control_path)]
    if ctrl_cands:
        rows_dedup.append(max(ctrl_cands, key=lambda r: r["dedupe_eff"]))
    for _tag, p in pinned_paths:
        cands = [r for r in rows if tuple(r["path"]) == tuple(p)]
        if cands:
            rows_dedup.append(max(cands, key=lambda r: r["dedupe_eff"]))

    for r in rows_dedup:
        r["weighted_dpg"] = sum(core_weights[i] * r["dpg"][i] for i in range(n_cores))
        r["weighted_dps"] = sum(core_weights[i] * r["y"][i] for i in range(n_cores))

    control_rows = [r for r in rows_dedup if r["is_control"]]
    if not control_rows:
        raise RuntimeError(
            f"Control build {control_path} not found in search space. "
            "Check candidate pools contain the control items."
        )
    best_control = max(control_rows, key=lambda r: r["weighted_dpg"])
    baseline = best_control["dpg"][:n_cores]

    for r in rows_dedup:
        core_rel_pct = [
            (r["dpg"][i] / baseline[i] * 100.0 if baseline[i] > 0 else 0.0)
            for i in range(n_cores)
        ]
        r["core_rel_delta_pct_4"] = [p - 100.0 for p in core_rel_pct]
        r["rel_dpg_score"] = sum(core_weights[i] * core_rel_pct[i] for i in range(n_cores))

    return rows_dedup, best_control
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_ranking_core.py -v`
Expected: 4 passed.

- [ ] **Step 5: 커밋**

```bash
git add tests/test_ranking_core.py adc_sim/simulations/ranking_core.py
git commit -m "feat(ranking): 공통 랭킹 러너 rank_builds(시뮬fn·가중·pinned 주입)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task D: 베인 이관 + 골든 동작 보존 검증

**Files:**
- Modify: `adc_sim/simulations/vayne.py` (`_rank_rows` 본문 → `rank_builds` 위임)
- Test: `tests/test_vayne_ranking_golden.py` (신규 — 이관 **전** 골든 캡처)

**Interfaces:**
- Consumes: Task C `rank_builds`. vayne 외부 인터페이스 전부 불변.

- [ ] **Step 1: 골든 테스트 작성(이관 전 기준값 캡처).** 먼저 아래 캡처 스크립트를 실행해 **이관 전** `_rank_rows` 출력을 기록:

Run:
```bash
.venv/bin/python -c "
from adc_sim.simulations.vayne import _rank_rows, CONTROL_PATH
paths = [CONTROL_PATH, ('kraken','pd','ie','ldr'), ('yuntal25','c44','ie','ldr'),
         ('guinsoo','botrk','terminus','pd'), ('kraken','guinsoo','ie','pd')]
rows, ctrl = _rank_rows(paths)
rows_sorted = sorted(rows, key=lambda r: r['rel_dpg_score'], reverse=True)
print('n_rows', len(rows_sorted))
for r in rows_sorted: print(tuple(r['path']), r['pkg_label'], round(r['rel_dpg_score'], 6), round(r['weighted_dpg'], 6))
print('ctrl', round(ctrl['weighted_dpg'], 6))"
```
출력값을 그대로 `tests/test_vayne_ranking_golden.py`에 골든으로 굳힌다(구조는 아래, `GOLDEN` 딕셔너리 값을 캡처 출력으로 채움):

```python
"""베인 러너 이관 동작 보존 골든 — 이관 전 _rank_rows 실측값(2026-07-06, weighted 4:4:3:3 고정).
값 출처: 이관 직전 커밋에서 캡처 스크립트 실행(값 변경 = 동작 변화 신호)."""
from adc_sim.simulations.vayne import _rank_rows, CONTROL_PATH

PATHS = [CONTROL_PATH, ("kraken", "pd", "ie", "ldr"), ("yuntal25", "c44", "ie", "ldr"),
         ("guinsoo", "botrk", "terminus", "pd"), ("kraken", "guinsoo", "ie", "pd")]

GOLDEN = {
    # (path 튜플): (rel_dpg_score, weighted_dpg)  ← 캡처 출력으로 채울 것
}
GOLDEN_N_ROWS = None      # 캡처 출력의 n_rows
GOLDEN_CTRL_WDPG = None   # 캡처 출력의 ctrl weighted_dpg


def test_vayne_rank_rows_golden():
    rows, ctrl = _rank_rows(PATHS)
    assert len(rows) == GOLDEN_N_ROWS
    assert abs(ctrl["weighted_dpg"] - GOLDEN_CTRL_WDPG) < 1e-6
    for r in rows:
        key = tuple(r["path"])
        assert key in GOLDEN, f"unexpected row {key}"
        exp_rel, exp_wdpg = GOLDEN[key]
        assert abs(r["rel_dpg_score"] - exp_rel) < 1e-6
        assert abs(r["weighted_dpg"] - exp_wdpg) < 1e-6
```

주: 골든은 **weighted 모드(현재 기본)** 값 — Task E에서 기본이 discounted 로 바뀌면 이 테스트가
깨지므로, Task E에서 이 테스트의 `_rank_rows` 호출을 `weights_raw=[4,4,3,3]` 고정으로 바꾼다
(아래 Task D Step 3에서 `_rank_rows`가 weights_raw 인자를 받게 되므로 가능).

- [ ] **Step 2: 골든 통과 확인(이관 전 코드에서)**

Run: `.venv/bin/python -m pytest tests/test_vayne_ranking_golden.py -v`
Expected: 1 passed (골든이 이관 전 코드와 일치 = 캡처 정확). ※ 시뮬 5경로×2패키지×4티어 = 40회, 수십 초.

- [ ] **Step 3: 이관** — `vayne.py`의 `_rank_rows`(122~179행 부근) 본문 전체를 위임으로 교체:

```python
def _rank_rows(all_paths, weights_raw=None):
    """전 (경로×패키지) 시뮬 → dedup → 컨트롤 정규화 RelDPG. (ranking_core 위임)"""
    return rank_builds(simulate_vayne_core_path, all_paths, CONTROL_PATH,
                       weights_raw=weights_raw)
```
상단 import 에 `from adc_sim.simulations.ranking_core import rank_builds` 추가.
`from adc_sim.settings import CORE_WEIGHTS_RAW, CORE_WEIGHTS_LABEL` 은 `CORE_WEIGHTS_LABEL`만
남긴다(`CORE_WEIGHTS_RAW` 직접 사용처가 `_rank_rows` 뿐이었으므로 — grep으로 확인 후 정리).

- [ ] **Step 4: 골든 재통과 + 전체 스위트**

Run: `.venv/bin/python -m pytest tests/test_vayne_ranking_golden.py tests/test_vayne_powercompare.py tests/test_vayne_sim.py -v`
Expected: 전부 통과 — **이관 전후 값 동일(diff 0) 증명**.
Run: `.venv/bin/python -m pytest tests/ -q`
Expected: **105 passed** (96 + 4(scoring) + 4(ranking_core) + 1(golden)).

- [ ] **Step 5: 커밋**

```bash
git add tests/test_vayne_ranking_golden.py adc_sim/simulations/vayne.py
git commit -m "refactor(vayne): 랭킹 파이프라인을 ranking_core.rank_builds 로 이관(골든 diff 0)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task E: 기본 discounted 전환 + 문서

**Files:**
- Modify: `adc_sim/settings.py` (`"mode": "weighted"` → `"discounted"`)
- Modify: `tests/test_vayne_ranking_golden.py` (weighted 고정 인자)
- Modify: `CLAUDE.md` (점수 모드·pen 규칙·ranking_core 문단 + "docs/ 예약(미생성)" 문구 수정)

**Interfaces:** 없음(설정·문서).

- [ ] **Step 1: 골든 테스트 고정** — `test_vayne_ranking_golden.py`의 `_rank_rows(PATHS)` 호출을 `_rank_rows(PATHS, weights_raw=[4.0, 4.0, 3.0, 3.0])`로 변경(골든은 weighted 기준값이므로).

- [ ] **Step 2: 기본 전환** — `settings.py` `RANKING_SCORING`의 `"mode": "weighted",` → `"mode": "discounted",` (주석 "Task E 에서 전환 예정" 제거).

- [ ] **Step 3: 전체 스위트 + 스모크**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: **105 passed** (골든은 weighted 고정이라 유지, 나머지는 형태 테스트라 무영향).
Run: `.venv/bin/python -c "from adc_sim.settings import CORE_WEIGHTS_RAW, CORE_WEIGHTS_LABEL; print(CORE_WEIGHTS_RAW, '|', CORE_WEIGHTS_LABEL)"`
Expected: `[0.9, 0.81, 0.7290000000000001, 0.6561] | 0.9:0.81:0.729:0.6561 (disc γ=0.9)` (float 표기 무관, 모드 태그 포함 확인).

- [ ] **Step 4: CLAUDE.md 갱신** — 아래 3곳:
  (a) "핵심 지표·개념"의 `rel_dpg_score` 항목 끝에 추가: `가중은 settings.RANKING_SCORING("weighted" 고정벡터 | "discounted" γ-할인, **기본 discounted γ=0.9**)에서 파생 — CORE_WEIGHTS_RAW 소비처는 자동 반영.`
  (b) "시뮬레이션 함정·규칙"의 pen 배타 언급(2b 신규 아이템 절): 기존 규칙 서술 뒤에 `구현은 items_data.pen_rule_ok(방관≤1 AND 마관≤1) 중앙화 — 시뮬별 로컬 상수 금지.` 추가.
  (c) 아키텍처 트리의 `simulations/` 아래 한 줄 추가: `ranking_core.py ─ 공통 랭킹 러너(rank_builds; Phase1 vayne 이관, cogmaw/jinx 예정)` 그리고 같은 문서의 `docs/ ─ 예약(미생성)` → `docs/ ─ superpowers 스펙·플랜 문서`.

- [ ] **Step 5: 커밋**

```bash
git add adc_sim/settings.py tests/test_vayne_ranking_golden.py CLAUDE.md
git commit -m "feat(settings): 기본 점수 모드 discounted γ=0.9 전환 + CLAUDE.md 갱신

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
