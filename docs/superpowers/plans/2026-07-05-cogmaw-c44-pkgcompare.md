# Cog'Maw C44 버프 반영 + 풀 추가 + 패키지 A/B 비교표 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** C44 아이템 버프(최대 증폭 거리 600→500)를 반영하고, 코그모 후보 풀 1~4코어에 c44를 추가하며, 코그모 랭킹 출력에 패키지 A/B RelDPG 비교표를 더한다.

**Architecture:** items.py의 C44 증폭 공식 1줄 수정 → cogmaw.py의 중복 후보 풀을 모듈 상수 `COGMAW_CORE_CANDIDATES`로 중앙화하며 c44 편입 → `_run_cogmaw_ranking` 끝에 순수 헬퍼 `_build_pkg_compare_rows`(테스트 가능) 기반 비교표 출력. 랭킹 로직·기존 표는 불변, 재시뮬 없음.

**Tech Stack:** Python 3.10 (`.venv`), pytest, matplotlib(Agg 헤드리스). 스펙: `docs/superpowers/specs/2026-07-05-cogmaw-c44-pkgcompare-design.md`

## Global Constraints

- 인터프리터는 항상 `.venv/bin/python` (시스템 python3 금지). 실행은 repo 루트에서 `-m` 모듈 방식.
- 시뮬 스크립트 실행 시 `MPLBACKEND=Agg` 접두 (끝의 `plt.show()`가 블로킹 창을 띄움).
- AGENTS.md 최소 변경 원칙 — 스펙에 없는 리팩터 금지. 후보 풀 상수 추출은 스펙에 명시된 유일한 리팩터.
- C44 버프 수치 출처: 사용자 인게임 툴팁 직접 확인(26.13) — "500 거리일 때 최대(10%) 피해". 주석에 출처 명기.
- 모든 커밋 메시지는 한국어 conventional(type(scope): …) + 트레일러 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- 작업 브랜치: `feat/cogmaw-c44` (이미 체크아웃됨).

---

### Task 1: C44 버프 반영 (증폭 최대거리 600→500)

**Files:**
- Modify: `adc_sim/items.py:379-401` (`HextechScopeC44.get_damage_modifier`)
- Test: `tests/test_c44_range.py` (신규)

**Interfaces:**
- Consumes: `adc_sim.items.HextechScopeC44` (기존 클래스; `get_damage_modifier(target, champion)`은 `champion.range`만 읽음)
- Produces: 동일 시그니처 유지 — 반환값만 500 기준으로 변경. 이후 태스크는 이 수치에 의존하지 않음.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_c44_range.py` 생성:

```python
"""C44(Hextech Scope C44) 확대 증폭 — 26.13 버프: 500 거리일 때 최대 10%."""
from adc_sim.items import HextechScopeC44


class _StubChampion:
    def __init__(self, range_):
        self.range = range_


def test_c44_max_amp_at_500_range():
    item = HextechScopeC44()
    assert abs(item.get_damage_modifier(None, _StubChampion(500)) - 0.10) < 1e-9


def test_c44_scales_below_500():
    item = HextechScopeC44()
    assert abs(item.get_damage_modifier(None, _StubChampion(250)) - 0.05) < 1e-9


def test_c44_clamped_above_500():
    item = HextechScopeC44()
    assert abs(item.get_damage_modifier(None, _StubChampion(600)) - 0.10) < 1e-9


