# Ezreal 챔피언 추가 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 이벤트 기반 엔진 위에 이즈리얼(평타 + Q/W/E 풀 로테이션, R 제외)을 추가하고 4코어 빌드 랭킹을 산출한다.

**Architecture:** `adc_sim/champion.py`에 `Ezreal(Champion)`를 **추가만**(기존 클래스/엔진/아이템 무수정). Corki/Kai'Sa의 이벤트 인터페이스(`pop_due_skill_events` 등)를 미러링. Q는 스킬 이벤트로 방출하되, 온힛 충실도를 위해 `_cast_q`에서 allow-list 온힛을 로컬 합산(Manamune/Muramana·룬은 엔진 스킬경로가 자동 처리). `adc_sim/simulations/ezreal.py`는 `corki.py`를 템플릿으로 빌드 탐색·랭킹.

**Tech Stack:** Python 3.10, `.venv/bin/python`, matplotlib(그래프). 표준 라이브러리만 추가 사용. **pytest 미사용**(프로젝트에 테스트 프레임워크 없음).

## Global Constraints
- 인터프리터는 항상 **`.venv/bin/python`**. 시뮬은 repo 루트에서 `-m`으로 실행.
- **엔진(`engine.py`)·기존 아이템(`items.py`)·기존 챔피언 클래스 무수정**(AGENTS.md §5 최소변경). `champion.py`에는 `Ezreal` 클래스 **추가만**.
- 모든 신규 메커니즘은 docstring/주석에 **`[Hypothesis]`** 태깅(AGENTS.md §4). 수치 출처는 `docs/superpowers/specs/2026-06-24-ezreal-design.md`.
- **검증은 pytest 미사용**: scratchpad에 assert 기반 런너블 스크립트를 작성해 `.venv/bin/python <script>`로 실행(프로젝트 관례). 커밋 산출물은 구현 코드. 검증 스크립트는 비커밋(ephemeral).
- 커밋 메시지 말미: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- 확정 수치(스펙 §3): base_ad 60(+3.75/lvl), base_as 0.625, as_ratio 0.625, as_growth 2.5, range 550, mana 375(+70). 패시브 +10%/스택·최대5·6초. Q base 20/45/70/95/120 +1.30×**총AD** +0.15 AP, **비치명**, 적중 시 전 스킬 −1.5초, 온힛 적용. W base 80/135/190/245/300 +1.0 추가AD +0.9 AP. E base 80/130/180/230/280 +0.6 추가AD +0.75 AP. R 제외.
- Q 온힛 allow-list(이름): `Kraken Slayer`, `Blade of the Ruined King`, `Guinsoo's Rageblade`, `Terminus`, `Nashor's Tooth`, `Wit's End`. (Manamune/주문검/에너자이즈드 제외.)
- 컨트롤 빌드: `trinity-muramana-ie-ldr`.

> **SCRATCH_DIR** (검증 스크립트 위치, 비커밋):
> `/private/tmp/claude-501/-Users-gimdohyeon-PycharmProjects-ADC-DPS-calculator/2189d742-911a-4f12-93e2-4e6b69b35675/scratchpad`

---

## File Structure
- **Modify** `adc_sim/champion.py`: 파일 끝에 `class Ezreal(Champion)` 추가(Task 1~3). 기존 코드 무변경.
- **Create** `adc_sim/simulations/ezreal.py`: 빌드 탐색·랭킹·표·그래프(Task 4). `corki.py` 미러링.
- (검증) **Create(ephemeral)** `SCRATCH_DIR/verify_ezreal_*.py`: assert 런너(비커밋).

---

## Task 1: `Ezreal` 클래스 — 스탯 + 패시브(Rising Spell Force) + 평타

**Files:**
- Modify: `adc_sim/champion.py` (파일 끝에 클래스 추가)
- Verify: `SCRATCH_DIR/verify_ezreal_t1.py` (ephemeral)

**Interfaces:**
- Consumes: `Champion`(base), `Target` (champion.py 기존).
- Produces: `Ezreal(level=1,q_level=5,w_level=5,e_level=5,r_level=3)`; 속성 `spell_stacks`,`max_spell_stacks`,`spell_stack_as`,`spell_stack_duration`,`stack_expire_time`,`_stack_as_applied`,`cooldowns_remaining`,`q_base/q_cd/q_total_ad_ratio/q_ap_ratio/q_cd_refund`,`w_*`,`e_*`,`auto_skill_enabled`,`auto_skill_order`,`manual_skill_casts`; 메서드 `_bonus_ad()`,`_sync_stack_as()`,`_add_spell_stack(time)`,`_expire_stacks_if_due(time)`,`init_combat_state`,`advance_combat_time`,`get_time_to_next_state_event`,`get_one_hit_damage`. (Task1 한정) `get_time_to_next_skill_event`→inf, `pop_due_skill_events`→[].

- [ ] **Step 1: 검증 스크립트 작성(실패 예상)** — `SCRATCH_DIR/verify_ezreal_t1.py`

