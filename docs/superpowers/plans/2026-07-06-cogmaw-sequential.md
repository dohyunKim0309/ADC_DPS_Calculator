# Cog'Maw 순차 최적 빌드 탐색 (미래 할인 DP) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 매 코어 시점에서 "다음 아이템"을 미래 코어 파워의 γ-할인합으로 선택하는 순차 최적화 모듈(`cogmaw_sequential.py`)을 코그모 파일럿으로 구현한다.

**Architecture:** 상태 = 보유 아이템 frozenset. 순수 DP 코어(주입식 power 함수·후보맵 — 시뮬 없이 테스트 가능) + 시뮬 캐시 레이어((집합,티어,패키지,룬) 메모) + 출력 레이어(궤적·분기점 대안 top3·[CTRL]/[CTRL2] 비교). 기존 cogmaw.py 불변, import 재사용.

**Tech Stack:** Python 3.10 (`.venv`), pytest. 스펙: `docs/superpowers/specs/2026-07-06-cogmaw-sequential-ranking-design.md`

## Global Constraints

- 인터프리터는 항상 `.venv/bin/python`, repo 루트에서 `-m` 실행.
- γ=0.9 기본(파라미터화). 호라이즌 5코어. 지표 DPS·DPG 각각 별도 DP.
- 슬롯 1~4 후보 = `COGMAW_CORE_CANDIDATES[slot]`, 슬롯 5 = 1~4티어 합집합. 방관 배타 `{terminus, ldr, mortal}` ≤ 1.
- 기존 파일(`cogmaw.py`/`champion.py` 등) 무변경 — 신규 모듈 + 신규 테스트 + CLAUDE.md 한 단락만.
- 기존 가중 랭킹 top1 비교행은 **옵션 플래그(`--with-top1`, 기본 off)** — 스펙의 비교행 요구를 런타임 이유로 완화(스펙에 주석 반영됨).
- 커밋: 한국어 conventional + 트레일러 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`. 브랜치 feat/cogmaw-c44.

---

### Task 1: DP 코어 (순수 로직, 시뮬 무의존)

**Files:**
- Create: `adc_sim/simulations/cogmaw_sequential.py`
- Test: `tests/test_cogmaw_sequential.py` (신규)

**Interfaces:**
- Produces (Task 2~3 이 사용):
  - `GAMMA = 0.9`, `HORIZON = 5`, `PEN_EXCLUSIVE = {"terminus", "ldr", "mortal"}`
  - `SLOT5_CANDIDATES: list[str]` (1~4티어 합집합, sorted)
  - `default_candidates_map() -> dict[int, list[str]]` (1~5 슬롯별 후보)
  - `legal_next_items(owned: frozenset, slot: int, candidates_map) -> list[str]`
  - `solve_sequential(power, gamma=GAMMA, horizon=HORIZON, candidates_map=None) -> (W: dict[frozenset,float], best: dict[frozenset,str|None])` — `power(frozenset)->float`
  - `extract_trajectory(best) -> list[str]` (∅부터 best 체인 따라 아이템 순서)
  - `node_alternatives(state, W, power, gamma, candidates_map, top_n=3) -> list[(item, value)]`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_cogmaw_sequential.py` 생성:

```python
"""순차 최적화 DP 코어 테스트 — 주입식 power/후보맵, 시뮬 무의존."""
from adc_sim.simulations.cogmaw_sequential import (
    legal_next_items, solve_sequential, extract_trajectory, node_alternatives,
    default_candidates_map, SLOT5_CANDIDATES, PEN_EXCLUSIVE,
)

# 수계산 합성 사례: horizon=2, γ=0.5
CANDS = {1: ["a", "b"], 2: ["a", "b", "c"]}
POWERS = {
    frozenset({"a"}): 10.0, frozenset({"b"}): 8.0,
    frozenset({"a", "b"}): 20.0, frozenset({"a", "c"}): 30.0,
    frozenset({"b", "c"}): 5.0,
}


def _power(state):
    return POWERS[state]


def test_dp_matches_hand_computation():
    W, best = solve_sequential(_power, gamma=0.5, horizon=2, candidates_map=CANDS)
    # W({a}) = max(0.5*20, 0.5*30) = 15 (best=c) ; W({b}) = max(0.5*20, 0.5*5) = 10 (best=a)
    assert abs(W[frozenset({"a"})] - 15.0) < 1e-9
    assert best[frozenset({"a"})] == "c"
    assert abs(W[frozenset({"b"})] - 10.0) < 1e-9
    assert best[frozenset({"b"})] == "a"
    # W(∅) = max(0.5*(10+15), 0.5*(8+10)) = 12.5 (best=a)
    assert abs(W[frozenset()] - 12.5) < 1e-9
    assert best[frozenset()] == "a"


def test_trajectory_follows_best_chain():
    _, best = solve_sequential(_power, gamma=0.5, horizon=2, candidates_map=CANDS)
    assert extract_trajectory(best) == ["a", "c"]


def test_node_alternatives_ranked():
    W, _ = solve_sequential(_power, gamma=0.5, horizon=2, candidates_map=CANDS)
    alts = node_alternatives(frozenset(), W, _power, 0.5, CANDS, top_n=3)
    assert [a[0] for a in alts] == ["a", "b"]
    assert abs(alts[0][1] - 12.5) < 1e-9 and abs(alts[1][1] - 9.0) < 1e-9


def test_legal_next_items_pen_exclusive_and_dup():
    cands = {2: ["terminus", "ldr", "guinsoo", "nashor"]}
    owned = frozenset({"ldr"})
    out = legal_next_items(owned, 2, cands)
    assert "terminus" not in out and "ldr" not in out
    assert set(out) == {"guinsoo", "nashor"}


def test_default_candidates_map_shape():
    m = default_candidates_map()
    assert set(m.keys()) == {1, 2, 3, 4, 5}
    assert m[5] == SLOT5_CANDIDATES and "c44" in m[1]
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_cogmaw_sequential.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adc_sim.simulations.cogmaw_sequential'`.

- [ ] **Step 3: 구현** — `adc_sim/simulations/cogmaw_sequential.py` 생성:

```python
"""코그모 순차 최적 빌드 탐색 — 미래 할인 DP (γ=0.9).

기존 랭킹(완성 경로 일괄 가중)과 달리, j코어 상태에서 "다음 아이템"을
j+1~5코어 파워의 γ-할인합 최대화로 선택한다(사용자 제안 방법론).
spec: docs/superpowers/specs/2026-07-06-cogmaw-sequential-ranking-design.md
실행: .venv/bin/python -m adc_sim.simulations.cogmaw_sequential  (표만 출력, 헤드리스 안전)
"""
from adc_sim.simulations.cogmaw import (
    COGMAW_CORE_CANDIDATES, CONTROL_PATH, CONTROL2_PATH, simulate_cogmaw_core_path,
)
from adc_sim.data.items_data import ADC_PACKAGES
from adc_sim.runes import LethalTempo, PressTheAttack

GAMMA = 0.9
HORIZON = 5
PEN_EXCLUSIVE = {"terminus", "ldr", "mortal"}
# 슬롯5 전용 후보 리스트가 없어 1~4티어 합집합 사용(스펙 승인, 추후 조정 지점).
SLOT5_CANDIDATES = sorted(set().union(*COGMAW_CORE_CANDIDATES.values()))


def default_candidates_map():
    m = {slot: list(COGMAW_CORE_CANDIDATES[slot]) for slot in (1, 2, 3, 4)}
    m[5] = list(SLOT5_CANDIDATES)
    return m


def legal_next_items(owned, slot, candidates_map):
    pen_owned = sum(1 for k in owned if k in PEN_EXCLUSIVE)
    out = []
    for k in candidates_map[slot]:
        if k in owned:
            continue
        if k in PEN_EXCLUSIVE and pen_owned >= 1:
            continue
        out.append(k)
    return out


def solve_sequential(power, gamma=GAMMA, horizon=HORIZON, candidates_map=None):
    """W(S) = max_x γ·(power(S∪x) + W(S∪x)); |S|=horizon 에서 W=0.

    power: frozenset -> float (해당 집합 완성 시점 = |집합| 코어의 파워).
    반환 (W, best): 상태별 할인합 가치와 최적 다음 아이템(터미널은 None).
    """
    if candidates_map is None:
        candidates_map = default_candidates_map()
    W, best = {}, {}

    def w(state):
        if state in W:
            return W[state]
        j = len(state)
        if j >= horizon:
            W[state], best[state] = 0.0, None
            return 0.0
        best_val, best_item = None, None
        for x in legal_next_items(state, j + 1, candidates_map):
            nxt = state | {x}
            val = gamma * (power(nxt) + w(nxt))
            if best_val is None or val > best_val:
                best_val, best_item = val, x
        if best_val is None:  # 후보 소진(방관 배타 등) — 조기 종단
            best_val = 0.0
        W[state], best[state] = best_val, best_item
        return best_val

    w(frozenset())
    return W, best


def extract_trajectory(best):
    state, path = frozenset(), []
    while best.get(state):
        x = best[state]
        path.append(x)
        state = state | {x}
    return path


def node_alternatives(state, W, power, gamma, candidates_map, top_n=3):
    """분기점 대안: 후보 x별 γ·(power+W) 값 상위 top_n. (W dict 재사용, 재시뮬 없음)"""
    vals = []
    for x in legal_next_items(state, len(state) + 1, candidates_map):
        nxt = state | {x}
        vals.append((x, gamma * (power(nxt) + W[nxt])))
    vals.sort(key=lambda t: t[1], reverse=True)
    return vals[:top_n]
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_cogmaw_sequential.py -v`
Expected: 5 passed.

- [ ] **Step 5: 커밋**

```bash
git add tests/test_cogmaw_sequential.py adc_sim/simulations/cogmaw_sequential.py
git commit -m "feat(cogmaw): 순차 최적화 DP 코어(γ-할인 가치·궤적·대안, 주입식 power)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: 시뮬 파워 캐시 + 지표 어댑터

**Files:**
- Modify: `adc_sim/simulations/cogmaw_sequential.py` (클래스 추가)
- Test: `tests/test_cogmaw_sequential.py` (테스트 2개 추가)

**Interfaces:**
- Consumes: Task 1 전부, `simulate_cogmaw_core_path`(cogmaw.py — 시그니처 `(full_path, core_tier, doran_key, boots_key, rune_as_bonus, keystone_cls)` → `(dps, total_cost)`)
- Produces: `PowerCache(pkg: dict, keystone_cls)` — 메서드 `dps_gold(state) -> (float, float)`(메모), `dps(state) -> float`, `dpg(state) -> float`, 속성 `sim_calls: int`(캐시미스 카운터), `sim_fn`(테스트 주입용, 기본 `simulate_cogmaw_core_path`).

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_cogmaw_sequential.py`에 추가:

```python
from adc_sim.simulations.cogmaw_sequential import PowerCache


def _fake_sim(full_path, core_tier, doran_key=None, boots_key=None,
              rune_as_bonus=0.0, keystone_cls=None):
    return 100.0 * core_tier, 1000.0 * core_tier


def test_power_cache_memoizes_and_computes_dpg():
    pkg = {"doran": "doranblade", "boots": "berserker", "rune_as": 0.0, "label": "T"}
    pc = PowerCache(pkg, keystone_cls=None, sim_fn=_fake_sim)
    s2 = frozenset({"a", "b"})
    assert abs(pc.dps(s2) - 200.0) < 1e-9
    assert abs(pc.dpg(s2) - 100.0) < 1e-9      # 200 / (2000/1000)
    assert pc.sim_calls == 1                    # dps→dpg 재호출에도 시뮬 1회
    pc.dps(s2)
    assert pc.sim_calls == 1


def test_power_cache_passes_sorted_tuple_and_tier():
    seen = {}

    def spy(full_path, core_tier, **kw):
        seen["path"], seen["tier"] = full_path, core_tier
        return 1.0, 1.0

    pkg = {"doran": "doranblade", "boots": "berserker", "rune_as": 0.0, "label": "T"}
    pc = PowerCache(pkg, keystone_cls=None, sim_fn=spy)
    pc.dps(frozenset({"b", "a", "c"}))
    assert seen["path"] == ("a", "b", "c") and seen["tier"] == 3
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_cogmaw_sequential.py -v`
Expected: 신규 2개 FAIL — `ImportError: cannot import name 'PowerCache'`.

- [ ] **Step 3: 구현** — `cogmaw_sequential.py`에 추가 (Task 1 함수들 아래):

```python
class PowerCache:
    """(집합) → (dps, gold) 메모 — 패키지·룬 고정. DPS/DPG DP 가 같은 캐시 공유."""

    def __init__(self, pkg, keystone_cls, sim_fn=simulate_cogmaw_core_path):
        self.pkg = pkg
        self.keystone_cls = keystone_cls
        self.sim_fn = sim_fn
        self.cache = {}
        self.sim_calls = 0

    def dps_gold(self, state):
        if state not in self.cache:
            self.sim_calls += 1
            kw = dict(doran_key=self.pkg["doran"], boots_key=self.pkg["boots"],
                      rune_as_bonus=self.pkg["rune_as"])
            if self.keystone_cls is not None:
                kw["keystone_cls"] = self.keystone_cls
            self.cache[state] = self.sim_fn(tuple(sorted(state)), len(state), **kw)
        return self.cache[state]

    def dps(self, state):
        return self.dps_gold(state)[0]

    def dpg(self, state):
        d, g = self.dps_gold(state)
        return d / (g / 1000.0) if g > 0 else 0.0
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_cogmaw_sequential.py -v`
Expected: 7 passed.

- [ ] **Step 5: 커밋**

```bash
git add tests/test_cogmaw_sequential.py adc_sim/simulations/cogmaw_sequential.py
git commit -m "feat(cogmaw): 순차 최적화 시뮬 파워 캐시(집합 메모·DPS/DPG 공유)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: 궤적 실행기 + 출력 + `__main__` + CLAUDE.md

**Files:**
- Modify: `adc_sim/simulations/cogmaw_sequential.py` (실행/출력 함수 + `__main__`)
- Modify: `CLAUDE.md` (코그모 섹션 아래 새 문단 1개)
- Test: `tests/test_cogmaw_sequential.py` (축소풀 end-to-end 1개 추가)

**Interfaces:**
- Consumes: Task 1·2 전부, `CONTROL_PATH`/`CONTROL2_PATH`, `ADC_PACKAGES`, `LethalTempo`/`PressTheAttack`
- Produces: `run_scenario(keystone_cls, pkg, metric, candidates_map=None, gamma=GAMMA) -> dict`
  (키: `trajectory`(list[str]), `steps`(코어별 dict: item/dps/dpg/gold/W), `alternatives`(스텝별 top3), `W0`),
  `evaluate_fixed_path(path, cache, metric, W, gamma=GAMMA, candidates_map=None) -> float`(고정 경로 할인합; 4아이템 경로면 잔여 슬롯은 W로 최적 연속), `print_scenario(...)`, `main(with_top1=False)`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_cogmaw_sequential.py`에 추가:

```python
def test_run_scenario_reduced_pool_end_to_end():
    """실제 시뮬로 축소풀(3슬롯) end-to-end — 궤적 합법성과 필드 형태 검증."""
    from adc_sim.simulations.cogmaw_sequential import run_scenario
    from adc_sim.runes import LethalTempo
    from adc_sim.data.items_data import ADC_PACKAGES
    small = {1: ["guinsoo", "kraken"], 2: ["guinsoo", "kraken", "nashor"],
             3: ["nashor", "terminus", "ldr"]}
    out = run_scenario(LethalTempo, ADC_PACKAGES[1], "dpg",
                       candidates_map=small, horizon=3)
    traj = out["trajectory"]
    assert len(traj) == 3 and len(set(traj)) == 3
    assert sum(1 for k in traj if k in {"terminus", "ldr", "mortal"}) <= 1
    assert len(out["steps"]) == 3
    for step in out["steps"]:
        assert step["dps"] > 0 and step["gold"] > 0
    assert len(out["alternatives"]) == 3
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_cogmaw_sequential.py::test_run_scenario_reduced_pool_end_to_end -v`
Expected: FAIL — `ImportError: cannot import name 'run_scenario'`.

- [ ] **Step 3: 구현** — `cogmaw_sequential.py`에 추가:

```python
def run_scenario(keystone_cls, pkg, metric, candidates_map=None, gamma=GAMMA,
                 horizon=HORIZON, cache=None):
    """룬×패키지×지표 1조합의 최적 궤적 계산. cache 를 넘기면 시뮬 캐시 공유(지표 간)."""
    if candidates_map is None:
        candidates_map = default_candidates_map()
    if cache is None:
        cache = PowerCache(pkg, keystone_cls)
    metric_fn = cache.dpg if metric == "dpg" else cache.dps
    W, best = solve_sequential(metric_fn, gamma=gamma, horizon=horizon,
                               candidates_map=candidates_map)
    traj = extract_trajectory(best)
    steps, alts, state = [], [], frozenset()
    for x in traj:
        alts.append(node_alternatives(state, W, metric_fn, gamma, candidates_map))
        state = state | {x}
        dps, gold = cache.dps_gold(state)
        steps.append({"item": x, "core": len(state), "dps": dps,
                      "dpg": dps / (gold / 1000.0) if gold > 0 else 0.0,
                      "gold": gold, "W": W[state]})
    return {"trajectory": traj, "steps": steps, "alternatives": alts,
            "W0": W[frozenset()], "W": W, "cache": cache}


def evaluate_fixed_path(path, cache, metric, W, gamma=GAMMA, candidates_map=None):
    """고정 구매 순서(4~5아이템)의 0코어 기준 할인합. 4아이템이면 잔여 슬롯은 W로 최적 연속."""
    if candidates_map is None:
        candidates_map = default_candidates_map()
    metric_fn = cache.dpg if metric == "dpg" else cache.dps
    total, state = 0.0, frozenset()
    for k, x in enumerate(path, start=1):
        state = state | {x}
        total += (gamma ** k) * metric_fn(state)
    if len(path) < HORIZON and state in W:
        total += (gamma ** len(path)) * W[state]
    return total


def print_scenario(title, out, ctrl_rows):
    print(f"\n=== {title} (γ={GAMMA}, horizon {HORIZON}core) ===")
    print(f"W(0core 할인합) = {out['W0']:.2f}")
    for i, step in enumerate(out["steps"]):
        alt_txt = " / ".join(f"{a}:{v:.1f}" for a, v in out["alternatives"][i])
        print(f"  {step['core']}core → {step['item']:<12} | DPS {step['dps']:>7.1f} | "
              f"DPG {step['dpg']:>7.2f} | Gold {step['gold']:>5.0f} | 대안: {alt_txt}")
    for name, val in ctrl_rows:
        print(f"  [{name}] 동일 척도 할인합 = {val:.2f}")


def main(with_top1=False):
    for keystone_cls, ks_label in ((LethalTempo, "치속"), (PressTheAttack, "집공")):
        for pkg in ADC_PACKAGES:
            cache = PowerCache(pkg, keystone_cls)
            for metric in ("dpg", "dps"):
                out = run_scenario(keystone_cls, pkg, metric, cache=cache)
                ctrl_rows = []
                for name, path in (("CTRL", CONTROL_PATH), ("CTRL2", CONTROL2_PATH)):
                    ctrl_rows.append((name, evaluate_fixed_path(
                        list(path), cache, metric, out["W"])))
                print_scenario(f"{ks_label} · {pkg['label']} · {metric.upper()}",
                               out, ctrl_rows)
            print(f"[{ks_label}·{pkg['label']}] sim_calls={cache.sim_calls}")


if __name__ == "__main__":
    import sys
    main(with_top1="--with-top1" in sys.argv)
```