def test_c44_vision_focus_buff_adds_range():
    item = HextechScopeC44()
    item.is_buff_active = True
    assert abs(item.get_damage_modifier(None, _StubChampion(400)) - 0.10) < 1e-9
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_c44_range.py -v`
Expected: `test_c44_max_amp_at_500_range` FAIL (0.0833… ≠ 0.10), `test_c44_scales_below_500` FAIL(0.0417… ≠ 0.05), `test_c44_vision_focus_buff_adds_range` FAIL, `test_c44_clamped_above_500` PASS(4개 중 3 FAIL).

- [ ] **Step 2.5: CDragon 교차 확인 시도 (비차단)**

Run: `.venv/bin/python -c "from adc_sim.data.cdragon import *" && .venv/bin/python -m adc_sim.data.cdragon 2>&1 | head -20`
아이템 설명에서 C44(id 확인 가능하면) 확대 문구의 거리 수치를 찾아본다. **확인되면** 주석 출처에 "CDragon 교차확인" 추가, **실패/미확인이어도 진행**(사용자 인게임 툴팁이 우선 출처 — 프로젝트 교차검증 관례에 결과만 기록).

- [ ] **Step 3: 구현** — `adc_sim/items.py` `get_damage_modifier` 내부 수정. 기존:

```python
        """
        확대: 적과의 거리(champion.range)에 따라 최대 10% 증가된 피해
        - 700 거리일 때 최대 (10%)
        - 버프 적용: 600 거리일 때 최대 (10%)
        """
```
→ 새 docstring:
```python
        """
        확대: 적과의 거리(champion.range)에 따라 최대 10% 증가된 피해
        - 500 거리일 때 최대 (10%) [26.13 버프, 사용자 인게임 툴팁 확인]
        """
```
기존:
```python
        # 2. 증폭률 계산 (최대 600 거리 기준)
        # 거리 600 이상이면 1.0, 그 미만이면 (거리/600) 비율
        ratio = min(1.0, current_range / 600.0)
```
→ 새 코드:
```python
        # 2. 증폭률 계산 (최대 500 거리 기준 — 26.13 버프)
        # 거리 500 이상이면 1.0, 그 미만이면 (거리/500) 비율
        ratio = min(1.0, current_range / 500.0)
```
그 외(`is_buff_active` +100, `modifier = ratio * 0.10`, 스탯 AD55/크리25%/2800G)는 불변.

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_c44_range.py -v`
Expected: 4 passed.

- [ ] **Step 5: 커밋**

```bash
git add tests/test_c44_range.py adc_sim/items.py
git commit -m "fix(items): C44 확대 증폭 최대거리 600→500 (26.13 버프, 사용자 툴팁 확인)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: 코그모 후보 풀 상수 추출 + c44 1~4코어 편입

**Files:**
- Modify: `adc_sim/simulations/cogmaw.py` (모듈 상수 추가: `CONTROL_PATH`(69행) 아래; 후보 리스트 교체: `get_cogmaw_4core_top1_build` 내 84~87행, `__main__` 내 362~365행; `item_short`(369~375행)에 c44 라벨)
- Test: `tests/test_cogmaw_pkg_compare.py` (신규 — 이 태스크에서는 풀 검증 테스트만; Task 3이 같은 파일에 헬퍼 테스트 추가)

**Interfaces:**
- Consumes: 없음 (독립)
- Produces: `COGMAW_CORE_CANDIDATES: dict[int, list[str]]` (키 1~4) — cogmaw.py 모듈 상수. Task 3 테스트 파일이 동일 파일에 공존.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_cogmaw_pkg_compare.py` 생성:

```python
"""코그모 후보 풀 상수 + 패키지 A/B 비교 헬퍼 테스트."""


def test_cogmaw_pool_contains_c44_all_tiers():
    from adc_sim.simulations.cogmaw import COGMAW_CORE_CANDIDATES
    for tier in (1, 2, 3, 4):
        assert "c44" in COGMAW_CORE_CANDIDATES[tier], f"c44 missing in tier {tier}"
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_cogmaw_pkg_compare.py -v`
Expected: FAIL — `ImportError: cannot import name 'COGMAW_CORE_CANDIDATES'`.

- [ ] **Step 3: 구현** — `adc_sim/simulations/cogmaw.py`:

(a) `CONTROL_PATH = ("guinsoo", "navori", "terminus", "wit")` 정의(69행) 바로 아래에 모듈 상수 추가:

```python
# 후보 풀(1~4코어) — get_cogmaw_4core_top1_build 와 __main__ 이 공유(중복 하드코딩 제거).
# c44: 26.13 버프(500거리부터 최대 10% 증폭)로 풀 편입 [spec 2026-07-05]. 관통 배타와 무관.
COGMAW_CORE_CANDIDATES = {
    1: ["guinsoo", "kraken", "nashor", "terminus", "bot", "rfc", "statikk", "storm", "pd", "ie", "yuntal", "shadowflame", "dawn", "navori", "wit", "c44"],
    2: ["guinsoo", "kraken", "nashor", "terminus", "bot", "rfc", "statikk", "storm", "pd", "ie", "yuntal", "shadowflame", "void", "dawn", "navori", "wit", "c44"],
    3: ["guinsoo", "nashor", "terminus", "bot", "kraken", "rfc", "pd", "ie", "ldr", "rabadon", "shadowflame", "void", "dawn", "navori", "wit", "c44"],
    4: ["nashor", "rabadon", "shadowflame", "ie", "ldr", "mortal", "terminus", "bot", "guinsoo", "kraken", "pd", "void", "dawn", "navori", "wit", "c44"],
}
```

(b) `get_cogmaw_4core_top1_build` 내부(84~87행)의 4줄:

```python
    core1_candidates = ["guinsoo", "kraken", "nashor", "terminus", "bot", "rfc", "statikk", "storm", "pd", "ie", "yuntal", "shadowflame", "dawn", "navori", "wit"]
    core2_candidates = ["guinsoo", "kraken", "nashor", "terminus", "bot", "rfc", "statikk", "storm", "pd", "ie", "yuntal", "shadowflame", "void", "dawn", "navori", "wit"]
    core3_candidates = ["guinsoo", "nashor", "terminus", "bot", "kraken", "rfc", "pd", "ie", "ldr", "rabadon", "shadowflame", "void", "dawn", "navori", "wit"]
    core4_candidates = ["nashor", "rabadon", "shadowflame", "ie", "ldr", "mortal", "terminus", "bot", "guinsoo", "kraken", "pd", "void", "dawn", "navori", "wit"]
```
→
```python
    core1_candidates = COGMAW_CORE_CANDIDATES[1]
    core2_candidates = COGMAW_CORE_CANDIDATES[2]
    core3_candidates = COGMAW_CORE_CANDIDATES[3]
    core4_candidates = COGMAW_CORE_CANDIDATES[4]
```

(c) `__main__`(362~365행)의 동일한 4줄도 위와 똑같은 4줄로 교체 (리스트 리터럴 → 상수 참조).

(d) `item_short` dict(369~375행)에 항목 추가 — `"navori": "Navori", "wit": "Wit's",` 줄을:

```python
        "navori": "Navori", "wit": "Wit's", "c44": "C44",
```

- [ ] **Step 4: 통과 확인 (풀 테스트 + 기존 랭킹 형태 테스트)**

Run: `.venv/bin/python -m pytest tests/test_cogmaw_pkg_compare.py tests/test_cogmaw_ranking.py -v`
Expected: 2 passed (test_cogmaw_ranking은 top1 전수조사를 돌려 느림 — 수 분 허용).

- [ ] **Step 5: 커밋**