```python
from adc_sim.champion import Ezreal, Target
from adc_sim.engine import run_simulation

# 1) 인스턴스화 + 기본 스탯
ez = Ezreal(level=11, q_level=5)
assert ez.name == "Ezreal"
assert abs(ez.base_attack_ad - (60 + 3.75 * 10)) < 1e-6, ez.base_attack_ad  # lvl11
assert abs(ez.base_as - 0.625) < 1e-6
print("[ok] stats: base_attack_ad(lv11)=%.2f base_as=%.3f range=%d" % (ez.base_attack_ad, ez.base_as, ez.range))

# 2) 패시브 스택: add → 공속 증가, 6초 후 decay → 환원
ez2 = Ezreal(level=11)
ez2.init_combat_state(None)
as0 = ez2.current_attack_speed
ez2._add_spell_stack(0.0); ez2._add_spell_stack(0.0)  # 2 stacks
as2 = ez2.current_attack_speed
assert as2 > as0, (as0, as2)
assert ez2.spell_stacks == 2
# 5스택 캡
for _ in range(10):
    ez2._add_spell_stack(0.0)
assert ez2.spell_stacks == 5, ez2.spell_stacks
# 만료(6초 경과) → 0스택, 공속 환원
ez2._expire_stacks_if_due(6.0 + 1e-9)
assert ez2.spell_stacks == 0
assert abs(ez2.current_attack_speed - as0) < 1e-9, (as0, ez2.current_attack_speed)
print("[ok] passive stacks: as0=%.3f as2=%.3f cap=5 decay->as0" % (as0, as2))

# 3) 평타 전용 시뮬(스킬 미발동) → DPS 양수·유한
target = Target(hp=1900, armor=70, magic_resist=30, bonus_hp=400)
_, dps, kt = run_simulation(ez, target, verbose=False,
                            skill_plan={"auto_cast": {"q": False, "w": False, "e": False}, "auto_order": []})
assert dps > 0 and dps != float("inf"), dps
print("[ok] auto-only sim: dps=%.1f kill_time=%.2f" % (dps, kt))
print("ALL T1 PASS")
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python SCRATCH_DIR/verify_ezreal_t1.py` (SCRATCH_DIR는 위 절대경로로 치환)
Expected: `ImportError: cannot import name 'Ezreal'` (아직 클래스 없음).

- [ ] **Step 3: `Ezreal` 클래스 추가(Task1 범위)** — `adc_sim/champion.py` 파일 **맨 끝**에 추가

```python
class Ezreal(Champion):
    """이즈리얼 — 스킬샷 포크형 원딜. [Hypothesis 다수 — 스펙 §9 참조]

    모델: 평타 연속 + Q/W/E 쿨마다 시전(R 제외). 마나 자원 미모델(무한마나)이나
    마나무네 스택은 on_hit/on_skill_hit로 정확 충전됨.
    - 패시브 Rising Spell Force[H]: 스킬 적중당 공속 +10%/스택, 최대 5, 6초(적중 시 갱신).
    - Q Mystic Shot[H]: 물리(비치명) base + 1.30*총AD + 0.15*AP. 적중 시 전 스킬 −1.5초.
      온힛 적용(Manamune/Muramana·룬=엔진 스킬경로; Kraken/BotRK/Guinsoo/Terminus/Nashor's/
      Wit's End=allow-list 로컬). 주문검은 장전만(다음 평타서 발동).
    - W Essence Flux[H]: 마법 base + 1.0*추가AD + 0.9*AP(단일 더미 즉시 기폭 단순화).
    - E Arcane Shift[H]: 마법 base + 0.6*추가AD + 0.75*AP.
    수치/가설 출처: docs/superpowers/specs/2026-06-24-ezreal-design.md
    """

    # Q 온힛 allow-list(이름 기준). Manamune(스킬경로)/주문검(평타)/에너자이즈드(평타) 제외.
    Q_ONHIT_ALLOW = {
        "Kraken Slayer", "Blade of the Ruined King", "Guinsoo's Rageblade",
        "Terminus", "Nashor's Tooth", "Wit's End",
    }

    def __init__(self, level=1, q_level=5, w_level=5, e_level=5, r_level=3):
        super().__init__(
            name="Ezreal", base_ad=60, base_as=0.625, as_ratio=0.625,
            as_growth=2.5, base_range=550, level=level, ad_growth=3.75,
        )
        # 보관(비-DPS): 미래 1대1 모델용
        self.base_hp = 600; self.hp_growth = 102
        self.base_mana = 375; self.mana_growth = 70
        self.base_armor = 24; self.armor_growth = 4.2
        self.base_mr = 30; self.mr_growth = 1.3

        self.q_level = q_level; self.w_level = w_level
        self.e_level = e_level; self.r_level = r_level

        # 패시브 Rising Spell Force [H]
        self.spell_stacks = 0
        self.max_spell_stacks = 5
        self.spell_stack_as = 0.10        # 스택당 공속
        self.spell_stack_duration = 6.0
        self.stack_expire_time = 0.0
        self._stack_as_applied = 0.0      # 현재 bonus_as_percent에 반영된 패시브 공속(환원용)

        # Q/W/E 데이터 [H]
        self.q_cd = [5.5, 5.25, 5.0, 4.75, 4.5]
        self.q_base = [20.0, 45.0, 70.0, 95.0, 120.0]
        self.q_total_ad_ratio = 1.30
        self.q_ap_ratio = 0.15
        self.q_cd_refund = 1.5

        self.w_cd = [8.0, 8.0, 8.0, 8.0, 8.0]
        self.w_base = [80.0, 135.0, 190.0, 245.0, 300.0]
        self.w_bonus_ad_ratio = 1.0
        self.w_ap_ratio = 0.9

        self.e_cd = [26.0, 23.0, 20.0, 17.0, 14.0]
        self.e_base = [80.0, 130.0, 180.0, 230.0, 280.0]
        self.e_bonus_ad_ratio = 0.6
        self.e_ap_ratio = 0.75

        # 자동 시전(R 제외)
        self.auto_cast_q = True; self.auto_cast_w = True; self.auto_cast_e = True
        self.cooldowns_remaining = {"q": 0.0, "w": 0.0, "e": 0.0}
        self.manual_skill_casts = []
        self.manual_skill_index = 0
        self.auto_skill_enabled = {"q": True, "w": True, "e": True}
        self.auto_skill_order = ["q", "w", "e"]

    # ---- 추가AD(W/E 계수용) ----
    def _bonus_ad(self):
        """아이템+동적(마나무네 경탄 등) 추가 AD = total_ad - 현재레벨 기본 AD."""
        return max(0.0, self.total_ad - self.base_attack_ad)

    # ---- 패시브 스택 ----
    def _sync_stack_as(self):
        """현재 스택 수에 맞춰 bonus_as_percent 보정(이전 적용분 환원 후 재적용)."""
        target_as = self.spell_stacks * self.spell_stack_as
        delta = target_as - self._stack_as_applied
        if delta != 0.0:
            self.bonus_as_percent += delta
            self._stack_as_applied = target_as

    def _add_spell_stack(self, time):
        """스킬 적중 1회 → 스택 +1(캡), 만료시간 갱신, 공속 반영. [H]"""
        self.spell_stacks = min(self.max_spell_stacks, self.spell_stacks + 1)
        self.stack_expire_time = time + self.spell_stack_duration
        self._sync_stack_as()

    def _expire_stacks_if_due(self, time):
        """만료시간 경과 시 스택 0 + 공속 환원."""
        if self.spell_stacks > 0 and time >= self.stack_expire_time:
            self.spell_stacks = 0
            self._sync_stack_as()

    # ---- 이벤트 인터페이스 ----
    def init_combat_state(self, skill_plan=None):
        super().init_combat_state(skill_plan)
        self.cooldowns_remaining = {"q": 0.0, "w": 0.0, "e": 0.0}
        # 패시브 초기화(이전 전투 잔여 공속 환원)
        self.spell_stacks = 0
        self.stack_expire_time = 0.0
        self._sync_stack_as()  # _stack_as_applied 만큼 환원
        self._stack_as_applied = 0.0

        plan = skill_plan or {}
        auto_cfg = plan.get("auto_cast", {})
        self.auto_skill_enabled = {
            "q": auto_cfg.get("q", self.auto_cast_q),
            "w": auto_cfg.get("w", self.auto_cast_w),
            "e": auto_cfg.get("e", self.auto_cast_e),
        }
        self.auto_skill_order = list(plan.get("auto_order", ["q", "w", "e"]))
        self.manual_skill_casts = sorted(list(plan.get("manual_casts", [])), key=lambda x: x[0])
        self.manual_skill_index = 0

    def advance_combat_time(self, delta_time, current_time, target):
        super().advance_combat_time(delta_time, current_time, target)
        if delta_time > 0:
            for k in self.cooldowns_remaining:
                self.cooldowns_remaining[k] = max(0.0, self.cooldowns_remaining[k] - delta_time)
        self._expire_stacks_if_due(current_time)

    def get_time_to_next_state_event(self, current_time):
        if self.spell_stacks > 0:
            return max(0.0, self.stack_expire_time - current_time)
        return float("inf")

    # Task1 한정 스텁(Task2에서 실제 구현으로 교체)
    def get_time_to_next_skill_event(self, current_time):
        return float("inf")

    def pop_due_skill_events(self, current_time, target):
        return []

    def get_one_hit_damage(self, target, time=0):
        # 평타 시점에 패시브 만료 동기화 후 부모 평타 로직(치명/주문검발동/온힛/증폭).
        self._expire_stacks_if_due(time)
        return super().get_one_hit_damage(target, time)
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python SCRATCH_DIR/verify_ezreal_t1.py`
Expected: `[ok] stats...`, `[ok] passive stacks...`, `[ok] auto-only sim...`, `ALL T1 PASS`.

