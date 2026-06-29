# Mana Resource Engine (Phase 0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make mana a hard-bounded consumable resource in the event-driven sim — skills cost mana, mana regenerates per second, and any cast that exceeds available mana is impossible — without changing existing champion DPS except where intended.

**Architecture:** Add mana state + helpers to the `Champion` base class (`current_mana`, `can_afford`, `spend_mana`, `regen_mana`, `mana_regen_per_sec`). Centralize regen in the base `advance_combat_time` (all champions call `super()`), so every champion regenerates for free. Gate the *cast-based* champions (Kai'Sa/Corki/Ezreal) at `_can_cast_skill` + spend at `_cast_*`, and fix `get_time_to_next_skill_event` with a "time-until-affordable" term so the min-dt loop never spins. Gate the *buff-abstracted* champions (Ashe/Yunara) at their `activate_q` point; Jinx Q is free (data only). Verify with a before/after DPS snapshot/diff over all existing champions.

**Tech Stack:** Python 3.10, stdlib only (no pytest). Tests are plain-`assert` scripts in a new `tests/` package, run with `.venv/bin/python -m tests.<name>`.

## Global Constraints

- **Interpreter:** always `.venv/bin/python` (Python 3.10). Never system `python3` (3.9). Run modules from repo root with `-m`.
- **No new dependencies.** `requirements.txt` stays `matplotlib`. Tests use stdlib `assert` only.
- **Mana hard bound (H-MANA-2):** if `cost > current_mana`, the skill **cannot** be cast (skipped); it waits until mana regenerates enough. A cast exceeding mana never happens.
- **Skills are instant (H-MANA-5):** casting does not consume attack-cycle time (engine-wide model, unchanged). Mana is the only throttle.
- **Autos are free:** basic-attack path (`get_one_hit_damage`) costs no mana — keep it byte-for-byte behavior-preserving.
- **Regen (H-MANA-1):** `mana_regen_per_sec = (base_mp5 + mp5_growth*(level-1) + sum(item mp5)) / 5.0`. Centralized in base `advance_combat_time`. Ignore complex regen passives.
- **Numbers are sourced, never estimated** (data-cross-validation rule): per-champion mana data is filled only from Task 4's cross-validated + user-confirmed table.
- **Item stat single source:** `adc_sim/data/items_data.py`. If an item grants MP5, add a `mana_regen` key there (and to `STAT_KEYS`), not in `items.py`.
- **AGENTS.md:** minimal change, add-before-replace, preserve existing behavior, hypothesis-tagged comments on new mechanics, explicit verification each task.
- **Return-tuple shapes (do not break):** item `on_hit`→`(phys,magic,true_base,true_onhit)`; champion/rune onhit→`(phys,magic)`; skill event→`(name,phys,magic,is_skill_hit)`; `get_one_hit_damage`→`(phys_base,magic_base,phys_onhit,magic_onhit,true_base,true_onhit)`.
- **Scope:** Phase 0 only. Cog'Maw class/sim = Phase 1 (separate plan). Manamune/Archangel rework = Phase 2 (separate plan). Do **not** touch item damage formulas here.

---

### Task 1: Capture pre-change DPS baseline (must run before any code change)

**Files:**
- Create: `tests/__init__.py` (empty — makes `tests` a package)
- Create: `tests/regression_snapshot.py`
- Create (generated): `tests/_baseline_dps.json`

**Interfaces:**
- Produces: `tests/regression_snapshot.py` exposing `REPRESENTATIVE_CASES` (list of `{"champion","fn","args"}`) and `compute_snapshot() -> dict[str, float]` mapping a case-key to DPS. Task 7 re-imports both.

- [ ] **Step 1: Create the `tests` package marker**

Create `tests/__init__.py` with a single comment line:

```python
# Test/verification scripts. Run with: .venv/bin/python -m tests.<name>
```

- [ ] **Step 2: Write the snapshot harness**

Create `tests/regression_snapshot.py`. It calls each champion's existing `simulate_*_core_path` for a fixed set of (build, tier) cases and returns DPS only (no plotting, no `plt.show()`). Use builds known to exist in each sim's search space (control builds).

```python
"""Pre/post mana-change DPS snapshot. No plotting — safe headless.

Run (capture baseline BEFORE mana changes):
    .venv/bin/python -m tests.regression_snapshot --write
Run (diff AFTER changes): see tests/test_regression_diff.py
"""
import json
from pathlib import Path

from adc_sim.simulations.ashe import simulate_ashe_core_path
from adc_sim.simulations.yunara import simulate_yunara_core_path
from adc_sim.simulations.kaisa import simulate_kaisa_core_path
from adc_sim.simulations.corki import simulate_corki_core_path
from adc_sim.simulations.ezreal import simulate_ezreal_core_path

BASELINE_PATH = Path(__file__).with_name("_baseline_dps.json")

# Control/representative builds per champion (must exist in each sim's pool).
REPRESENTATIVE_CASES = [
    {"champion": "Ashe",   "fn": simulate_ashe_core_path,   "path": ("kraken", "pd", "ie", "ldr")},
    {"champion": "Yunara", "fn": simulate_yunara_core_path, "path": ("kraken", "pd", "ie", "ldr")},
    {"champion": "KaiSa",  "fn": simulate_kaisa_core_path,  "path": ("kraken", "guinsoo", "nashor", "terminus")},
    {"champion": "Corki",  "fn": simulate_corki_core_path,  "path": ("trinity", "muramana", "collector", "ie")},
    {"champion": "Ezreal", "fn": simulate_ezreal_core_path, "path": ("trinity", "muramana", "ie", "ldr")},
]


def _dps_for_case(case, tier):
    """Call a champion's simulate_*_core_path with whatever signature it has.

    Ashe/Yunara/KaiSa: fn(path, tier). Corki/Ezreal: fn(path, shoe, rune, tier).
    Returns dps (first element of the returned tuple)."""
    fn, path = case["fn"], case["path"]
    name = case["champion"]
    if name in ("Corki", "Ezreal"):
        result = fn(path, "berserker", "conq", tier)
    else:
        result = fn(path[:tier], tier) if name == "Ashe" else fn(path, tier)
    return float(result[0])


def compute_snapshot():
    snap = {}
    for case in REPRESENTATIVE_CASES:
        for tier in (1, 2, 3, 4):
            key = f"{case['champion']}|{'-'.join(case['path'])}|T{tier}"
            snap[key] = round(_dps_for_case(case, tier), 6)
    return snap


if __name__ == "__main__":
    import sys
    snap = compute_snapshot()
    if "--write" in sys.argv:
        BASELINE_PATH.write_text(json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[baseline] wrote {len(snap)} cases -> {BASELINE_PATH}")
    else:
        print(json.dumps(snap, indent=2, ensure_ascii=False))
```

- [ ] **Step 3: Verify the harness runs against current (pre-change) code**

Run: `.venv/bin/python -m tests.regression_snapshot`
Expected: prints a JSON object of ~20 case→DPS entries, all finite positive numbers, no traceback.
(If any `simulate_*_core_path` signature differs, fix `_dps_for_case` now — read the actual signature in the sim file. Do not guess.)

- [ ] **Step 4: Write the baseline snapshot file**

Run: `.venv/bin/python -m tests.regression_snapshot --write`
Expected: `[baseline] wrote N cases -> .../tests/_baseline_dps.json` and the file exists.

- [ ] **Step 5: Commit**

```bash
git add tests/__init__.py tests/regression_snapshot.py tests/_baseline_dps.json
git commit -m "test: capture pre-mana-change DPS baseline (Phase 0 regression guard)"
```

---

### Task 2: Base-class mana state + helpers

**Files:**
- Modify: `adc_sim/champion.py` (class `Champion`: `__init__`, `init_combat_state`, `advance_combat_time`; add helpers)
- Create: `tests/test_mana_base.py`

**Interfaces:**
- Produces (on `Champion`): attrs `current_mana: float`, `base_mp5: float`, `mp5_growth: float`; property `mana_regen_per_sec: float`; methods `can_afford(cost: float) -> bool`, `spend_mana(cost: float) -> None`, `regen_mana(dt: float) -> None`, `_afford_in(cost: float) -> float`. `init_combat_state` sets `current_mana = total_mana`. Base `advance_combat_time` calls `regen_mana(delta_time)`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_mana_base.py`:

```python
"""Base-class mana mechanics. Run: .venv/bin/python -m tests.test_mana_base"""
from adc_sim.champion import Champion


def _make():
    c = Champion(name="T", base_ad=60, base_as=0.65, as_ratio=0.65,
                 as_growth=2.0, base_range=500, level=11)
    c.base_mana = 400.0
    c.mana_growth = 40.0      # total_mana = 400 + 40*10 = 800
    c.base_mp5 = 10.0
    c.mp5_growth = 0.5        # mp5 = 10 + 0.5*10 = 15 -> 3.0/sec
    return c


def test_init_fills_to_full():
    c = _make()
    c.init_combat_state()
    assert abs(c.current_mana - 800.0) < 1e-9, c.current_mana


def test_regen_per_sec_and_clamp():
    c = _make(); c.init_combat_state()
    assert abs(c.mana_regen_per_sec - 3.0) < 1e-9, c.mana_regen_per_sec
    c.spend_mana(100.0)                 # 700
    c.regen_mana(10.0)                  # +30 -> 730
    assert abs(c.current_mana - 730.0) < 1e-9, c.current_mana
    c.regen_mana(10_000.0)              # clamp at 800
    assert abs(c.current_mana - 800.0) < 1e-9, c.current_mana


def test_afford_and_spend():
    c = _make(); c.init_combat_state(); c.spend_mana(750.0)   # 50 left
    assert c.can_afford(50.0) and not c.can_afford(50.1)
    assert abs(c._afford_in(50.0) - 0.0) < 1e-9
    # need 110 -> short 60 -> at 3/sec -> 20s
    assert abs(c._afford_in(110.0) - 20.0) < 1e-9, c._afford_in(110.0)
    c.spend_mana(999.0)                 # clamps to 0, never negative
    assert c.current_mana == 0.0


def test_no_regen_means_infinite_afford():
    c = _make(); c.base_mp5 = 0.0; c.mp5_growth = 0.0
    c.init_combat_state(); c.spend_mana(800.0)
    assert c._afford_in(10.0) == float("inf")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"PASS {name}")
    print("ALL PASS")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m tests.test_mana_base`
Expected: FAIL — `AttributeError` on `base_mp5`/`mana_regen_per_sec`/`can_afford` (not yet defined).

- [ ] **Step 3: Add mana state + helpers to `Champion`**

In `adc_sim/champion.py`, in `Champion.__init__` (after the existing dynamic-stat block, near `self.ability_haste = 0.0`), add:

```python
        # 마나 자원 (Phase 0). total_mana = 풀; current_mana = 전투 중 현재값.
        self.current_mana = 0.0
        self.base_mp5 = 0.0      # 5초당 기본 마나재생 (챔프별 데이터, Task 6)
        self.mp5_growth = 0.0    # 레벨당 MP5 성장