```bash
git add tests/test_cogmaw_pkg_compare.py adc_sim/simulations/cogmaw.py
git commit -m "feat(cogmaw): 후보 풀 COGMAW_CORE_CANDIDATES 중앙화 + c44 1~4코어 편입

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: 패키지 A/B RelDPG 비교표

**Files:**
- Modify: `adc_sim/simulations/cogmaw.py` (모듈 함수 `_build_pkg_compare_rows` 추가: `_run_cogmaw_ranking` 정의 바로 위; 비교표 출력: `_run_cogmaw_ranking` 끝 `return ranked` 직전)
- Test: `tests/test_cogmaw_pkg_compare.py` (Task 2 파일에 추가)

**Interfaces:**
- Consumes: `_run_cogmaw_ranking` 로컬 변수 `rows`(pre-dedup 전 행: dict에 `path`/`pkg_label`/`dpg` 포함), `baseline_dpg_4`, `core_weights`, `ranked`, `control_rows`, `item_short`, `col_build`, `trim_text`; `ADC_PACKAGES`(이미 import됨, A=라벨 "Bld+Zerk", B=라벨 "Bow+Glut" 순서)
- Produces: `_build_pkg_compare_rows(rows, target_paths, baseline_dpg_4, core_weights) -> list[dict]` — 각 dict: `{"path": tuple, "scores": {pkg_label: float}, "delta_b_minus_a": float, "winner": str}`. 대상 순서 유지, 한쪽 패키지 행이 없는 path는 건너뜀.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_cogmaw_pkg_compare.py`에 아래를 추가:

```python
from adc_sim.simulations.cogmaw import _build_pkg_compare_rows


def _row(path, pkg_label, dpg):
    return {"path": path, "pkg_label": pkg_label, "dpg": dpg}


BASELINE = [100.0, 100.0, 100.0, 100.0]
WEIGHTS = [0.25, 0.25, 0.25, 0.25]


def test_pkg_compare_pairs_scores_delta_winner():
    rows = [
        _row(("a", "b", "c", "d"), "Bld+Zerk", [100.0, 100.0, 100.0, 100.0]),
        _row(("a", "b", "c", "d"), "Bow+Glut", [110.0, 110.0, 110.0, 110.0]),
    ]
    out = _build_pkg_compare_rows(rows, [("a", "b", "c", "d")], BASELINE, WEIGHTS)
    assert len(out) == 1
    row = out[0]
    assert abs(row["scores"]["Bld+Zerk"] - 100.0) < 1e-9
    assert abs(row["scores"]["Bow+Glut"] - 110.0) < 1e-9
    assert abs(row["delta_b_minus_a"] - 10.0) < 1e-9
    assert row["winner"] == "Bow+Glut"


def test_pkg_compare_winner_a_and_target_order_kept():
    rows = [
        _row(("a", "b", "c", "d"), "Bld+Zerk", [120.0] * 4),
        _row(("a", "b", "c", "d"), "Bow+Glut", [100.0] * 4),
        _row(("e", "f", "g", "h"), "Bld+Zerk", [90.0] * 4),
        _row(("e", "f", "g", "h"), "Bow+Glut", [95.0] * 4),
    ]
    out = _build_pkg_compare_rows(
        rows, [("e", "f", "g", "h"), ("a", "b", "c", "d")], BASELINE, WEIGHTS)
    assert [r["path"] for r in out] == [("e", "f", "g", "h"), ("a", "b", "c", "d")]
    assert out[1]["winner"] == "Bld+Zerk"
    assert abs(out[0]["delta_b_minus_a"] - 5.0) < 1e-9


def test_pkg_compare_skips_path_missing_a_package():
    rows = [_row(("a", "b", "c", "d"), "Bld+Zerk", [100.0] * 4)]
    out = _build_pkg_compare_rows(rows, [("a", "b", "c", "d")], BASELINE, WEIGHTS)
    assert out == []
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_cogmaw_pkg_compare.py -v`
Expected: FAIL — `ImportError: cannot import name '_build_pkg_compare_rows'` (기존 풀 테스트도 import 에러로 함께 실패 — 정상).

- [ ] **Step 3: 구현(1/2)** — `adc_sim/simulations/cogmaw.py`의 `def _run_cogmaw_ranking(...)` 정의 바로 위에 모듈 함수 추가:

```python
def _build_pkg_compare_rows(rows, target_paths, baseline_dpg_4, core_weights):
    """상위 빌드들의 패키지 A/B rel-DPG 비교 행 구성 — print 와 분리한 순수 함수(테스트용).

    rows: pre-dedup 전 행(빌드×패키지, dict 에 path/pkg_label/dpg 필요).
    target_paths: 비교 대상 path 튜플 리스트(순서 유지). 한쪽 패키지가 없는 path 는 건너뜀.
    반환: [{"path", "scores": {pkg_label: rel_dpg_score}, "delta_b_minus_a", "winner"}]
    """
    by_path = {}
    for r in rows:
        by_path.setdefault(tuple(r["path"]), {})[r["pkg_label"]] = r
    labels = [p["label"] for p in ADC_PACKAGES]
    out = []
    for path in target_paths:
        pkg_rows = by_path.get(tuple(path), {})
        scores = {}
        for label in labels:
            r = pkg_rows.get(label)
            if r is None:
                continue
            core_rel = [
                (r["dpg"][i] / baseline_dpg_4[i] * 100.0 if baseline_dpg_4[i] > 0 else 0.0)
                for i in range(4)
            ]
            scores[label] = sum(core_weights[i] * core_rel[i] for i in range(4))
        if len(scores) < len(labels):
            continue
        a_label, b_label = labels[0], labels[1]
        delta = scores[b_label] - scores[a_label]
        out.append({
            "path": tuple(path),
            "scores": scores,
            "delta_b_minus_a": delta,
            "winner": b_label if delta > 0 else a_label,
        })
    return out
```

- [ ] **Step 4: 구현(2/2)** — `_run_cogmaw_ranking` 끝, 랭킹 표 print 루프(`for rank, r in enumerate(output_rows, ...)` 블록) 다음이자 `return ranked` 바로 앞에 삽입:

```python
    # ── 패키지 A/B 비교표: 상위 10 + 컨트롤, 동일 baseline·재시뮬 없음 [spec 2026-07-05] ──
    compare_targets = [tuple(r["path"]) for r in ranked[:10]]
    for cr in control_rows:
        if tuple(cr["path"]) not in compare_targets:
            compare_targets.append(tuple(cr["path"]))
    pkg_cmp = _build_pkg_compare_rows(rows, compare_targets, baseline_dpg_4, core_weights)
    a_label, b_label = ADC_PACKAGES[0]["label"], ADC_PACKAGES[1]["label"]
    print(
        f"\nPackage A({a_label}=도란검+광전사+핏빛길) vs B({b_label}=도란활+피흡신발+민첩함)"
        f" — RelDPG, top {min(10, len(ranked))} builds + control"
    )
    cmp_hdr = (
        f"{'BUILD(4C)':<{col_build}} | {'A '+a_label:>12} | {'B '+b_label:>12} | "
        f"{'Δ(B-A)':>8} | 우세"
    )
    print(cmp_hdr)
    print("-" * len(cmp_hdr))
    for row in pkg_cmp:
        p = row["path"]
        s = item_short
        lbl = trim_text(f"{s.get(p[0], p[0])}-{s.get(p[1], p[1])}-{s.get(p[2], p[2])}-{s.get(p[3], p[3])}", col_build)
        print(
            f"{lbl:<{col_build}} | {row['scores'][a_label]:>12.2f} | {row['scores'][b_label]:>12.2f} | "
            f"{row['delta_b_minus_a']:>+8.2f} | {row['winner']}"
        )
```

- [ ] **Step 5: 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_cogmaw_pkg_compare.py -v`
Expected: 4 passed (풀 테스트 1 + 헬퍼 테스트 3).

- [ ] **Step 6: 커밋**

```bash
git add tests/test_cogmaw_pkg_compare.py adc_sim/simulations/cogmaw.py
git commit -m "feat(cogmaw): 패키지 A/B RelDPG 비교표(상위10+컨트롤) 룬별 출력

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: 통합 검증 + CLAUDE.md 갱신

**Files:**
- Modify: `CLAUDE.md` (코그모 섹션 "전용 sim" 항목)
- 검증 실행만: `tests/` 전체, `adc_sim.simulations.cogmaw` 헤드리스 실행