- [ ] **Step 5: 커밋**

```bash
git add adc_sim/champion.py
git commit -m "이즈리얼 클래스 1: 스탯+패시브(Rising Spell Force)+평타

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Q — Mystic Shot (비치명 물리 + 온힛 allow-list + 쿨 −1.5초 루프 + 패시브 스택 + 주문검 장전)

**Files:**
- Modify: `adc_sim/champion.py` (`Ezreal`의 Task1 스텁 2개 교체 + 메서드 추가)
- Verify: `SCRATCH_DIR/verify_ezreal_t2.py` (ephemeral)

**Interfaces:**
- Consumes: Task1 산출물.
- Produces: `_can_cast(name)→bool`, `_cast_skill(name,target,time)→(name,phys,magic,is_hit)`, `_cast_q(target,time)→(phys,magic)`, `_assemble_q_onhit(target)→(phys,magic)`; 실제 `get_time_to_next_skill_event`/`pop_due_skill_events`.

- [ ] **Step 1: 검증 스크립트 작성(실패 예상)** — `SCRATCH_DIR/verify_ezreal_t2.py`

```python
from adc_sim.champion import Ezreal, Target
from adc_sim.engine import run_simulation
from adc_sim.data.items_registry import create_item_from_key

# 1) Q 기본 물리: base + 1.30*총AD + 0.15*AP (비치명, 온힛 없음 상태)
ez = Ezreal(level=11, q_level=5)
ez.crit_chance = 1.0  # 치명타 100%여도 Q는 비치명이어야 함
ez.init_combat_state({"auto_cast": {"q": False, "w": False, "e": False}, "auto_order": []})
exp_q = 120.0 + 1.30 * ez.total_ad + 0.15 * ez.total_ap
p, m = ez._cast_q(Target(hp=9999, armor=0, magic_resist=0), 0.0)
assert abs(p - exp_q) < 1e-6, (p, exp_q)   # 치명타 미적용 확인
assert m == 0.0, m
print("[ok] Q phys(no-crit)=%.1f (expected %.1f)" % (p, exp_q))

# 2) 쿨 −1.5초 루프: Q 시전 시 q/w/e 전부 −1.5초
ez2 = Ezreal(level=11, q_level=5)
ez2.init_combat_state({"auto_cast": {"q": False, "w": False, "e": False}, "auto_order": []})
ez2.cooldowns_remaining = {"q": 0.0, "w": 8.0, "e": 14.0}
ez2._cast_q(Target(hp=9999, armor=0, magic_resist=0), 0.0)
# q_level=5 → q_cd=4.5 설정 후 −1.5 = 3.0; w=8-1.5=6.5; e=14-1.5=12.5
assert abs(ez2.cooldowns_remaining["q"] - (4.5 - 1.5)) < 1e-6, ez2.cooldowns_remaining
assert abs(ez2.cooldowns_remaining["w"] - 6.5) < 1e-6, ez2.cooldowns_remaining
assert abs(ez2.cooldowns_remaining["e"] - 12.5) < 1e-6, ez2.cooldowns_remaining
print("[ok] Q cd-refund loop:", ez2.cooldowns_remaining)

# 3) 패시브 스택: Q 시전 후 +1
ez3 = Ezreal(level=11, q_level=5)
ez3.init_combat_state({"auto_cast": {"q": False}, "auto_order": []})
assert ez3.spell_stacks == 0
ez3._cast_q(Target(hp=9999, armor=0, magic_resist=0), 0.0)
assert ez3.spell_stacks == 1, ez3.spell_stacks
print("[ok] Q grants passive stack ->", ez3.spell_stacks)