```

Add these methods to `Champion` (place near `total_mana`):

```python
    @property
    def mana_regen_per_sec(self):
        """초당 마나 재생 = (기본 MP5 + 성장 + 아이템 MP5)/5. [H-MANA-1] 복합 패시브 무시."""
        base = self.base_mp5 + self.mp5_growth * (self.level - 1)
        item_mp5 = 0.0
        for item in self.inventory:
            item_mp5 += getattr(item, "stats", {}).get("mana_regen", 0.0)
        return (base + item_mp5) / 5.0

    def can_afford(self, cost):
        """[H-MANA-2] 하드 바운드: 현재 마나로 cost를 감당 가능한가."""
        return self.current_mana + 1e-9 >= cost

    def spend_mana(self, cost):
        """마나 차감(0 미만 클램프)."""
        self.current_mana = max(0.0, self.current_mana - cost)

    def regen_mana(self, dt):
        """dt초 동안 마나 재생(total_mana 상한 클램프)."""
        if dt > 0:
            self.current_mana = min(self.total_mana, self.current_mana + self.mana_regen_per_sec * dt)

    def _afford_in(self, cost):
        """cost를 감당할 때까지 남은 시간(초). 0=즉시, inf=재생 0이라 영영 불가. [0-dt 스핀 방지용]"""
        if self.can_afford(cost):
            return 0.0
        rps = self.mana_regen_per_sec
        if rps <= 0:
            return float("inf")
        return (cost - self.current_mana) / rps