**Interfaces:**
- Consumes: Task 1~3 결과 전부
- Produces: 없음 (검증·문서)

- [ ] **Step 1: 전체 테스트 스위트**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: **82 passed** (기존 74 + Task1 4개 + Task2/3 4개), 실패 0. 특히 `test_regression_diff` 통과 = C44 버프가 5챔프 대표 빌드(비-c44)에 무영향 확인.

- [ ] **Step 2: 코그모 시뮬 헤드리스 실행 (수동 검증)**

Run: `MPLBACKEND=Agg .venv/bin/python -m adc_sim.simulations.cogmaw 2>&1 | tail -60`
Expected: 룬 2개(치명적 속도/집중공격) 각각 — 랭킹 표 뒤에 "Package A(...) vs B(...)" 비교표 출력, 경로 수가 기존 대비 증가(c44 편입), 에러 없음. 상위권에 c44 포함 빌드 등장 여부를 확인해 결과 요약에 기록(등장 안 해도 실패 아님 — 랭킹은 모델 결과).

- [ ] **Step 3: CLAUDE.md 코그모 섹션 갱신** — "### Cog'Maw" 섹션의 "**전용 sim**" 불릿에서:

기존 텍스트 중 `**황혼과 새벽(`dawn`)·나보리(`navori`)·마법사의최후(`wit`) 1~4코어 전부**).` 부분을 다음으로 교체:

```
**황혼과 새벽(`dawn`)·나보리(`navori`)·마법사의최후(`wit`)·**C44(`c44`)** 1~4코어 전부**; c44는 26.13 버프(확대: 500거리부터 최대 10% 증폭, `items.py` 반영) 편입). 후보 풀은 `COGMAW_CORE_CANDIDATES` 상수로 중앙화(top1·`__main__` 공유). 랭킹 표 뒤에 **패키지 A/B(도란검+광전사+핏빛길 vs 도란활+피흡신발+민첩함) RelDPG 비교표**(상위 10+컨트롤)를 룬별로 출력.
```

- [ ] **Step 4: 커밋**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md 코그모 섹션 c44 편입·풀 상수·A/B 비교표 반영

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: [CTRL2] 고정 레퍼런스 행 — c44-pd-ldr-ie (사용자 추가 요청)

**Files:**
- Modify: `adc_sim/simulations/cogmaw.py` (`CONTROL_PATH` 아래 상수 1개; `_run_cogmaw_ranking` 내부 5곳)
- Modify: `CLAUDE.md` (코그모 "전용 sim" 불릿 끝에 한 구절 추가)
- Test: `tests/test_cogmaw_pkg_compare.py` (테스트 1개 추가)

**Interfaces:**
- Consumes: Task 2의 `COGMAW_CORE_CANDIDATES`, Task 3의 A/B 비교표 블록(`control_rows + ...` 대상 목록), `_run_cogmaw_ranking` 로컬 `rows`/`rows_dedup`/`dedupe_best`/`top_row_paths`/`output_rows`/`ctrl_tag`.
- Produces: 모듈 상수 `CONTROL2_PATH: tuple[str, str, str, str]`, row dict 키 `"is_control2": bool` (해당 함수 내 전 행 보유).

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_cogmaw_pkg_compare.py`에 추가:

```python
def test_control2_path_is_legal_in_pools():
    from adc_sim.simulations.cogmaw import CONTROL2_PATH, COGMAW_CORE_CANDIDATES
    assert CONTROL2_PATH == ("c44", "pd", "ldr", "ie")
    assert len(set(CONTROL2_PATH)) == 4
    for tier, key in enumerate(CONTROL2_PATH, start=1):
        assert key in COGMAW_CORE_CANDIDATES[tier], f"{key} not in tier {tier}"
    pen_exclusive = {"terminus", "ldr", "mortal"}
    assert sum(1 for k in CONTROL2_PATH if k in pen_exclusive) <= 1
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_cogmaw_pkg_compare.py -v`
Expected: FAIL — `ImportError: cannot import name 'CONTROL2_PATH'` (신규 테스트만; 기존 테스트는 import 위치가 함수 내부라 영향 없음 — 만약 파일 전체가 죽으면 신규 테스트의 import를 함수 안에 둔 위 코드 그대로인지 확인).

- [ ] **Step 3: 구현** — `adc_sim/simulations/cogmaw.py`:

(a) `CONTROL_PATH = ("guinsoo", "navori", "terminus", "wit")` 바로 아래에 추가:

```python
# 표시 전용 고정 레퍼런스(크리 빌드) — baseline 아님, 랭킹 표에 [CTRL2]로 항상 표시 [사용자 요청 2026-07-05]
CONTROL2_PATH = ("c44", "pd", "ldr", "ie")
```

(b) `_run_cogmaw_ranking` 상단, `rows = []` 직전에 추가:

```python
    ctrl2_combo = tuple(sorted(CONTROL2_PATH))