# 4) 온힛 allow-list: Kraken/BotRK는 Q 물리에 합산, 주문검은 Q서 미발동
ez4 = Ezreal(level=11, q_level=5)
ez4.add_item(create_item_from_key("botrk"))      # 현재체력 6% 물리 온힛
ez4.add_item(create_item_from_key("trinity"))    # 주문검(장전만)
ez4.init_combat_state({"auto_cast": {"q": False}, "auto_order": []})
tgt = Target(hp=1000, armor=0, magic_resist=0)
p4, m4 = ez4._cast_q(tgt, 0.0)
exp_q4 = 120.0 + 1.30 * ez4.total_ad + 0.15 * ez4.total_ap
exp_botrk = 1000 * 0.06
assert abs(p4 - (exp_q4 + exp_botrk)) < 1e-6, (p4, exp_q4, exp_botrk)
# 주문검은 장전만(다음 평타서 발동) → Q 직후 last_spellblade_damage == 0
tri = next(it for it in ez4.inventory if it.name == "Trinity Force")
assert tri.last_spellblade_damage == 0.0, tri.last_spellblade_damage
assert tri.is_spellblade_active is True, "Q가 주문검을 장전해야 함"
print("[ok] Q allow-list onhit: +botrk %.1f; spellblade armed(not fired)" % exp_botrk)

# 5) 풀 전투(Q 자동) → DPS 양수, Q가 평타보다 자주 나가는 가속 확인(스모크)
ez5 = Ezreal(level=11, q_level=5)
for k in ("trinity", "muramana", "ie"):
    ez5.add_item(create_item_from_key(k))
_, dps, kt = run_simulation(ez5, Target(hp=2400, armor=100, magic_resist=50, bonus_hp=900),
                            verbose=False,
                            skill_plan={"manual_casts": [(0.0, "q")], "auto_cast": {"q": True, "w": False, "e": False}, "auto_order": ["q"]})
assert dps > 0 and dps != float("inf"), dps
print("[ok] Q-weave sim: dps=%.1f kill_time=%.2f" % (dps, kt))
print("ALL T2 PASS")
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python SCRATCH_DIR/verify_ezreal_t2.py`
Expected: `AttributeError: 'Ezreal' object has no attribute '_cast_q'`.

- [ ] **Step 3: Task1 스텁 2개 교체 + Q 메서드 추가** — `adc_sim/champion.py` `Ezreal` 내부

(3a) `get_time_to_next_skill_event`/`pop_due_skill_events` 스텁을 아래로 **교체**:

```python
    def _can_cast(self, name):
        return self.cooldowns_remaining.get(name, float("inf")) <= 1e-9

    def get_time_to_next_skill_event(self, current_time):
        eps = 1e-9
        candidates = []
        if self.manual_skill_index < len(self.manual_skill_casts):
            t, _ = self.manual_skill_casts[self.manual_skill_index]
            candidates.append(max(0.0, t - current_time))
        for name, enabled in self.auto_skill_enabled.items():
            if enabled:
                candidates.append(max(0.0, self.cooldowns_remaining.get(name, float("inf"))))
        valid = [dt for dt in candidates if dt >= -eps]
        return max(0.0, min(valid)) if valid else float("inf")

    def pop_due_skill_events(self, current_time, target):
        eps = 1e-9
        events = []
        while self.manual_skill_index < len(self.manual_skill_casts):
            t, name = self.manual_skill_casts[self.manual_skill_index]
            if t > current_time + eps:
                break
            self.manual_skill_index += 1
            if self._can_cast(name):
                events.append(self._cast_skill(name, target, current_time))
        for name in self.auto_skill_order:
            if self.auto_skill_enabled.get(name, False) and self._can_cast(name):
                events.append(self._cast_skill(name, target, current_time))
        return events

    def _cast_skill(self, name, target, time):
        if name == "q":
            p, m = self._cast_q(target, time)
            return ("q", p, m, True)
        return (name, 0.0, 0.0, False)
```

(3b) 이어서 Q 메서드 추가:

```python
    def _assemble_q_onhit(self, target):
        """Q에 적용할 평타 온힛 중 allow-list 아이템만 합산. [Hypothesis H-EZ-6]

        - Manamune/Muramana: 엔진 스킬경로(on_skill_hit)가 처리 → 여기서 제외(이중계산 방지).
        - 주문검/에너자이즈드: Q서 미적용(주문검은 _cast_q의 cast_spell로 장전만).
        - proc_count(구인수 팬텀히트)는 평타 경로와 동일하게 allow-list 번들 전체에 적용.
        - 현 allow-list 아이템은 고정(true) 온힛이 없어 (phys,magic)만 합산(검증됨).
        반환: (phys, magic)
        """
        def bundle_once():
            p = 0.0; m = 0.0
            for item in self.inventory:
                if item.name in self.Q_ONHIT_ALLOW:
                    ip, im, _t_base, _t_onhit = item.on_hit(target, self)
                    p += ip; m += im
            return p, m

        proc = 1
        for item in self.inventory:
            if item.name in self.Q_ONHIT_ALLOW and hasattr(item, "get_onhit_proc_count"):
                proc = max(proc, item.get_onhit_proc_count(self))

        phys = 0.0; magic = 0.0
        for _ in range(proc):
            bp, bm = bundle_once()
            phys += bp; magic += bm
        return phys, magic

    def _cast_q(self, target, time):
        """Q Mystic Shot. 물리(비치명) + allow-list 온힛. 적중 시 전 스킬 −1.5초. [H]

        반환: (phys, magic). Manamune/Muramana·룬 스킬훅은 엔진 스킬경로가 자동 처리.
        """
        self._combat_time = time
        idx = self.q_level - 1
        q_phys = self.q_base[idx] + (self.q_total_ad_ratio * self.total_ad) + (self.q_ap_ratio * self.total_ap)

        # allow-list 온힛(주문검/Manamune 제외)
        onhit_p, onhit_m = self._assemble_q_onhit(target)

        # 자기 쿨 설정 후, 적중 쿨 환급(−1.5초)을 전 스킬에 적용(자기 포함)
        self.cooldowns_remaining["q"] = self.apply_haste_to_cooldown(self.q_cd[idx])
        for k in self.cooldowns_remaining:
            self.cooldowns_remaining[k] = max(0.0, self.cooldowns_remaining[k] - self.q_cd_refund)

        # 주문검 장전(다음 평타서 발동)
        self.cast_spell(time)
        # 패시브 스택
        self._add_spell_stack(time)

        return q_phys + onhit_p, onhit_m
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python SCRATCH_DIR/verify_ezreal_t2.py`
Expected: 5개 `[ok]` 라인 + `ALL T2 PASS`.

- [ ] **Step 5: 커밋**

```bash
git add adc_sim/champion.py
git commit -m "이즈리얼 클래스 2: Q(비치명 물리+온힛 allow-list+쿨−1.5루프+주문검장전)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: W(Essence Flux) + E(Arcane Shift) — 단순화 마법 피해 + 패시브 스택 + 주문검 장전