```

- [ ] **Step 4: Reset mana on combat start + regen each step (base class)**

In `Champion.init_combat_state`, change the body to also fill mana:

```python
    def init_combat_state(self, skill_plan=None):
        self._combat_time = 0.0
        self.current_mana = self.total_mana   # 전투 시작 시 풀충전
```

In `Champion.advance_combat_time`, add regen:

```python
    def advance_combat_time(self, delta_time, current_time, target):
        self._combat_time = current_time
        self.regen_mana(delta_time)           # [H-MANA-1] 중앙집중 재생; 서브클래스는 super() 호출로 상속
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m tests.test_mana_base`
Expected: `PASS test_*` ×4, then `ALL PASS`.

- [ ] **Step 6: Commit**

```bash
git add adc_sim/champion.py tests/test_mana_base.py
git commit -m "feat(mana): base-class mana state, regen, hard-bound helpers (Phase 0)"
```

---

### Task 3: Cast-gating + 0-dt-spin fix for cast-based champions (Kai'Sa / Corki / Ezreal)

**Files:**
- Modify: `adc_sim/champion.py` (classes `KaiSa`, `Corki`, `Ezreal`: add `self.mana_cost`, gate `_can_cast_skill`/`_can_cast`, spend in `_cast_*`, augment `get_time_to_next_skill_event`)
- Create: `tests/test_mana_gating.py`

**Interfaces:**
- Consumes: `Champion.can_afford/_afford_in/spend_mana` (Task 2).
- Produces: each cast champ has `self.mana_cost: dict[str,float]`; `_can_cast_skill(name)`/`_can_cast(name)` returns False when unaffordable; `get_time_to_next_skill_event` returns `max(cd_left, _afford_in(cost))` per skill.

- [ ] **Step 1: Write the failing test (synthetic costs — logic only, real numbers come in Task 6)**

Create `tests/test_mana_gating.py`:

```python
"""Cast gating + no-spin. Uses synthetic mana to test the MECHANISM.
Run: .venv/bin/python -m tests.test_mana_gating"""
from adc_sim.champion import KaiSa, Target
from adc_sim.engine import run_simulation