```

(c) 같은 함수 rows.append dict의 `"is_control": ...` 줄 바로 아래에 추가:

```python
                "is_control2": tuple(sorted(path)) == ctrl2_combo,
```

(d) canonical 고정 블록 —

```python
    rows_dedup = [r for r in rows_dedup if not r["is_control"]]
    ctrl_cands = [r for r in rows if tuple(r["path"]) == CONTROL_PATH]
    if ctrl_cands:
        rows_dedup.append(max(ctrl_cands, key=lambda r: r["dedupe_eff"]))
```
→
```python
    rows_dedup = [r for r in rows_dedup if not (r["is_control"] or r["is_control2"])]
    ctrl_cands = [r for r in rows if tuple(r["path"]) == CONTROL_PATH]
    if ctrl_cands:
        rows_dedup.append(max(ctrl_cands, key=lambda r: r["dedupe_eff"]))
    ctrl2_cands = [r for r in rows if tuple(r["path"]) == CONTROL2_PATH]
    if ctrl2_cands:  # baseline 아님 → 없으면 조용히 생략(RuntimeError 없음)
        rows_dedup.append(max(ctrl2_cands, key=lambda r: r["dedupe_eff"]))
```

(e) 출력 행 구성 —

```python
    extra_controls = [r for r in control_rows if tuple(r["path"]) not in top_row_paths]
```
→
```python
    control2_rows = [r for r in rows_dedup if r["is_control2"]]
    extra_controls = [r for r in control_rows + control2_rows if tuple(r["path"]) not in top_row_paths]
```

(f) 태그·칼럼 폭 — 헤더의 `{'CTRL':>6}` → `{'CTRL':>7}`, 행의

```python
        ctrl_tag = "[CTRL]" if r["is_control"] else ""
```
→
```python
        ctrl_tag = "[CTRL]" if r["is_control"] else ("[CTRL2]" if r["is_control2"] else "")
```
그리고 같은 print의 `{ctrl_tag:>6}` → `{ctrl_tag:>7}`.

(g) A/B 비교표 대상 — Task 3이 넣은

```python
    for cr in control_rows:
```
→
```python
    for cr in control_rows + control2_rows:
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_cogmaw_pkg_compare.py tests/test_cogmaw_ranking.py -v`
Expected: 6 passed (신규 1 포함; 랭킹 테스트는 전수조사라 수 분).

- [ ] **Step 5: CLAUDE.md** — 코그모 "전용 sim" 불릿의 A/B 비교표 문장 끝에 추가:

```
크리 레퍼런스 `[CTRL2]`=c44-pd-ldr-ie(표시 전용, baseline 아님)도 표·A/B 비교에 항상 표시.
```

- [ ] **Step 6: 커밋**

```bash
git add tests/test_cogmaw_pkg_compare.py adc_sim/simulations/cogmaw.py CLAUDE.md
git commit -m "feat(cogmaw): [CTRL2] 크리 레퍼런스 행(c44-pd-ldr-ie) 표·A/B 비교 고정 표시

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