**Files:**
- Modify: `adc_sim/champion.py` (`Ezreal._cast_skill` 확장 + `_cast_w`/`_cast_e` 추가)
- Verify: `SCRATCH_DIR/verify_ezreal_t3.py` (ephemeral)

**Interfaces:**
- Consumes: Task2 산출물.
- Produces: `_cast_w(time)→(phys,magic)`, `_cast_e(time)→(phys,magic)`; `_cast_skill`이 w/e 분기 처리.

- [ ] **Step 1: 검증 스크립트 작성(실패 예상)** — `SCRATCH_DIR/verify_ezreal_t3.py`

```python
from adc_sim.champion import Ezreal, Target
from adc_sim.engine import run_simulation
from adc_sim.data.items_registry import create_item_from_key

# W: 마법 base + 1.0*추가AD + 0.9*AP
ez = Ezreal(level=15, w_level=5, e_level=5)
ez.add_item(create_item_from_key("trinity"))
ez.init_combat_state({"auto_cast": {"q": False, "w": False, "e": False}, "auto_order": []})
exp_w = 300.0 + 1.0 * ez._bonus_ad() + 0.9 * ez.total_ap
pw, mw = ez._cast_w(0.0)
assert pw == 0.0 and abs(mw - exp_w) < 1e-6, (pw, mw, exp_w)
assert ez.spell_stacks == 1, ez.spell_stacks  # W도 패시브 스택
print("[ok] W magic=%.1f (expected %.1f), stack=%d" % (mw, exp_w, ez.spell_stacks))

# E: 마법 base + 0.6*추가AD + 0.75*AP
ez2 = Ezreal(level=15, e_level=5)
ez2.add_item(create_item_from_key("trinity"))
ez2.init_combat_state({"auto_cast": {"q": False, "w": False, "e": False}, "auto_order": []})
exp_e = 280.0 + 0.6 * ez2._bonus_ad() + 0.75 * ez2.total_ap
pe, me = ez2._cast_e(0.0)
assert pe == 0.0 and abs(me - exp_e) < 1e-6, (pe, me, exp_e)
print("[ok] E magic=%.1f (expected %.1f)" % (me, exp_e))

# 풀 로테이션(Q+W+E 자동) 시뮬 → DPS 양수
ez3 = Ezreal(level=13, q_level=5, w_level=5, e_level=3)
for k in ("trinity", "muramana", "ie"):
    ez3.add_item(create_item_from_key(k))
_, dps, kt = run_simulation(ez3, Target(hp=2400, armor=100, magic_resist=50, bonus_hp=900),
                            verbose=False,
                            skill_plan={"manual_casts": [(0.0, "q"), (0.0, "w"), (0.0, "e")],
                                        "auto_cast": {"q": True, "w": True, "e": True},
                                        "auto_order": ["q", "w", "e"]})
assert dps > 0 and dps != float("inf"), dps
print("[ok] full rotation sim: dps=%.1f kill_time=%.2f" % (dps, kt))
print("ALL T3 PASS")
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python SCRATCH_DIR/verify_ezreal_t3.py`
Expected: `AttributeError: 'Ezreal' object has no attribute '_cast_w'`.

- [ ] **Step 3: `_cast_skill` 확장 + W/E 추가** — `adc_sim/champion.py` `Ezreal` 내부

(3a) `_cast_skill`을 아래로 **교체**(w/e 분기 추가):

```python
    def _cast_skill(self, name, target, time):
        if name == "q":
            p, m = self._cast_q(target, time)
            return ("q", p, m, True)
        if name == "w":
            p, m = self._cast_w(time)
            return ("w", p, m, True)
        if name == "e":
            p, m = self._cast_e(time)
            return ("e", p, m, True)
        return (name, 0.0, 0.0, False)
```

(3b) W/E 메서드 추가:

```python
    def _cast_w(self, time):
        """W Essence Flux — 단일 더미 즉시 기폭 단순화. 마법. [H]"""
        self._combat_time = time
        idx = self.w_level - 1
        magic = self.w_base[idx] + (self.w_bonus_ad_ratio * self._bonus_ad()) + (self.w_ap_ratio * self.total_ap)
        self.cooldowns_remaining["w"] = self.apply_haste_to_cooldown(self.w_cd[idx])
        self.cast_spell(time)      # 주문검 장전
        self._add_spell_stack(time)
        return 0.0, magic

    def _cast_e(self, time):
        """E Arcane Shift — 순간이동 후 마법 볼트. [H]"""
        self._combat_time = time
        idx = self.e_level - 1
        magic = self.e_base[idx] + (self.e_bonus_ad_ratio * self._bonus_ad()) + (self.e_ap_ratio * self.total_ap)
        self.cooldowns_remaining["e"] = self.apply_haste_to_cooldown(self.e_cd[idx])
        self.cast_spell(time)      # 주문검 장전
        self._add_spell_stack(time)
        return 0.0, magic
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python SCRATCH_DIR/verify_ezreal_t3.py`
Expected: 3개 `[ok]` 라인 + `ALL T3 PASS`.

- [ ] **Step 5: 커밋**

