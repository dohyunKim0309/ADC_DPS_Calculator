# Cog'Maw (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add Cog'Maw as a full-kit, mana-aware champion (`CogMaw` class) plus a dedicated build-ranking simulation (`simulations/cogmaw.py`), reusing the Phase 0 mana engine so R is naturally throttled by its mana ramp.

**Architecture:** `CogMaw(Champion)` mirrors the KaiSa/Corki event-driven skill system. Basic attacks + a constant Q-passive attack-speed bonus; **W** is a KaiSa-E-style cooldown-managed buff that, while active, makes each auto deal `(%maxHP + AP)` bonus magic on-hit via `get_champion_onhit`; **Q-active/E/R** are mana-gated damage casts (Q applies a Corki-E-style armor+MR % shred; R scales with the target's missing HP). The sim file mirrors `kaisa.py`'s 4-core search + `rel_dpg_score` (5:4:3:3) ranking.

**Tech Stack:** Python 3.10, stdlib + matplotlib. Tests are plain `assert` scripts under `tests/`, run with `.venv/bin/python -m tests.<name>`.

## Global Constraints

- **Interpreter:** always `.venv/bin/python` (3.10). Run sims/tests from repo root with `-m`.
- **Mana engine EXISTS (Phase 0):** `Champion` has `current_mana`, `can_afford(cost)`, `spend_mana(cost)`, `regen_mana(dt)`, `mana_regen_per_sec`, `_afford_in(cost)`; base `init_combat_state` fills `current_mana=total_mana`; base `advance_combat_time` regens. Cog'Maw MUST follow the KaiSa pattern: gate casts on `can_afford`, `spend_mana` once at cast, add `_afford_in(cost)` to `get_time_to_next_skill_event` candidates (0-dt-spin guard). Hard bound (H-MANA-2): a cast costing more than current mana cannot happen.
- **Confirmed numbers (spec §4.1, 4-source):** base_ad 61, **ad_growth 3.11**, base_as 0.665, as_ratio 0.665, as_growth 2.65, range 500. Mana: base_mana 325, mana_growth 40, base_mp5 8.75, mp5_growth 0.7. base_hp 635(+99), base_armor 24(+4.45), base_mr 30(+1.3). Skill mana: Q 40, W 40, E [40,55,70,85,100], R 40 + 40/stack (≤9 stacks, decays after 8s).
- **Return-tuple shapes (do not break):** champion onhit `get_champion_onhit(target) -> (phys, magic)`; skill event `(name, phys, magic, is_skill_hit)` (buff casts use `is_skill_hit=False`, damage casts `True`); `get_one_hit_damage -> (phys_base, magic_base, phys_onhit, magic_onhit, true_base, true_onhit)`.
- **No new dependencies.** No pytest. `git add` only the files each task names — never `-A`/`.` (the repo has unrelated uncommitted files: `adc_sim/simulations/{ashe,kaisa,yunara,power_compare}.py`, `items*.py`, `settings.py`, CLAUDE.md, etc. — leave them untouched).
- **AGENTS.md:** minimal change, hypothesis-tagged comments on new mechanics (`[H-KOG-*]` per spec §4.4), explicit verification each task.
- **Hypotheses (spec §4.4):** H-KOG-2 W cooldown-managed buff (8s/17s/mana40) + `(pct+0.00015·AP)·maxHP` on-hit, ×2 by Guinsoo proc, amped by mod_factor/Shadowflame; H-KOG-3 Q passive AS constant; H-KOG-4 Q-active armor+MR %shred (reduction-before-pen) + E/R cast on cd; H-KOG-5 R = `(base+0.75·bonusAD+apMin·AP)×mult`, `mult=2.0 if hp_ratio≤0.40 else 1+(5/6)·(1−hp_ratio)`, mana ramp.
- **Scope:** Cog'Maw class + `simulations/cogmaw.py` only. NOT `power_compare.py` integration (a later step). Cog'Maw is NOT added to other champions' sims.

---

### Task 1: `CogMaw` class — stats, mana, Q-passive AS, basic attack

**Files:**
- Modify: `adc_sim/champion.py` (add `class CogMaw(Champion)` after the `Ezreal` class)
- Test: `tests/test_cogmaw_basic.py`

**Interfaces:**
- Produces: `CogMaw(level=1, q_level=5, w_level=5, e_level=5, r_level=3)`. After construction: confirmed stats/mana set; `q_passive_as=[0.05,0.10,0.15,0.20,0.25]` added to `bonus_as_percent` at the chosen `q_level`; basic attacks work via the inherited `get_one_hit_damage`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cogmaw_basic.py`:

```python
"""CogMaw stats/mana/Q-passive AS + basic attack. Run: .venv/bin/python -m tests.test_cogmaw_basic"""
from adc_sim.champion import CogMaw, Target
from adc_sim.engine import run_simulation


def test_stats_and_mana():
    c = CogMaw(level=11, q_level=5)
    assert c.name == "Kog'Maw"
    assert abs(c.base_ad - 61) < 1e-9 and abs(c.ad_growth - 3.11) < 1e-9
    assert abs(c.base_as - 0.665) < 1e-9 and abs(c.as_ratio - 0.665) < 1e-9
    assert c.base_range == 500
    assert abs(c.base_mana - 325) < 1e-9 and abs(c.mana_growth - 40) < 1e-9
    assert abs(c.base_mp5 - 8.75) < 1e-9 and abs(c.mp5_growth - 0.7) < 1e-9
    assert c.total_mana > 0 and c.mana_regen_per_sec > 0


def test_q_passive_as_applied():
    # q5 passive = +25% AS folded into bonus_as_percent at construction.
    c5 = CogMaw(level=11, q_level=5)
    c1 = CogMaw(level=11, q_level=1)
    assert abs(c5.bonus_as_percent - 0.25) < 1e-9, c5.bonus_as_percent
    assert abs(c1.bonus_as_percent - 0.05) < 1e-9, c1.bonus_as_percent
    assert c5.current_attack_speed > c1.current_attack_speed


def test_basic_attack_kills_dummy():
    c = CogMaw(level=11, q_level=5)
    hist, dps, t = run_simulation(c, Target(hp=1500, armor=40, magic_resist=30), verbose=False)
    assert dps > 0 and t > 0


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_") and callable(f):
            f(); print(f"PASS {n}")
    print("ALL PASS")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m tests.test_cogmaw_basic`
Expected: FAIL — `ImportError: cannot import name 'CogMaw'`.

- [ ] **Step 3: Add the `CogMaw` class skeleton**

In `adc_sim/champion.py`, after the `Ezreal` class, add. (Follow the KaiSa `__init__` shape for the stored-but-unused base stats + the event-system state fields, which later tasks fill.)

```python
class CogMaw(Champion):
    """Kog'Maw — 온힛 %최대체력(W)·공속(Q패시브) 평타 캐리 + Q/E/R 마법. [Hypothesis 다수 — 스펙 §4]

    풀킷: 평타 + W(쿨관리 버프: 활성 중 평타가 %최대체력 마법 온힛) + Q(패시브 공속 + 액티브 넛지·방/마저 %감소)
    + E(마법 넛지) + R(잃은체력 연속배율 + 마나 램프). 마나는 Phase 0 엔진으로 하드 바운드.
    수치 출처: spec §4.1 (LoL Wiki+DDragon+Meraki+나무위키 4소스).
    """

    def __init__(self, level=1, q_level=5, w_level=5, e_level=5, r_level=3):
        super().__init__(
            name="Kog'Maw", base_ad=61, base_as=0.665, as_ratio=0.665,
            as_growth=2.65, base_range=500, level=level, ad_growth=3.11,
        )
        # 보관(비-DPS): 미래 1대1 모델용
        self.base_hp = 635; self.hp_growth = 99
        self.base_armor = 24; self.armor_growth = 4.45
        self.base_mr = 30; self.mr_growth = 1.3
        # 마나 (spec §3.5/§4.1). base_mp5/mp5_growth = Champion.mana_regen_per_sec가 읽는 이름.
        self.base_mana = 325; self.mana_growth = 40
        self.base_mp5 = 8.75; self.mp5_growth = 0.7

        self.q_level = q_level; self.w_level = w_level
        self.e_level = e_level; self.r_level = r_level

        # Q 패시브 공속 [H-KOG-3]: 상수(시전 시 순간해제 무시). 생성 시 1회 반영.
        self.q_passive_as = [0.05, 0.10, 0.15, 0.20, 0.25]
        self.bonus_as_percent += self.q_passive_as[self.q_level - 1]

        # 스킬 마나비용 (spec §3.5). R은 동적(스택)이라 _r_mana_cost()로 계산.
        self.mana_cost = {"q": 40.0, "w": 40.0, "e": 0.0, "r": 0.0}
        self.e_mana = [40.0, 55.0, 70.0, 85.0, 100.0]
        self.mana_cost["e"] = self.e_mana[self.e_level - 1]

        # 이벤트/버프 상태 (Task 2~4에서 채움)
        self.cooldowns_remaining = {"q": 0.0, "w": 0.0, "e": 0.0, "r": 0.0}
        self.manual_skill_casts = []
        self.manual_skill_index = 0
        self.auto_skill_enabled = {"q": True, "w": True, "e": True, "r": True}
        self.auto_skill_order = ["w", "q", "e", "r"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m tests.test_cogmaw_basic`
Expected: `PASS test_basic_attack_kills_dummy`, `PASS test_q_passive_as_applied`, `PASS test_stats_and_mana`, `ALL PASS`.

- [ ] **Step 5: Commit**

```bash
git add adc_sim/champion.py tests/test_cogmaw_basic.py
git commit -m "feat(cogmaw): class skeleton — stats, mana, Q-passive AS, basic attack"
```

---

### Task 2: W — Bio-Arcane Barrage (cooldown-managed %max-HP on-hit buff)

**Files:**
- Modify: `adc_sim/champion.py` (`CogMaw`: add W buff state + `get_champion_onhit` + event-system methods `init_combat_state`/`advance_combat_time`/`get_time_to_next_skill_event`/`get_time_to_next_state_event`/`pop_due_skill_events`/`_cast_skill`/`_can_cast_skill`/`_cast_w`)
- Test: `tests/test_cogmaw_w.py`

**Interfaces:**
- Consumes: Phase 0 `can_afford`/`spend_mana`/`_afford_in`; parent `get_one_hit_damage` calls `get_champion_onhit` (×Guinsoo proc_count, ×mod_factor, ×Shadowflame).
- Produces: while `w_active`, `get_champion_onhit(target) -> (0, (w_pct[idx] + 0.00015*total_ap)*target.max_hp)`; else `(0,0)`. W cast (`is_skill_hit=False`) toggles `w_active` for 8.0s, CD 17s (haste-reduced), mana 40, gated.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cogmaw_w.py`:

```python
"""CogMaw W = cooldown-managed %maxHP on-hit. Run: .venv/bin/python -m tests.test_cogmaw_w"""
from adc_sim.champion import CogMaw, Target


def test_onhit_zero_when_w_inactive():
    c = CogMaw(level=11, w_level=5); c.init_combat_state()
    c.w_active = False
    assert c.get_champion_onhit(Target(hp=2000, armor=40, magic_resist=30)) == (0, 0)


def test_onhit_pct_maxhp_when_active():
    c = CogMaw(level=11, w_level=5); c.init_combat_state()
    c.w_active = True; c._combat_time = 1.0
    tgt = Target(hp=2000, armor=40, magic_resist=30)
    phys, magic = c.get_champion_onhit(tgt)
    # w5 = 6% maxHP + 0.00015*AP*maxHP. AP=0 here -> 0.06*2000 = 120.
    assert phys == 0 and abs(magic - 0.06 * 2000) < 1e-6, (phys, magic)


def test_w_cast_toggles_buff_and_spends_mana():
    c = CogMaw(level=11, w_level=5); c.init_combat_state()
    start = c.current_mana
    name, p, m, is_hit = c._cast_skill("w", Target(hp=2000, armor=40, magic_resist=30), 0.0)
    assert is_hit is False and p == 0.0 and m == 0.0   # W is a buff, no direct damage
    assert c.w_active is True
    assert c.current_mana <= start - 40.0 + 1e-9


def test_w_expires_after_8s():
    c = CogMaw(level=11, w_level=5); c.init_combat_state()
    c._cast_skill("w", Target(hp=2000, armor=40, magic_resist=30), 0.0)
    c.advance_combat_time(8.0 + 1e-6, 8.0 + 1e-6, Target(hp=2000, armor=40, magic_resist=30))
    assert c.w_active is False


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_") and callable(f):
            f(); print(f"PASS {n}")
    print("ALL PASS")
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m tests.test_cogmaw_w`
Expected: FAIL — `AttributeError` (`w_active`/`init_combat_state` not yet on CogMaw, or `get_champion_onhit` inherited returns (0,0) but `_cast_skill`/`init_combat_state` missing).

- [ ] **Step 3: Add W state + the event-system scaffolding (mirror KaiSa) + `get_champion_onhit`**

Add to `CogMaw` these methods. The event-system methods mirror `KaiSa`'s exactly in shape (read `KaiSa.init_combat_state`/`advance_combat_time`/`get_time_to_next_skill_event`/`pop_due_skill_events`/`_can_cast_skill`/`_cast_skill` in `champion.py` for the template); the Cog'Maw-specific parts are W's buff toggle here and Q/E/R in later tasks.

```python
    # W 데이터 [H-KOG-2]
    W_PCT = [0.03, 0.0375, 0.045, 0.0525, 0.06]   # 랭크별 최대체력 비율
    W_DURATION = 8.0
    W_CD = 17.0

    def get_champion_onhit(self, target):
        """W 활성 중 평타 온힛: 대상 최대체력 비례 마법(+AP). [H-KOG-2]

        구인수 proc_count·mod_factor·Shadowflame 증폭은 부모 get_one_hit_damage가 처리.
        """
        if not getattr(self, "w_active", False):
            return 0, 0
        idx = self.w_level - 1
        pct = self.W_PCT[idx] + 0.00015 * self.total_ap   # 100AP당 +1.5%
        return 0, pct * target.max_hp

    def init_combat_state(self, skill_plan=None):
        super().init_combat_state(skill_plan)   # _combat_time=0, current_mana=total_mana
        self.cooldowns_remaining = {"q": 0.0, "w": 0.0, "e": 0.0, "r": 0.0}
        self.w_active = False
        self.w_end_time = 0.0
        # (Q 셔레드·R 스택 상태는 Task 3/4에서 init에 추가)
        plan = skill_plan or {}
        auto_cfg = plan.get("auto_cast", {})
        self.auto_skill_enabled = {k: auto_cfg.get(k, True) for k in ("q", "w", "e", "r")}
        self.auto_skill_order = list(plan.get("auto_order", ["w", "q", "e", "r"]))
        self.manual_skill_casts = sorted(list(plan.get("manual_casts", [])), key=lambda x: x[0])
        self.manual_skill_index = 0

    def advance_combat_time(self, delta_time, current_time, target):
        super().advance_combat_time(delta_time, current_time, target)   # regen
        if delta_time > 0:
            for k in self.cooldowns_remaining:
                self.cooldowns_remaining[k] = max(0.0, self.cooldowns_remaining[k] - delta_time)
        if self.w_active and current_time >= self.w_end_time:
            self.w_active = False
        # (Q 셔레드 만료·R 스택 감쇠는 Task 3/4에서 추가)

    def get_time_to_next_state_event(self, current_time):
        cands = []
        if getattr(self, "w_active", False):
            cands.append(max(0.0, self.w_end_time - current_time))
        return min(cands) if cands else float("inf")

    def _can_cast_skill(self, name):
        eps = 1e-9
        if self.cooldowns_remaining.get(name, float("inf")) > eps:
            return False
        if name == "w" and getattr(self, "w_active", False):
            return False
        if not self.can_afford(self._cost(name)):
            return False
        return True

    def _cost(self, name):
        """현재 마나비용. R은 스택 기반 동적(Task 4); 그 외 정적."""
        return self.mana_cost.get(name, 0.0)

    def get_time_to_next_skill_event(self, current_time):
        eps = 1e-9
        cands = []
        if self.manual_skill_index < len(self.manual_skill_casts):
            t, _ = self.manual_skill_casts[self.manual_skill_index]
            cands.append(max(0.0, t - current_time))
        for name, enabled in self.auto_skill_enabled.items():
            if not enabled:
                continue
            if name == "w" and getattr(self, "w_active", False):
                continue
            cd = self.cooldowns_remaining.get(name, float("inf"))
            cands.append(max(0.0, cd, self._afford_in(self._cost(name))))
        valid = [d for d in cands if d >= -eps]
        return max(0.0, min(valid)) if valid else float("inf")

    def pop_due_skill_events(self, current_time, target):
        eps = 1e-9
        events = []
        while self.manual_skill_index < len(self.manual_skill_casts):
            t, name = self.manual_skill_casts[self.manual_skill_index]
            if t > current_time + eps:
                break
            self.manual_skill_index += 1
            if self._can_cast_skill(name):
                events.append(self._cast_skill(name, target, current_time))
        for name in self.auto_skill_order:
            if self.auto_skill_enabled.get(name, False) and self._can_cast_skill(name):
                events.append(self._cast_skill(name, target, current_time))
        return events

    def _cast_skill(self, name, target, time):
        self._combat_time = time
        self.spend_mana(self._cost(name))
        if name == "w":
            self._cast_w(time)
            return ("w", 0.0, 0.0, False)   # 버프 — 직접피해 없음
        # q/e/r는 Task 3/4에서 분기 추가
        return (name, 0.0, 0.0, False)

    def _cast_w(self, time):
        """W 활성: 8초 버프 + 쿨 17s(스킬가속). 마나는 _cast_skill이 차감. [H-KOG-2]"""
        self.w_active = True
        self.w_end_time = time + self.W_DURATION
        self.cooldowns_remaining["w"] = self.apply_haste_to_cooldown(self.W_CD)
        self.cast_spell(time)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m tests.test_cogmaw_w`
Expected: all 4 `PASS`, `ALL PASS`. Also re-run `.venv/bin/python -m tests.test_cogmaw_basic` → still `ALL PASS`.

- [ ] **Step 5: Commit**

```bash
git add adc_sim/champion.py tests/test_cogmaw_w.py
git commit -m "feat(cogmaw): W cooldown-managed %maxHP on-hit buff + event scaffolding"
```

---

### Task 3: Q-active (nuke + armor/MR % shred) and E (nuke)

**Files:**
- Modify: `adc_sim/champion.py` (`CogMaw`: `_cast_q`/`_cast_e`, shred debuff state in `init_combat_state`/`advance_combat_time`, dispatch in `_cast_skill`, shred-expiry in `get_time_to_next_state_event`)
- Test: `tests/test_cogmaw_qe.py`

**Interfaces:**
- Produces: `_cast_q(target, time) -> (0.0, q_magic)` where `q_magic = q_base[idx] + 0.9*total_ap`, and applies an armor+MR `shred_pct[idx]` debuff on `target` for 4.0s (stores delta, restores on expiry). `_cast_e(time) -> (0.0, e_magic)`, `e_magic = e_base[idx] + 0.65*total_ap`. Both dispatched with `is_skill_hit=True`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cogmaw_qe.py`:

```python
"""CogMaw Q-active (nuke+shred) and E (nuke). Run: .venv/bin/python -m tests.test_cogmaw_qe"""
from adc_sim.champion import CogMaw, Target


def test_q_active_damage_and_shred():
    c = CogMaw(level=11, q_level=5); c.init_combat_state()
    tgt = Target(hp=3000, armor=100, magic_resist=80)
    name, p, m, is_hit = c._cast_skill("q", tgt, 0.0)
    assert is_hit is True and p == 0.0
    assert abs(m - (260 + 0.9 * c.total_ap)) < 1e-6, m         # q5 = 260 (+0.9AP)
    # q5 shred = 32% of armor AND mr
    assert abs(tgt.armor - 100 * (1 - 0.32)) < 1e-6, tgt.armor
    assert abs(tgt.magic_resist - 80 * (1 - 0.32)) < 1e-6, tgt.magic_resist


def test_shred_restores_after_4s():
    c = CogMaw(level=11, q_level=5); c.init_combat_state()
    tgt = Target(hp=3000, armor=100, magic_resist=80)
    c._cast_skill("q", tgt, 0.0)
    c.advance_combat_time(4.0 + 1e-6, 4.0 + 1e-6, tgt)
    assert abs(tgt.armor - 100) < 1e-6 and abs(tgt.magic_resist - 80) < 1e-6


def test_e_damage():
    c = CogMaw(level=11, e_level=5); c.init_combat_state()
    name, p, m, is_hit = c._cast_skill("e", Target(hp=3000, armor=100, magic_resist=80), 0.0)
    assert is_hit is True and p == 0.0
    assert abs(m - (230 + 0.65 * c.total_ap)) < 1e-6, m        # e5 = 230 (+0.65AP)


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_") and callable(f):
            f(); print(f"PASS {n}")
    print("ALL PASS")
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m tests.test_cogmaw_qe`
Expected: FAIL — `_cast_skill("q", ...)` currently returns `(name,0,0,False)` (no q branch); shred not applied.

- [ ] **Step 3: Implement Q-active (+shred) and E**

Add Q/E data + methods to `CogMaw`, extend `_cast_skill` dispatch, add shred state to `init_combat_state`/`advance_combat_time`/`get_time_to_next_state_event`. (Shred mirrors Corki `_cast_e`/`_clear_e_debuff`.)

In `__init__` (after the W data) — add Q/E damage data:
```python
        self.q_base = [80.0, 125.0, 170.0, 215.0, 260.0]   # +0.9 AP [H-KOG-4]
        self.q_shred_pct = [0.16, 0.20, 0.24, 0.28, 0.32]  # 방어력+마저 % 감소, 4초
        self.q_shred_dur = 4.0
        self.e_base = [70.0, 110.0, 150.0, 190.0, 230.0]   # +0.65 AP
```

In `init_combat_state`, after `self.w_end_time = 0.0`, add shred state:
```python
        self.shred_target = None
        self.shred_end_time = 0.0
        self.shred_armor = 0.0
        self.shred_mr = 0.0
```

In `advance_combat_time`, after the W-expiry block, add shred expiry:
```python
        if self.shred_target is not None and current_time >= self.shred_end_time:
            self._clear_shred()
```

In `get_time_to_next_state_event`, also consider shred:
```python
        if getattr(self, "shred_target", None) is not None:
            cands.append(max(0.0, self.shred_end_time - current_time))
```

Add the cast + shred methods:
```python
    def _clear_shred(self):
        if self.shred_target is not None:
            self.shred_target.armor += self.shred_armor
            self.shred_target.magic_resist += self.shred_mr
        self.shred_target = None; self.shred_end_time = 0.0
        self.shred_armor = 0.0; self.shred_mr = 0.0

    def _cast_q(self, target, time):
        """Q 액티브: 마법 넛지 + 방어력·마저 %감소 디버프(감소→관통 순서). [H-KOG-4]"""
        idx = self.q_level - 1
        q_magic = self.q_base[idx] + 0.9 * self.total_ap
        # 셔레드: 기존 디버프 복원 후 재적용(중첩 금지)
        if self.shred_target is not None:
            self._clear_shred()
        pct = self.q_shred_pct[idx]
        d_arm = target.armor * pct
        d_mr = target.magic_resist * pct
        target.armor -= d_arm
        target.magic_resist -= d_mr
        self.shred_target = target; self.shred_end_time = time + self.q_shred_dur
        self.shred_armor = d_arm; self.shred_mr = d_mr
        self.cooldowns_remaining["q"] = self.apply_haste_to_cooldown(7.0)
        self.cast_spell(time)
        return 0.0, q_magic

    def _cast_e(self, time):
        """E 공허진흙: 마법 넛지. [H-KOG-4]"""
        idx = self.e_level - 1
        e_magic = self.e_base[idx] + 0.65 * self.total_ap
        self.cooldowns_remaining["e"] = self.apply_haste_to_cooldown(12.0)
        self.cast_spell(time)
        return 0.0, e_magic
```

Extend `_cast_skill` (replace the `# q/e/r는 Task 3/4...` line) with q/e branches:
```python
        if name == "q":
            p, m = self._cast_q(target, time)
            return ("q", p, m, True)
        if name == "e":
            p, m = self._cast_e(time)
            return ("e", p, m, True)
        return (name, 0.0, 0.0, False)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m tests.test_cogmaw_qe`
Expected: `PASS test_e_damage`, `PASS test_q_active_damage_and_shred`, `PASS test_shred_restores_after_4s`, `ALL PASS`. Re-run `tests.test_cogmaw_w` and `tests.test_cogmaw_basic` → still pass.

- [ ] **Step 5: Commit**

```bash
git add adc_sim/champion.py tests/test_cogmaw_qe.py
git commit -m "feat(cogmaw): Q-active nuke + armor/MR %shred, E nuke"
```

---

### Task 4: R — Living Artillery (missing-HP scaling + mana ramp)

**Files:**
- Modify: `adc_sim/champion.py` (`CogMaw`: `_cast_r`, R mana-stack state + dynamic `_cost("r")`, R-stack decay in `advance_combat_time`, dispatch in `_cast_skill`)
- Test: `tests/test_cogmaw_r.py`

**Interfaces:**
- Produces: `_cast_r(target, time) -> (0.0, r_magic)`, `r_magic = (r_base[idx] + 0.75*bonus_ad + r_ap[idx]*total_ap) * mult`, `mult = 2.0 if hp_ratio<=0.40 else 1 + (5/6)*(1-hp_ratio)`, `bonus_ad = max(0, total_ad - base_attack_ad)`. R mana cost ramps: `40 + 40*stacks` (stacks 0..9, cap 400), each cast +1 stack, stack resets after 8s without casting.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cogmaw_r.py`:

```python
"""CogMaw R = missing-HP scaling + mana ramp. Run: .venv/bin/python -m tests.test_cogmaw_r"""
from adc_sim.champion import CogMaw, Target


def _bonus_ad(c):
    return max(0.0, c.total_ad - c.base_attack_ad)


def test_r_full_hp_base_damage():
    c = CogMaw(level=16, r_level=3); c.init_combat_state()
    tgt = Target(hp=2000, armor=80, magic_resist=60)   # full hp -> mult 1.0
    name, p, m, is_hit = c._cast_skill("r", tgt, 0.0)
    expected = (180 + 0.75 * _bonus_ad(c) + 0.45 * c.total_ap) * 1.0   # r3 base 180, ap 0.45
    assert is_hit is True and abs(m - expected) < 1e-6, (m, expected)


def test_r_execute_below_40pct_doubles():
    c = CogMaw(level=16, r_level=3); c.init_combat_state()
    tgt = Target(hp=2000, armor=80, magic_resist=60); tgt.current_hp = 0.39 * 2000
    name, p, m, is_hit = c._cast_skill("r", tgt, 0.0)
    expected = (180 + 0.75 * _bonus_ad(c) + 0.45 * c.total_ap) * 2.0
    assert abs(m - expected) < 1e-6, (m, expected)


def test_r_mana_ramps_per_consecutive_cast():
    c = CogMaw(level=16, r_level=3); c.init_combat_state()
    tgt = Target(hp=9_000_000, armor=0, magic_resist=0)   # never dies; mana is huge
    c.base_mana = 100000; c.init_combat_state()            # ensure affordable
    assert c._cost("r") == 40.0                            # first cast: 40
    c._cast_skill("r", tgt, 0.0)
    assert c._cost("r") == 80.0                            # next: +40
    c._cast_skill("r", tgt, 0.1)
    assert c._cost("r") == 120.0


def test_r_stack_decays_after_8s():
    c = CogMaw(level=16, r_level=3); c.base_mana = 100000; c.init_combat_state()
    tgt = Target(hp=9_000_000, armor=0, magic_resist=0)
    c._cast_skill("r", tgt, 0.0)
    assert c._cost("r") == 80.0
    c.advance_combat_time(8.0 + 1e-6, 8.0 + 1e-6, tgt)
    assert c._cost("r") == 40.0                            # decayed back to base


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_") and callable(f):
            f(); print(f"PASS {n}")
    print("ALL PASS")
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m tests.test_cogmaw_r`
Expected: FAIL — no `r` branch in `_cast_skill`; `_cost("r")` returns static 0.0 (no ramp).

- [ ] **Step 3: Implement R + mana ramp**

In `__init__` (after E data) add R data:
```python
        self.r_base = [100.0, 140.0, 180.0]
        self.r_ap = [0.35, 0.40, 0.45]
        self.r_bonus_ad = 0.75
        self.r_cd = [2.0, 1.5, 1.0]
        self.r_mana_base = 40.0
        self.r_mana_step = 40.0
        self.r_mana_max_stacks = 9
        self.r_stack_window = 8.0
```

In `init_combat_state` (after shred state) add R-stack state:
```python
        self.r_stacks = 0
        self.r_last_cast_time = -999.0
```

Override `_cost` so R is dynamic (replace the Task-2 `_cost`):
```python
    def _cost(self, name):
        """현재 마나비용. R은 스택 램프(40 + 40*stacks, ≤400). [H-KOG-5]"""
        if name == "r":
            stacks = min(self.r_mana_max_stacks, max(0, self.r_stacks))
            return self.r_mana_base + self.r_mana_step * stacks
        return self.mana_cost.get(name, 0.0)
```

In `advance_combat_time` (after shred-expiry) add R-stack decay:
```python
        if self.r_stacks > 0 and current_time - self.r_last_cast_time >= self.r_stack_window:
            self.r_stacks = 0
```

Add `_cast_r` (note: `_cast_skill` spends `_cost("r")` BEFORE calling this, so increment the stack AFTER the spend — see Step 4 ordering note):
```python
    def _cast_r(self, target, time):
        """R: (base + 0.75·추가AD + apMin·AP) × 잃은체력 배율. [H-KOG-5]

        배율: 대상 HP≤40% → 2.0, 그 외 1 + (5/6)·잃은체력비율(40%HP서 1.5 도달).
        """
        idx = self.r_level - 1
        bonus_ad = max(0.0, self.total_ad - self.base_attack_ad)
        base = self.r_base[idx] + self.r_bonus_ad * bonus_ad + self.r_ap[idx] * self.total_ap
        hp_ratio = target.current_hp / target.max_hp if target.max_hp > 0 else 1.0
        if hp_ratio <= 0.40:
            mult = 2.0
        else:
            mult = 1.0 + (5.0 / 6.0) * (1.0 - hp_ratio)
        self.cooldowns_remaining["r"] = self.apply_haste_to_cooldown(self.r_cd[idx])
        self.cast_spell(time); self.cast_ultimate(time)
        return 0.0, base * mult
```

Extend `_cast_skill` r branch. **Ordering matters:** `_cast_skill` already did `self.spend_mana(self._cost(name))` at the top using the CURRENT stack count. After dispatching R, increment the stack + stamp the time so the NEXT cast costs more:
```python
        if name == "r":
            p, m = self._cast_r(target, time)
            self.r_stacks = min(self.r_mana_max_stacks, self.r_stacks + 1)
            self.r_last_cast_time = time
            return ("r", p, m, True)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m tests.test_cogmaw_r`
Expected: all 4 `PASS`, `ALL PASS`. Re-run `tests.test_cogmaw_qe`, `tests.test_cogmaw_w`, `tests.test_cogmaw_basic` → still pass.

- [ ] **Step 5: Commit**

```bash
git add adc_sim/champion.py tests/test_cogmaw_r.py
git commit -m "feat(cogmaw): R missing-HP scaling + mana-stack ramp"
```

---

### Task 5: `simulations/cogmaw.py` — core simulate function

**Files:**
- Create: `adc_sim/simulations/cogmaw.py`
- Test: `tests/test_cogmaw_sim.py`

**Interfaces:**
- Produces: `CORE_TARGET_STATS` (reuse Ashe/KaiSa values, tiers 1–5), `CORE_COGMAW_LEVELS` (1:lvl9,2:11,3:13,4:15,5:17), `build_target_for_core(tier)`, `simulate_cogmaw_core_path(full_path, core_tier, doran_key="doranblade", boots_key="berserker", rune_as_bonus=0.0) -> (dps, total_cost)`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cogmaw_sim.py`:

```python
"""CogMaw core sim. Run: .venv/bin/python -m tests.test_cogmaw_sim"""
from adc_sim.simulations.cogmaw import simulate_cogmaw_core_path


def test_simulate_returns_positive_dps_and_cost():
    dps, cost = simulate_cogmaw_core_path(("guinsoo", "kraken", "nashor", "terminus"), 4)
    assert dps > 0 and cost > 0


def test_dps_monotonic_across_cores():
    path = ("guinsoo", "kraken", "nashor", "terminus")
    d1, _ = simulate_cogmaw_core_path(path, 1)
    d4, _ = simulate_cogmaw_core_path(path, 4)
    assert d4 > d1   # more items + higher level + tankier target, but net DPS up


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_") and callable(f):
            f(); print(f"PASS {n}")
    print("ALL PASS")
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m tests.test_cogmaw_sim`
Expected: FAIL — `ModuleNotFoundError: adc_sim.simulations.cogmaw`.

- [ ] **Step 3: Create the core sim module**

Create `adc_sim/simulations/cogmaw.py`. Mirror the top of `kaisa.py` (imports, CORE_TARGET_STATS, build_target_for_core, registry usage). Cog'Maw casts W/Q/E/R on cooldown (skill_plan auto), W kept up via its own recast.

```python
from adc_sim.champion import CogMaw, Target
import matplotlib.pyplot as plt
from adc_sim.runes import LethalTempo, CutDown
from adc_sim.engine import run_simulation
from adc_sim.data.items_registry import create_item_from_key
from adc_sim.data.items_data import ADC_PACKAGES

# 코어 단계별 고정 타겟 (Ashe/KaiSa 시뮬과 동일)
CORE_TARGET_STATS = {
    1: {"hp": 1700, "armor": 50, "mr": 25},
    2: {"hp": 1900, "armor": 70, "mr": 30},
    3: {"hp": 2400, "armor": 100, "mr": 50},
    4: {"hp": 2600, "armor": 120, "mr": 70},
    5: {"hp": 3000, "armor": 150, "mr": 90},
}
CORE_COGMAW_LEVELS = {1: {"level": 9}, 2: {"level": 11}, 3: {"level": 13},
                      4: {"level": 15}, 5: {"level": 17}}


def build_target_for_core(core_tier):
    s = CORE_TARGET_STATS[core_tier]
    return Target(hp=s["hp"], armor=s["armor"], magic_resist=s["mr"],
                  bonus_hp=max(0, s["hp"] - 1500))


def _skill_levels_for_core(core_tier):
    """코어별 스킬레벨 가정: W 선마, 그 다음 Q. R은 6렙부터(tier1=lvl9 → r 가능)."""
    # 단순화: q/w/e는 코어가 오를수록 최대로, r은 레벨 기반.
    lvl = CORE_COGMAW_LEVELS[core_tier]["level"]
    w = min(5, max(1, core_tier + 1))
    q = min(5, max(1, core_tier))
    e = min(5, max(1, core_tier - 1)) if core_tier > 1 else 1
    r = 1 if lvl < 11 else (2 if lvl < 16 else 3)
    return q, w, e, r


def simulate_cogmaw_core_path(full_path, core_tier, doran_key="doranblade",
                              boots_key="berserker", rune_as_bonus=0.0):
    """Cog'Maw DPS + total gold for a core timing. W/Q/E/R 쿨마다 시전(마나 바운드)."""
    target = build_target_for_core(core_tier)
    lvl = CORE_COGMAW_LEVELS[core_tier]["level"]
    q, w, e, r = _skill_levels_for_core(core_tier)
    cog = CogMaw(level=lvl, q_level=q, w_level=w, e_level=e, r_level=r)
    cog.set_rune(LethalTempo())
    cog.set_sub_rune(CutDown())

    items = ([create_item_from_key(doran_key)] if doran_key else []) + [create_item_from_key(boots_key)]
    for key in full_path[:core_tier]:
        items.append(create_item_from_key(key))
    total_cost = 0
    for it in items:
        total_cost += it.cost
        cog.add_item(it)
    cog.bonus_as_percent += rune_as_bonus

    # W를 t=0에 시전(버프 시작), 이후 Q/E/R + W 재시전 모두 쿨마다 자동.
    skill_plan = {
        "manual_casts": [(0.0, "w")],
        "auto_cast": {"q": True, "w": True, "e": True, "r": True},
        "auto_order": ["w", "q", "e", "r"],
    }
    _, dps, _ = run_simulation(cog, target, verbose=False, skill_plan=skill_plan)
    return dps, total_cost


if __name__ == "__main__":
    # Task 6에서 랭킹·표·그래프 추가
    d, c = simulate_cogmaw_core_path(("guinsoo", "kraken", "nashor", "terminus"), 4)
    print(f"[smoke] 4-core guinsoo-kraken-nashor-terminus: DPS {d:.1f} / Gold {c}")
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m tests.test_cogmaw_sim`
Expected: `PASS test_simulate_returns_positive_dps_and_cost`, `PASS test_dps_monotonic_across_cores`, `ALL PASS`.
Then a manual smoke: `.venv/bin/python -m adc_sim.simulations.cogmaw` → prints one `[smoke]` line, no traceback, no plot window.

- [ ] **Step 5: Commit**

```bash
git add adc_sim/simulations/cogmaw.py tests/test_cogmaw_sim.py
git commit -m "feat(cogmaw): dedicated sim — core simulate_cogmaw_core_path"
```

---

### Task 6: `simulations/cogmaw.py` — 4-core build ranking + table + graph

**Files:**
- Modify: `adc_sim/simulations/cogmaw.py` (add `get_cogmaw_4core_top1_build`, `build_cogmaw_core_report_meta`, and a `__main__` that prints the ranked table + shows a matplotlib graph)
- Test: `tests/test_cogmaw_ranking.py`

**Interfaces:**
- Produces: `get_cogmaw_4core_top1_build() -> {"path","doran","boots","rune_as","pkg_label","score","control_path",...}` and `build_cogmaw_core_report_meta(full_path, core_tier) -> dict`. Mirrors `kaisa.get_kaisa_4core_top1_build` (read it as the template).

- [ ] **Step 1: Write the failing test**

Create `tests/test_cogmaw_ranking.py`:

```python
"""CogMaw 4-core ranking. Run: .venv/bin/python -m tests.test_cogmaw_ranking"""
from adc_sim.simulations.cogmaw import get_cogmaw_4core_top1_build


def test_top1_has_control_in_search_and_score():
    top1 = get_cogmaw_4core_top1_build()
    assert isinstance(top1["path"], tuple) and len(top1["path"]) == 4
    assert top1["score"] > 0
    # control build must exist in the search space
    assert tuple(sorted(top1["control_path"])) == tuple(sorted(("kraken", "guinsoo", "nashor", "terminus")))


if __name__ == "__main__":
    test_top1_has_control_in_search_and_score()
    print("PASS test_top1_has_control_in_search_and_score")
    print("ALL PASS")
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m tests.test_cogmaw_ranking`
Expected: FAIL — `ImportError: cannot import name 'get_cogmaw_4core_top1_build'`.

- [ ] **Step 3: Add the ranking + report-meta + `__main__`**

Read `adc_sim/simulations/kaisa.py` `get_kaisa_4core_top1_build` (and its `__main__`) as the exact template. Replicate its structure — candidate pools, distinct-item + pen-exclusive constraints, per-(path,pkg) simulate over tiers 1–4, dedupe by sorted-combo (best weighted DPG), control via the canonical control path, `rel_dpg_score = sum(core_weights[i] * (dpg[i]/baseline_dpg[i]) * 100)` with weights 5:4:3:3 — with these **Cog'Maw-specific deltas**:

- Candidate pools (Cog'Maw on-hit + AP):
  ```python
  core1 = core2 = ["guinsoo", "kraken", "nashor", "terminus", "bot", "rfc", "statikk", "storm", "pd", "ie", "yuntal"]
  core3 = ["guinsoo", "nashor", "terminus", "bot", "kraken", "rfc", "pd", "ie", "ldr", "rabadon"]
  core4 = ["nashor", "rabadon", "shadowflame", "ie", "ldr", "mortal", "terminus", "bot", "guinsoo", "kraken", "pd"]
  pen_exclusive = {"terminus", "ldr", "mortal"}
  ```
- Control build (must be reachable in the search; raise `RuntimeError` if absent, mirroring the house rule):
  ```python
  CONTROL_PATH = ("kraken", "guinsoo", "nashor", "terminus")
  ```
- Use `simulate_cogmaw_core_path(path, tier, **pkg_kw)` for each `pkg` in `ADC_PACKAGES` (same as kaisa). Cog'Maw has no yuntal-crit branching subtlety beyond what the registry handles — if `yuntal` is in a path, create it via `create_item_from_key("yuntal")` (default crit), same as the registry default; no special-casing required for v1 (note this as [H-KOG-6]).
- `build_cogmaw_core_report_meta(full_path, core_tier)` mirrors `kaisa.build_kaisa_core_report_meta` (champion="CogMaw", active_path = path[:tier], etc.).
- `__main__`: print the ranked table (RelDPG, DPS, Gold per core) and `plt.show()` the DPS-vs-gold curves — same output conventions as `kaisa.py`'s `__main__`. Headless note: `plt.show()` blocks.

Implement these by adapting kaisa.py's code with the deltas above. Keep `get_cogmaw_4core_top1_build` cached in a module global like `_KAISA_4CORE_TOP1_CACHE`.

- [ ] **Step 4: Run to verify it passes + integration run**

Run: `.venv/bin/python -m tests.test_cogmaw_ranking`
Expected: `PASS test_top1_has_control_in_search_and_score`, `ALL PASS`.
Integration (headless-safe — set Agg so `plt.show()` doesn't block): `MPLBACKEND=Agg .venv/bin/python -m adc_sim.simulations.cogmaw` → prints the ranked table with a `[CTRL]`/control row present and per-core DPG/DPS values; exits 0. Visually sanity-check: on-hit/AP builds (guinsoo/nashor/rabadon) should rank well for Cog'Maw.

- [ ] **Step 5: Commit**

```bash
git add adc_sim/simulations/cogmaw.py tests/test_cogmaw_ranking.py
git commit -m "feat(cogmaw): 4-core build ranking (rel_dpg 5:4:3:3) + table + graph"
```

---

## Self-Review

**Spec coverage (spec §4):** stats/mana §4.1 → T1; W cooldown-managed on-hit §4.2 → T2; Q passive-AS §4.1.2/§4.2 → T1; Q-active nuke+shred + E §4.2 → T3; R missing-HP scaling + mana ramp §4.2 → T4; sim file §4.3 (target/levels/simulate) → T5; 4-core ranking + control + table + graph §4.3 → T6. Hypotheses H-KOG-1..6 cited in code comments. `power_compare` integration is intentionally out of scope (spec §1.3).

**Placeholder scan:** Task 6 references kaisa.py's search code as the template rather than re-transcribing ~150 lines — the Cog'Maw-specific deltas (pools, control, champion ctor) are spelled out explicitly, and the structural algorithm is "replicate kaisa's, which is the established house pattern." This is a deliberate pattern-reuse instruction, not a vague placeholder; every Cog'Maw-specific value is concrete.

**Type consistency:** `get_champion_onhit -> (phys, magic)`; `_cast_skill -> (name, phys, magic, is_skill_hit)` (W `False`, Q/E/R `True`); `_cost(name)` is the single source of mana cost (static for q/w/e, dynamic for r) used uniformly in `_can_cast_skill`/`get_time_to_next_skill_event`/`_cast_skill`; `simulate_cogmaw_core_path(full_path, core_tier, ...) -> (dps, cost)` matches the test and the power_compare-ready signature used by later phases.

**Ordering note:** R mana is spent in `_cast_skill` (via `_cost("r")`) BEFORE `_cast_r` runs and BEFORE the stack increments — so the Nth consecutive cast pays `40+40*(N-1)`, and the stack/`r_last_cast_time` update happens after, making the (N+1)th cost one step more. Verified by `test_r_mana_ramps_per_consecutive_cast`.