def test_oom_blocks_cast_and_never_spins():
    k = KaiSa(level=11, q_level=5, w_level=5, e_level=5, r_level=3)
    # Force a tiny pool + zero regen: once mana is gone, Q/W must not cast,
    # and the sim must still terminate in finite steps (0-dt spin guard).
    k.base_mana = 0.0; k.mana_growth = 0.0; k.base_mp5 = 0.0; k.mp5_growth = 0.0
    k.mana_cost = {"q": 50.0, "w": 50.0, "e": 0.0, "r": 0.0}
    target = Target(hp=3000, armor=80, magic_resist=50, bonus_hp=1500)
    # Must return (finite kill time, positive dps) without hanging.
    history, dps, kill_time = run_simulation(k, target, verbose=False,
        skill_plan={"auto_cast": {"q": True, "w": True, "e": False, "r": False}})
    assert dps > 0 and kill_time < 10_000, (dps, kill_time)
    assert k.current_mana >= -1e-9


def test_affordable_casts_consume_mana():
    k = KaiSa(level=11, q_level=5, w_level=5, e_level=5, r_level=3)
    k.base_mana = 1000.0; k.mana_growth = 0.0; k.base_mp5 = 0.0; k.mp5_growth = 0.0
    k.mana_cost = {"q": 50.0, "w": 50.0, "e": 0.0, "r": 0.0}
    k.init_combat_state({"auto_cast": {"q": True, "w": False, "e": False, "r": False}})
    start = k.current_mana
    assert k._can_cast_skill("q")
    k.pop_due_skill_events(0.0, Target(hp=4000, armor=80, magic_resist=50))
    assert k.current_mana <= start - 50.0 + 1e-9, (start, k.current_mana)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"PASS {name}")
    print("ALL PASS")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m tests.test_mana_gating`
Expected: FAIL — either `AttributeError: mana_cost` or a hang/wrong value (gating not yet implemented). If it hangs, Ctrl-C confirms the spin the fix prevents.

- [ ] **Step 3: KaiSa — add costs, gate, spend, afford-aware dt**

In `KaiSa.__init__` (after `self.cooldowns_remaining = {...}` block) add a default cost map (real values set in Task 6; default keeps tests/other code working):

```python
        # 스킬 마나 비용 (실제 수치는 Task 6 확정 데이터로 교체). [H-MANA-2]
        self.mana_cost = {"q": 0.0, "w": 0.0, "e": 0.0, "r": 0.0}
```

In `KaiSa._can_cast_skill`, add the affordability clause before `return True`:

```python
        if not self.can_afford(self.mana_cost.get(skill_name, 0.0)):
            return False
        return True
```

In `KaiSa._cast_skill` spend at the moment of casting — add as the first line of the method:

```python
        self.spend_mana(self.mana_cost.get(skill_name, 0.0))
```

In `KaiSa.get_time_to_next_skill_event`, change the per-skill candidate to include afford time. Replace the auto-skill loop body:

```python
        for skill_name, enabled in self.auto_skill_enabled.items():
            if not enabled:
                continue
            if skill_name == "e" and self.e_active:
                continue
            remaining = self.cooldowns_remaining.get(skill_name, float("inf"))
            afford = self._afford_in(self.mana_cost.get(skill_name, 0.0))
            candidates.append(max(0.0, remaining, afford))   # [0-dt 스핀 방지]
```

- [ ] **Step 4: Corki — same wiring**

In `Corki.__init__` (after its `self.cooldowns_remaining = {...}`):

```python
        self.mana_cost = {"q": 0.0, "w": 0.0, "e": 0.0, "r": 0.0}   # 실수치 Task 6
```

In `Corki._cast_skill`, first line:

```python
        self.spend_mana(self.mana_cost.get(skill_name, 0.0))