```bash
git add adc_sim/champion.py
git commit -m "이즈리얼 클래스 3: W/E(단순화 마법피해)+패시브 스택+주문검 장전

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `simulations/ezreal.py` — 4코어 빌드 탐색·랭킹(표+그래프)

**Files:**
- Create: `adc_sim/simulations/ezreal.py`
- Verify: 표준 실행 + `SCRATCH_DIR/verify_ezreal_t4.py` (ephemeral, 그래프 없이 top1만)

**Interfaces:**
- Consumes: `Ezreal`(Task1~3), `run_simulation`, `create_item_from_key`, `DORAN_OPTIONS`/`DORAN_SHORT`.
- Produces: `CORE_TARGET_STATS`, `CORE_LEVELS`, `EZREAL_SKILL_LEVELS`, `build_target_for_core(core_tier)`, `simulate_ezreal_core_path(full_path, shoe_key, rune_key, core_tier, include_we=True, doran_key=None)→(dps,cost)`, 모듈 상수 `CONTROL_PATH/CONTROL_SHOE/CONTROL_RUNE`, `_iter_paths()`. (`get_ezreal_4core_top1_build`은 power_compare 연계가 범위에 들어올 때 추가 — v1은 YAGNI로 제외.)

- [ ] **Step 1: 검증 스크립트 작성(실패 예상)** — `SCRATCH_DIR/verify_ezreal_t4.py`

```python
# 빠른 단일 경로 검증(전수 탐색 X — 전수는 Step 5 __main__에서 수분 소요).
from adc_sim.simulations.ezreal import simulate_ezreal_core_path, CONTROL_PATH, CONTROL_SHOE, CONTROL_RUNE

# 컨트롤 경로: 코어별 DPS/비용 산출 + 단조 증가
dps1, c1 = simulate_ezreal_core_path(CONTROL_PATH, CONTROL_SHOE, CONTROL_RUNE, 1, include_we=False, doran_key="doranblade")
dps4, c4 = simulate_ezreal_core_path(CONTROL_PATH, CONTROL_SHOE, CONTROL_RUNE, 4, include_we=False, doran_key="doranblade")
assert dps1 > 0 and dps4 > 0, (dps1, dps4)
assert c4 > c1 > 0, (c1, c4)
assert dps4 > dps1, (dps1, dps4)  # 4코어가 1코어보다 강해야 함
print("[ok] control path 1C dps=%.1f gold=%d | 4C dps=%.1f gold=%d" % (dps1, c1, dps4, c4))

# include_we=True(W/E 포함)도 정상 동작
dpsw, _ = simulate_ezreal_core_path(CONTROL_PATH, CONTROL_SHOE, CONTROL_RUNE, 3, include_we=True, doran_key="doranblade")
assert dpsw > 0, dpsw
print("[ok] include_we=True 3C dps=%.1f" % dpsw)
print("ALL T4 PASS")
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python SCRATCH_DIR/verify_ezreal_t4.py`
Expected: `ModuleNotFoundError: No module named 'adc_sim.simulations.ezreal'`.

- [ ] **Step 3: `adc_sim/simulations/ezreal.py` 생성**

```python
from adc_sim.champion import Ezreal, Target
from adc_sim.engine import run_simulation
from adc_sim.runes import Conqueror, LethalTempo, CutDown
from adc_sim.data.items_registry import create_item_from_key
from adc_sim.data.items_data import DORAN_OPTIONS, DORAN_SHORT
import matplotlib.pyplot as plt
import random


CORE_TARGET_STATS = {
    1: {"hp": 1700, "armor": 50, "mr": 25},
    2: {"hp": 1900, "armor": 70, "mr": 30},
    3: {"hp": 2400, "armor": 100, "mr": 50},
    4: {"hp": 2600, "armor": 120, "mr": 70},
}

CORE_LEVELS = {1: {"level": 9}, 2: {"level": 11}, 3: {"level": 13}, 4: {"level": 15}}

# Q 선마(코어별 스킬 레벨). R은 v1 미사용(데미지 제외)이라 r_level은 표기상 의미만. [H, 튜닝 가능]
EZREAL_SKILL_LEVELS = {
    1: {"q": 5, "w": 2, "e": 1, "r": 1},
    2: {"q": 5, "w": 4, "e": 1, "r": 2},
    3: {"q": 5, "w": 5, "e": 2, "r": 2},
    4: {"q": 5, "w": 5, "e": 4, "r": 3},
}


def build_target_for_core(core_tier):
    s = CORE_TARGET_STATS[core_tier]
    return Target(hp=s["hp"], armor=s["armor"], magic_resist=s["mr"], bonus_hp=max(0, s["hp"] - 1500))


def short_name(item_key):
    mapping = {
        "muramana": "Mura", "trinity": "Tri", "statikk": "Statikk", "kraken": "Krk",
        "guinsoo": "Gui", "storm": "Storm", "essence": "ER", "ie": "IE",
        "collector": "Collector", "yuntal": "Yun", "botrk": "BotRK", "bt": "BT",
        "terminus": "Terminus", "ldr": "LDR", "mortal": "Mortal", "pd": "PD",
        "runaan": "Runaan", "shieldbow": "Shieldbow", "rfc": "RFC", "nashor": "Nashor",
        "plated": "Plated", "berserker": "Berserker",
    }
    return mapping.get(item_key, item_key)


def create_rune_from_key(rune_key):
    if rune_key == "conq":
        return Conqueror()
    if rune_key == "lt":
        return LethalTempo()
    raise ValueError(f"Unknown rune key: {rune_key}")


def rune_short(rune_key):
    return {"conq": "Conq", "lt": "LT"}.get(rune_key, rune_key)