주: `run_scenario` 시그니처에 `horizon` 파라미터가 테스트에서 쓰이므로 위처럼 포함. `--with-top1`은
파일럿에서는 수신만 하고 미구현(후속) — 인자 파싱만 두고 동작 없음, 주석으로 명시.

- [ ] **Step 4: 통과 확인 (전체 파일)**

Run: `.venv/bin/python -m pytest tests/test_cogmaw_sequential.py -v`
Expected: 8 passed (축소풀 테스트는 실제 시뮬 수십 회 — 수 초).

- [ ] **Step 5: CLAUDE.md** — 코그모 섹션 마지막에 문단 추가:

```
- **순차 최적 빌드 탐색**(`simulations/cogmaw_sequential.py`, 파일럿): 매 코어 시점에서 다음
  아이템을 "미래 코어 파워의 γ-할인합(γ=0.9, 5코어 호라이즌)" 최대화로 선택하는 DP.
  룬(치속/집공)×패키지(A/B)×지표(DPS/DPG)별 궤적 + 분기점 대안 top3 + [CTRL]/[CTRL2] 동일
  척도 비교 출력. 기존 가중 랭킹과 병행(대체 아님). `-m adc_sim.simulations.cogmaw_sequential`
  로 실행(표만, 헤드리스 안전 — 전체 풀 실행은 수 분). spec: 2026-07-06 설계 문서.
```

- [ ] **Step 6: 커밋**

```bash
git add tests/test_cogmaw_sequential.py adc_sim/simulations/cogmaw_sequential.py CLAUDE.md
git commit -m "feat(cogmaw): 순차 최적화 궤적 실행기·출력·__main__ + CLAUDE.md 문서화

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: 통합 검증

**Files:** 없음(검증만; 필요 시 버그픽스는 해당 파일)

**Interfaces:** Task 1~3 전부.

- [ ] **Step 1: 전체 스위트**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: **94 passed** (86 + 신규 8), 실패 0.

- [ ] **Step 2: 축소풀 스모크 실행** (전체 풀 실행은 컨트롤러가 별도 수행)

Run: `.venv/bin/python -c "
from adc_sim.simulations.cogmaw_sequential import run_scenario, PowerCache
from adc_sim.runes import LethalTempo
from adc_sim.data.items_data import ADC_PACKAGES
small = {1:['guinsoo','kraken'],2:['guinsoo','kraken','nashor'],3:['nashor','terminus','ldr'],4:['ie','pd','ldr','terminus'],5:['rabadon','void','ie','pd']}
out = run_scenario(LethalTempo, ADC_PACKAGES[1], 'dpg', candidates_map=small)
print('traj:', out['trajectory']); print('W0:', round(out['W0'],2)); print('sim_calls:', out['cache'].sim_calls)
"`
Expected: 5아이템 궤적 출력, 에러 없음, sim_calls > 0.

- [ ] **Step 3: 보고** — 이상 없으면 커밋 없이 DONE 보고(검증 태스크). 문제 발견 시 원인 파일 수정 + 테스트 보강 후 커밋.