```

In `Corki._can_cast_skill`, gate each branch by wrapping the final decision — replace the method's per-skill `return` checks so each returns `False` when unaffordable. Simplest: at the top of `_can_cast_skill`, after computing it would be castable, add an affordability guard. Concretely, change the body to:

```python
    def _can_cast_skill(self, skill_name):
        eps = 1e-9
        if not self.can_afford(self.mana_cost.get(skill_name, 0.0)):
            return False
        if skill_name == "r":
            return self.r_charges > 0 and self.cooldowns_remaining["r_cast"] <= eps
        if skill_name == "q":
            return self.cooldowns_remaining["q"] <= eps
        if skill_name == "w":
            return self.cooldowns_remaining["w"] <= eps
        if skill_name == "e":
            return self.cooldowns_remaining["e"] <= eps
        return False
```

In `Corki.get_time_to_next_skill_event`, add afford time to each appended candidate. Replace the four `candidates.append(...)` lines for q/w/e/r with:

```python
        if self.auto_skill_enabled.get("e", False):
            candidates.append(max(0.0, self.cooldowns_remaining["e"], self._afford_in(self.mana_cost.get("e", 0.0))))
        if self.auto_skill_enabled.get("q", False):
            candidates.append(max(0.0, self.cooldowns_remaining["q"], self._afford_in(self.mana_cost.get("q", 0.0))))
        if self.auto_skill_enabled.get("w", False):
            candidates.append(max(0.0, self.cooldowns_remaining["w"], self._afford_in(self.mana_cost.get("w", 0.0))))
        if self.auto_skill_enabled.get("r", False) and self.r_charges > 0:
            candidates.append(max(0.0, self.cooldowns_remaining["r_cast"], self._afford_in(self.mana_cost.get("r", 0.0))))
```

- [ ] **Step 5: Ezreal — same wiring**

In `Ezreal.__init__` (after `self.auto_skill_order = ["q", "w", "e"]`):

```python
        self.mana_cost = {"q": 0.0, "w": 0.0, "e": 0.0}   # 실수치 Task 6
```

In `Ezreal._cast_skill`, first line:

```python
        self.spend_mana(self.mana_cost.get(name, 0.0))
```

In `Ezreal._can_cast`, gate:

```python
    def _can_cast(self, name):
        if not self.can_afford(self.mana_cost.get(name, 0.0)):
            return False
        return self.cooldowns_remaining.get(name, float("inf")) <= 1e-9
```

In `Ezreal.get_time_to_next_skill_event`, change the enabled-skill loop:

```python
        for name, enabled in self.auto_skill_enabled.items():
            if enabled:
                candidates.append(max(0.0, self.cooldowns_remaining.get(name, float("inf")),
                                      self._afford_in(self.mana_cost.get(name, 0.0))))
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/bin/python -m tests.test_mana_gating`
Expected: `PASS test_oom_blocks_cast_and_never_spins`, `PASS test_affordable_casts_consume_mana`, `ALL PASS`. (No hang.)

- [ ] **Step 7: Commit**

```bash
git add adc_sim/champion.py tests/test_mana_gating.py
git commit -m "feat(mana): cast gating + 0-dt afford-aware scheduling for KaiSa/Corki/Ezreal"
```

---

### Task 4: Source & confirm per-champion mana data (interactive research)

**Files:**
- Modify: `docs/superpowers/specs/2026-06-29-mana-resource-overhaul.md` (§3.5 table — fill `[src?]` cells)

**Interfaces:**
- Produces: a fully-filled mana table (base_mana, mana_growth, base_mp5, mp5_growth, per-skill mana costs) for Ashe, Jinx, Yunara, Kai'Sa, Corki, Ezreal — the exact numbers Task 6 encodes.

- [ ] **Step 1: Gather from multiple sources (no estimation)**

For each of Ashe, Jinx, Yunara, Kai'Sa, Corki, Ezreal, collect: `base_mana`, `mana_growth`, `base_mp5`, `mp5_growth`, and per-skill mana costs (Q/W/E/R as modeled).
- Try in order: Meraki JSON (`https://cdn.merakianalytics.com/riot/lol/resources/latest/en-US/champions/<Name>.json`), DDragon (`.../cdn/16.13.1/data/en_US/champion/<Name>.json` stats block), and LoL Wiki.
- Known anchors already in code (verify, don't blindly trust): KaiSa 345(+40); Corki 350(+40); Ezreal 375(+70). Known: Ashe Q (Ranger's Focus) ≈ 50; Jinx Q (Switcheroo) = 0.
- **Meraki proved unreliable for Kog'Maw** (wrong AS/AP ratios) — cross-check every Meraki number against a 2nd source.