def simulate_ezreal_core_path(full_path, shoe_key, rune_key, core_tier, include_we=True, doran_key=None):
    """이즈리얼 DPS·총골드 시뮬. include_we=False면 랭킹용으로 W/E 데미지 제외."""
    target = build_target_for_core(core_tier)
    level_cfg = CORE_LEVELS[core_tier]
    skill_cfg = EZREAL_SKILL_LEVELS[core_tier]

    ez = Ezreal(level=level_cfg["level"], q_level=skill_cfg["q"], w_level=skill_cfg["w"],
                e_level=skill_cfg["e"], r_level=skill_cfg["r"])
    ez.set_rune(create_rune_from_key(rune_key))
    ez.set_sub_rune(CutDown())

    doran_items = [create_item_from_key(doran_key)] if doran_key else []
    items = doran_items + [create_item_from_key(shoe_key)]
    for idx, key in enumerate(full_path[:core_tier], start=1):
        if key == "yuntal":
            crit = 0.05 if idx == core_tier else 0.25
            items.append(create_item_from_key(key, yuntal_crit=crit))
        else:
            items.append(create_item_from_key(key))

    total_cost = 0
    for item in items:
        total_cost += item.cost
        ez.add_item(item)

    if include_we:
        skill_plan = {
            "manual_casts": [(0.0, "q"), (0.0, "w"), (0.0, "e")],
            "auto_cast": {"q": True, "w": True, "e": True},
            "auto_order": ["q", "w", "e"],
        }
    else:
        # 챔피언 간/랭킹 비교에서 W/E 버스트가 kill-time DPS를 왜곡하면 제외
        skill_plan = {
            "manual_casts": [(0.0, "q")],
            "auto_cast": {"q": True, "w": False, "e": False},
            "auto_order": ["q"],
        }

    _, dps, _ = run_simulation(ez, target, verbose=False, skill_plan=skill_plan)
    return dps, total_cost


# --- 탐색 후보 풀(Corki AD-캐리 풀 재사용; Q 비치명이라 크리는 평타에만 이득 → 랭킹이 반영) ---
CORE12_CANDIDATES = ["muramana", "trinity", "statikk", "kraken", "guinsoo", "storm",
                     "essence", "ie", "collector", "yuntal", "botrk", "terminus"]
CORE3_CANDIDATES = ["ldr", "ie", "mortal", "statikk", "pd", "runaan", "guinsoo", "terminus",
                    "botrk", "essence", "trinity", "muramana", "kraken", "shieldbow",
                    "collector", "rfc", "storm", "yuntal", "nashor"]
CORE4_CANDIDATES = ["ie", "ldr", "botrk", "bt", "kraken", "yuntal", "storm", "essence",
                    "trinity", "statikk", "nashor"]
SHOE_CANDIDATES = ["plated", "berserker"]
RUNE_CANDIDATES = ["conq", "lt"]
PEN_EXCLUSIVE = {"terminus", "ldr", "mortal"}

CONTROL_PATH = ("trinity", "muramana", "ie", "ldr")
CONTROL_SHOE = "berserker"
CONTROL_RUNE = "lt"


def _iter_paths():
    """유효 4코어 경로 생성(중복/상호배제 규칙 적용)."""
    for c1 in CORE12_CANDIDATES:
        for c2 in CORE12_CANDIDATES:
            if c1 == c2:
                continue
            if {"trinity", "essence"} == {c1, c2}:
                continue
            for c3 in CORE3_CANDIDATES:
                if c3 in (c1, c2):
                    continue
                for c4 in CORE4_CANDIDATES:
                    if c4 in (c1, c2, c3):
                        continue
                    quad = (c1, c2, c3, c4)
                    if "trinity" in quad and "essence" in quad:
                        continue
                    if sum(1 for k in quad if k in PEN_EXCLUSIVE) > 1:
                        continue
                    yield quad


# 참고: get_ezreal_4core_top1_build 는 power_compare 연계가 범위에 들어올 때
# corki.get_corki_4core_top1_build 패턴(prefix sim 캐시)으로 추가한다. v1은 YAGNI로 제외.


if __name__ == "__main__":
    print("\n=== Ezreal 4-Core Efficiency (DPG vs Control, 5:4:3:3, W/E 제외) ===")
    w1, w2, w3, w4 = 5.0, 4.0, 3.0, 3.0
    wsum = w1 + w2 + w3 + w4
    results = []
    for rune_key in RUNE_CANDIDATES:
        for shoe in SHOE_CANDIDATES:
            for doran in DORAN_OPTIONS:
                for path in _iter_paths():
                    ys = []
                    xs = []
                    dpg = []
                    for tier in (1, 2, 3, 4):
                        dps, cost = simulate_ezreal_core_path(path, shoe, rune_key, tier, include_we=False, doran_key=doran)
                        ys.append(dps); xs.append(cost)
                        dpg.append(dps / (cost / 1000.0) if cost > 0 else 0.0)
                    label = (f"{short_name(path[0])}-{short_name(path[1])}-{short_name(path[2])}-{short_name(path[3])}-"
                             f"{short_name(shoe)}-{rune_short(rune_key)} [{DORAN_SHORT[doran]}]")
                    results.append({
                        "path": path, "shoe": shoe, "rune": rune_key, "doran": doran, "label": label,
                        "x": xs, "y": ys, "dpg": dpg,
                        "is_control": (path == CONTROL_PATH and shoe == CONTROL_SHOE and rune_key == CONTROL_RUNE),
                    })

    control_candidates = [r for r in results if r["is_control"]]
    if not control_candidates:
        raise RuntimeError("Control build not found.")
    control_row = max(control_candidates, key=lambda r: (w1 * r["dpg"][0] + w2 * r["dpg"][1] + w3 * r["dpg"][2] + w4 * r["dpg"][3]))
    cd = control_row["dpg"]

    for r in results:
        rel = [((r["dpg"][i] / cd[i]) * 100.0 - 100.0) if cd[i] > 0 else 0.0 for i in range(4)]
        r["rel_dpg_core"] = rel
        r["score"] = ((w1 * rel[0]) + (w2 * rel[1]) + (w3 * rel[2]) + (w4 * rel[3])) / wsum

    ranked = sorted(results, key=lambda r: r["score"], reverse=True)
    print(f"Control: {control_row['label']} | "
          f"1C {cd[0]:.2f}, 2C {cd[1]:.2f}, 3C {cd[2]:.2f}, 4C {cd[3]:.2f} DPG")
    print("\nTop 30 (rank by weighted relative DPG, 5:4:3:3)")
    print("RK | BUILD                                                    | 1C DPS/ΔDPG% | 2C | 3C | 4C | SCORE")
    print("-" * 140)
    top_n = min(30, len(ranked))
    rows = ranked[:top_n]
    if not any(r["is_control"] for r in rows):
        rows.append(control_row)
    for i, r in enumerate(rows, start=1):
        y = r["y"]; d = r["rel_dpg_core"]
        tag = " [CTRL]" if r["is_control"] else ""
        cells = " | ".join(f"{y[k]:.0f}/{d[k]:+.1f}%" for k in range(4))
        print(f"{i:>2} | {(r['label'] + tag):<56} | {cells} | {r['score']:>6.2f}")

    # 그래프(상위5 강조 + 일부 샘플)
    top5 = ranked[:5]
    top5_keys = {(r["path"], r["shoe"], r["rune"]) for r in top5}
    plt.figure(figsize=(13, 8))
    non_top = [r for r in ranked if (r["path"], r["shoe"], r["rune"]) not in top5_keys]
    rng = random.Random(42)
    for r in (rng.sample(non_top, max(1, int(len(non_top) * 0.05))) if non_top else []):
        plt.plot(r["x"], r["y"], color="#A0A0A0", alpha=0.18, linewidth=1.0, marker="o", markersize=3, zorder=1)
    colors = ["#E4572E", "#4C78A8", "#54A24B", "#F3A712", "#B279A2"]
    for i, r in enumerate(top5):
        plt.plot(r["x"], r["y"], color=colors[i % 5], linewidth=2.8, marker="D", markersize=6, zorder=3,
                 label=f"Top{i+1} {r['label']} (Score {r['score']:.2f})")
    plt.plot(control_row["x"], control_row["y"], color="#111111", linewidth=2.6, marker="s", markersize=7,
             linestyle="--", zorder=4, label=f"CTRL {control_row['label']}")
    plt.title("Ezreal 4-Core DPS Power Spike (Top5 Highlighted, W/E excluded)")
    plt.xlabel("Invested Gold"); plt.ylabel("DPS")
    plt.grid(True, alpha=0.25); plt.legend(loc="best", fontsize=8); plt.tight_layout()
    plt.show()