- [ ] **Step 2: Present the filled table to the user and get explicit confirmation**

Post the completed table (all 6 champions × 5 stat columns + skill costs) and ask the user to confirm or correct, exactly as done for Cog'Maw via Namu Wiki. Wait for confirmation. Treat user corrections as authoritative.

- [ ] **Step 3: Record confirmed numbers in the spec**

Replace the `[src?]` cells in §3.5 of `docs/superpowers/specs/2026-06-29-mana-resource-overhaul.md` with the confirmed values and source tags (`✓`/`[user]`).

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-06-29-mana-resource-overhaul.md
git commit -m "docs(mana): fill confirmed per-champion mana data table (§3.5)"
```

---

### Task 5: Encode per-champion mana data (base/growth/MP5 + skill costs)

**Files:**
- Modify: `adc_sim/champion.py` (Ashe, Jinx, Yunara, KaiSa, Corki, Ezreal `__init__`)
- Create: `tests/test_mana_data.py`

**Interfaces:**
- Consumes: confirmed table (Task 4).
- Produces: every champion sets `base_mana`, `mana_growth`, `base_mp5`, `mp5_growth`, and cast champs set real `self.mana_cost`. After this task, `total_mana` and `mana_regen_per_sec` are correct for all champions.

- [ ] **Step 1: Write the failing test (assert the confirmed values — fill from Task 4 table)**

Create `tests/test_mana_data.py`. Use the **confirmed** numbers from Task 4 (the example values below are placeholders for the test author to replace with the committed §3.5 table — replace ALL of them):

```python
"""Per-champion mana data is present & correct. Run: .venv/bin/python -m tests.test_mana_data"""
from adc_sim.champion import Ashe, Jinx, Yunara, KaiSa, Corki, Ezreal

# (base_mana, mana_growth, base_mp5, mp5_growth)  -- REPLACE with confirmed §3.5 values
EXPECTED = {
    "Ashe":   (280.0, 35.0,  7.0,  0.65),
    "Jinx":   (260.0, 50.0,  6.7,  0.45),
    "Yunara": (300.0, 40.0,  8.0,  0.7),
    "KaiSa":  (345.0, 40.0,  8.2,  0.7),
    "Corki":  (350.0, 40.0,  7.4,  0.55),
    "Ezreal": (375.0, 70.0,  8.5,  0.65),
}


def test_pools_and_regen_present():
    for cls in (Ashe, Jinx, Yunara, KaiSa, Corki, Ezreal):
        c = cls(level=11)
        bm, mg, mp5, mp5g = EXPECTED[c.name.replace("'", "")] if c.name != "Kai'Sa" else EXPECTED["KaiSa"]
        assert abs(c.base_mana - bm) < 1e-9, (c.name, c.base_mana)
        assert abs(c.mana_growth - mg) < 1e-9, (c.name, c.mana_growth)
        assert abs(c.base_mp5 - mp5) < 1e-9, (c.name, c.base_mp5)
        assert c.total_mana > 0 and c.mana_regen_per_sec > 0


def test_cast_champs_have_real_costs():
    for cls in (KaiSa, Corki, Ezreal):
        c = cls(level=11)
        assert any(v > 0 for v in c.mana_cost.values()), (c.name, c.mana_cost)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"PASS {name}")
    print("ALL PASS")
```

(Note: simplify the name-keying if needed; the point is each champion's confirmed numbers are asserted.)

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m tests.test_mana_data`
Expected: FAIL — Ashe/Jinx/Yunara have `base_mana == 0` (defaults), assertions fail.

- [ ] **Step 3: Set base mana/growth/MP5 on every champion**

In each champion's `__init__`, set the four mana-pool fields from the confirmed table. Example for Ashe (replace numbers with confirmed §3.5):

```python
        # 마나 (Task 4 확정). [데이터 출처: spec §3.5]
        self.base_mana = 280.0
        self.mana_growth = 35.0
        self.base_mp5 = 7.0
        self.mp5_growth = 0.65
```

Do the same for Jinx, Yunara. For KaiSa/Corki/Ezreal, **add** the missing `base_mp5`/`mp5_growth` (they already set `base_mana`/`mana_growth`; KaiSa already has `base_mana_regen`/`mana_regen_growth` — set `base_mp5`/`mp5_growth` to those same confirmed values for consistency).

- [ ] **Step 4: Set real `self.mana_cost` for cast champs**

Replace the `{"q":0.0,...}` defaults in KaiSa/Corki/Ezreal with confirmed costs, e.g.:

```python
        self.mana_cost = {"q": 55.0, "w": 80.0, "e": 0.0, "r": 100.0}   # KaiSa, 확정 §3.5
```