```

- [ ] **Step 4: 단일 경로 검증(빠름, 그래프 없음)**

Run: `.venv/bin/python SCRATCH_DIR/verify_ezreal_t4.py`
Expected: `[ok] control path ...`, `[ok] include_we=True ...`, `ALL T4 PASS`.

- [ ] **Step 5: 전수 표 출력 육안 검사 (⚠ 수분 소요 + 블로킹 그래프)**

⚠ `__main__`은 corki와 동일한 브루트포스(전수 탐색)라 **수 분** 걸리고, 끝에 `plt.show()`로
**블로킹 그래프 창**이 뜬다(헤드리스/자동화면 창 닫기 필요). 헤드리스에서 표만 보려면
`MPLBACKEND=Agg`로 그래프 창을 억제할 수 있다(표는 그대로 출력, `plt.show()`는 무동작).

Run: `MPLBACKEND=Agg .venv/bin/python -m adc_sim.simulations.ezreal`
Expected: `Control: Tri-Mura-IE-LDR-Berserker-LT [...]` 헤더 + Top 30 표 출력, 표에 `[CTRL]` 행 존재,
코어가 오를수록 DPS 증가 경향.

- [ ] **Step 6: 커밋**

```bash
git add adc_sim/simulations/ezreal.py
git commit -m "이즈리얼 시뮬: 4코어 빌드 탐색·5:4:3:3 상대DPG 랭킹·표·그래프

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: 회귀 — 기존 챔피언/시뮬 무변경 확인

**Files:**
- Verify: `SCRATCH_DIR/verify_ezreal_regression.py` (ephemeral)

**Interfaces:** Consumes 기존 챔피언 클래스 + Corki 시뮬. (champion.py에 Ezreal 추가만 했으므로 기존 동작 불변이 기대값.)

- [ ] **Step 1: 회귀 스크립트 작성 + 실행**

```python
# 기존 챔피언이 정상 import·시뮬되는지(공유 코드 무수정이므로 불변 기대)
from adc_sim.champion import Ashe, Corki, KaiSa, Yunara, Target
from adc_sim.engine import run_simulation
from adc_sim.data.items_registry import create_item_from_key

def quick(champ):
    for k in ("kraken", "ie"):
        champ.add_item(create_item_from_key(k))
    _, dps, _ = run_simulation(champ, Target(hp=2000, armor=80, magic_resist=40, bonus_hp=500), verbose=False)
    return dps

for C in (Ashe, Corki, KaiSa, Yunara):
    dps = quick(C(level=13))
    assert dps > 0 and dps != float("inf"), (C.__name__, dps)
    print(f"[ok] {C.__name__:7} dps={dps:.1f}")

# Corki 시뮬 top1 함수도 정상 동작(스모크)
from adc_sim.simulations.corki import get_corki_4core_top1_build  # noqa
print("[ok] corki top1 import OK")
print("REGRESSION PASS")
```

Run: `.venv/bin/python SCRATCH_DIR/verify_ezreal_regression.py`
Expected: 각 챔피언 `[ok]` 라인 + `REGRESSION PASS`. (실패 시 = 공유 상태 오염 → 근본원인 조사, AGENTS.md §3.)

- [ ] **Step 2: (코드 변경 없음 — 커밋 불필요)** 회귀가 통과하면 Task 1~4 커밋으로 작업 완료.

---

## 최종 체크리스트
- [ ] Task 1~4 커밋 4개 + 회귀 통과.
- [ ] `git status`에 의도치 않은 파일 변경 없음(champion.py + 신규 ezreal.py만).
- [ ] 스펙 §9 가설(H-EZ-1..10)이 코드 주석에 `[H]`로 반영됨.
- [ ] `python -m adc_sim.simulations.ezreal` 표에 `[CTRL]` 존재, 코어별 DPS 단조 증가 경향.
- [ ] (선택) 사용자가 표를 보고 W/E 포함/제외, 스킬레벨표, 컨트롤 빌드 튜닝 의향 확인.