(Use the per-skill costs as modeled. If a modeled skill toggles a buff with no mana in-game, set 0.0.)

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m tests.test_mana_data`
Expected: `PASS test_pools_and_regen_present`, `PASS test_cast_champs_have_real_costs`, `ALL PASS`.

- [ ] **Step 6: Commit**

```bash
git add adc_sim/champion.py tests/test_mana_data.py
git commit -m "feat(mana): encode confirmed per-champion mana pools, regen, skill costs"
```

---

### Task 6: Buff-abstracted champions — mana-gated activation (Ashe / Yunara), Jinx data-only

**Files:**
- Modify: `adc_sim/champion.py` (Ashe `activate_q`; Yunara `activate_q`; add `q_mana_cost` to both)
- Create: `tests/test_mana_buff_champs.py`

**Interfaces:**
- Consumes: `can_afford`/`spend_mana` (Task 2), confirmed Ashe/Yunara Q cost (Task 4).
- Produces: Ashe/Yunara `activate_q` only fires when `can_afford(q_mana_cost)`, spending it; otherwise activation is deferred (buff effect preserved, just gated). Jinx unchanged (Q free).

- [ ] **Step 1: Write the failing test**

Create `tests/test_mana_buff_champs.py`:

```python
"""Ashe/Yunara Q activation is mana-gated. Run: .venv/bin/python -m tests.test_mana_buff_champs"""
from adc_sim.champion import Ashe, Yunara, Target


def test_ashe_q_blocked_when_oom():
    a = Ashe(level=11, q_level=5)
    a.q_mana_cost = 50.0
    a.init_combat_state()
    a.current_mana = 0.0          # force OOM
    a.hit_count = 4               # activation condition met
    a.get_one_hit_damage(Target(hp=2000, armor=60, magic_resist=40), time=1.0)
    assert a.q_active is False, "Q must not activate while OOM"


def test_ashe_q_activates_and_spends_when_affordable():
    a = Ashe(level=11, q_level=5)
    a.q_mana_cost = 50.0
    a.init_combat_state()
    a.current_mana = 500.0
    a.hit_count = 4
    a.get_one_hit_damage(Target(hp=2000, armor=60, magic_resist=40), time=1.0)
    assert a.q_active is True
    assert a.current_mana <= 500.0 - 50.0 + 1e-9, a.current_mana


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"PASS {name}")
    print("ALL PASS")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m tests.test_mana_buff_champs`
Expected: FAIL — `q_active` becomes True even at 0 mana (no gate yet), or `AttributeError: q_mana_cost`.

- [ ] **Step 3: Gate Ashe `activate_q`**

In `Ashe.__init__`, add the cost (confirmed value from Task 4):

```python
        self.q_mana_cost = 50.0   # Ranger's Focus, 확정 §3.5. [H-MANA-3]
```

At the very start of `Ashe.activate_q(self, time)`, add the hard-bound gate:

```python
        # [H-MANA-3] 마나 부족 시 활성 지연(버프 효과는 보존, 활성만 게이트)
        if not self.can_afford(self.q_mana_cost):
            return
        self.spend_mana(self.q_mana_cost)
```

- [ ] **Step 4: Gate Yunara `activate_q` the same way**

In `Yunara.__init__`:

```python
        self.q_mana_cost = 0.0   # 확정 §3.5 (Yunara Q cost). [H-MANA-3]
```

At the start of `Yunara.activate_q(self, time)`:

```python
        if not self.can_afford(self.q_mana_cost):
            return
        self.spend_mana(self.q_mana_cost)
```

(Jinx: no change — Q is 0 mana. Its pool/regen data was set in Task 5.)

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m tests.test_mana_buff_champs`
Expected: `PASS test_ashe_q_blocked_when_oom`, `PASS test_ashe_q_activates_and_spends_when_affordable`, `ALL PASS`.

- [ ] **Step 6: Commit**

```bash
git add adc_sim/champion.py tests/test_mana_buff_champs.py
git commit -m "feat(mana): mana-gated Q activation for Ashe/Yunara (Jinx Q free)"
```

---

### Task 7: Regression diff — prove only intended changes

**Files:**
- Create: `tests/test_regression_diff.py`

**Interfaces:**
- Consumes: `tests.regression_snapshot.compute_snapshot`, `tests/_baseline_dps.json` (Task 1).
- Produces: a pass/fail diff classifying every case as unchanged (within tolerance) or changed, with changed cases printed for the user to confirm they are intended (mana-item builds, or champs that genuinely went OOM).

- [ ] **Step 1: Write the diff test**

Create `tests/test_regression_diff.py`:

```python
"""Compare post-change DPS to the pre-change baseline.
Run: .venv/bin/python -m tests.test_regression_diff"""
import json
from tests.regression_snapshot import compute_snapshot, BASELINE_PATH

TOL = 1e-4   # relative tolerance


def test_no_unexpected_dps_change():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    now = compute_snapshot()
    changed = []
    for key, base in baseline.items():
        cur = now.get(key)
        assert cur is not None, f"missing case {key}"
        denom = base if abs(base) > 1e-9 else 1.0
        if abs(cur - base) / abs(denom) > TOL:
            changed.append((key, base, cur, f"{(cur-base)/denom*100:+.2f}%"))
    if changed:
        print("CHANGED CASES (confirm intended — mana-item builds / OOM):")
        for row in changed:
            print("  ", row)
    # The representative builds in Task 1 are non-mana-item, short-ish fights:
    # expectation is ZERO changed. If any appear, STOP and explain before proceeding.
    assert not changed, f"{len(changed)} cases changed unexpectedly — investigate"


if __name__ == "__main__":
    test_no_unexpected_dps_change()
    print("PASS test_no_unexpected_dps_change")
    print("ALL PASS")
```

- [ ] **Step 2: Run the diff**

Run: `.venv/bin/python -m tests.test_regression_diff`
Expected: `PASS` (zero changed cases) — the representative builds carry no mana items and start at full mana, so over their kill-time windows no champion goes OOM and DPS is identical.

- [ ] **Step 3: If any case changed — investigate, do not paper over**

If `changed` is non-empty: for each case, determine *why* (did the champ go OOM within kill-time? is the kill-time long enough that regen/gating altered cast count?). Confirm the change is a true accuracy improvement (the champ really would run out in that scenario), report it to the user with the per-case delta, and only then accept it by moving that case to an `INTENDED_CHANGES` allowlist in the test (with a comment citing the reason). Never loosen `TOL` to hide a real behavior change.

- [ ] **Step 4: Run the full Phase 0 test suite**

Run each and confirm `ALL PASS`:
```bash
.venv/bin/python -m tests.test_mana_base
.venv/bin/python -m tests.test_mana_gating
.venv/bin/python -m tests.test_mana_data
.venv/bin/python -m tests.test_mana_buff_champs
.venv/bin/python -m tests.test_regression_diff
```

- [ ] **Step 5: Smoke-run one real sim end-to-end (headless-safe portion)**

Run: `.venv/bin/python -c "from tests.regression_snapshot import compute_snapshot; print('cases:', len(compute_snapshot()))"`
Expected: prints `cases: 20` (or your case count) with no traceback — confirms all sims still import and run with mana active.

- [ ] **Step 6: Commit**

```bash
git add tests/test_regression_diff.py
git commit -m "test(mana): regression diff vs baseline — Phase 0 preserves existing DPS"
```

---

## Self-Review

**Spec coverage (Phase 0 = spec §3, §8 steps 1–2):**
- §3.1 base state/helpers/reset → Task 2 ✓
- §3.2 regen model → Task 2 (Step 4) ✓
- §3.3 cast gating + 0-dt fix → Task 3 ✓
- §3.4 buff-champ discretization (Ashe/Yunara gated; Jinx data-only) → Task 6 ✓
- §3.5 per-champion data schema + sourcing/confirm → Task 4 (source) + Task 5 (encode) ✓
- §3.6 snapshot/diff regression → Task 1 (baseline) + Task 7 (diff) ✓
- §3.7 hypotheses H-MANA-1..5 → cited in code comments across Tasks 2/3/6 ✓
- (Phase 1 Cog'Maw, Phase 2 items = separate plans, intentionally out of scope.)

**Placeholder scan:** Task 5's `EXPECTED`/example cost numbers are explicitly flagged "replace with confirmed §3.5 values from Task 4" — this is a *data dependency on Task 4's verified table*, mandated by the don't-estimate rule, not a lazy placeholder. All code mechanics (helpers, gating, regen, 0-dt fix, buff gating, diff) are fully specified. No "TODO/handle edge cases/add validation" present.

**Type consistency:** `mana_cost` is a `dict[str,float]` on every cast champ; `can_afford(cost)`, `spend_mana(cost)`, `regen_mana(dt)`, `_afford_in(cost)` signatures are identical across Tasks 2/3/6; `compute_snapshot()` / `BASELINE_PATH` names match between Task 1 and Task 7. `q_mana_cost` (Ashe/Yunara) is consistently a float.

**Sequencing note:** Tasks 2–3 build/test the *mechanism* with synthetic mana, so they don't block on Task 4's interactive data sourcing. Real numbers land in Task 5. Task 1 must run before any code change (captures the pre-mana baseline).
