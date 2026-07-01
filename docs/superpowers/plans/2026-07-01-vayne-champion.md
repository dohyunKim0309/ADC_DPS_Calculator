# Vayne 챔피언 추가 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 이벤트 기반 엔진 위에 베인(Vayne)을 W(은화살)+Q(구르기)+R(결전) 풀 로테이션 DPS로 모델링하고, 전용 온힛/크리 풀에서 4코어 빌드 랭킹 + power_compare 통합을 구현한다.

**Architecture:** `Vayne(Champion)`를 `champion.py`에 추가(Cog'Maw 이벤트 인터페이스 + Ashe 평타리셋 미러). 은화살은 `get_one_hit_damage` 오버라이드에서 **proc 루프 바깥** `true_onhit` 채널에 베인 전용 3타 카운터로 가산(구인수 2배 방지). 은화살 고정피해는 대미지증가(PtA/CutDown/LDR거인학살자=`mod_factor`)로 증폭하되 경감 우회 — 베이스가 stash 한 `_last_damage_amp` 경유. `simulations/vayne.py`는 `cogmaw.py` 단일-키스톤(LethalTempo) 미러.

**Tech Stack:** Python 3.10, `.venv/bin/python`(항상 이것 사용), 표준 라이브러리 + matplotlib. 시뮬은 repo 루트에서 `-m`으로 실행. 테스트는 `pytest`(설치돼 있지 않으면 `.venv/bin/python -m pytest`; 없으면 각 test 파일에 `if __name__=="__main__"` 러너 포함해 `python -m tests.test_x`로도 구동 가능하나 기본은 pytest 가정).

## Global Constraints

- **인터프리터**: 항상 `.venv/bin/python`(Python 3.10). 시스템 python3 금지.
- **실행**: 시뮬/테스트는 **repo 루트**(`/Users/gimdohyeon/PycharmProjects/ADC_DPS_calculator`)에서. 시뮬은 `-m`.
- **수치는 스펙 §3 확정값만 사용**(추정 금지): AD 60(+2.35), AS 0.658(ratio 0.658, +3.3%/lvl), range 550, mana 232(+35), mp5 7.0(+0.4). W%maxHP 6/7/8/9/10, W floor 50/65/80/95/110. Q 총AD비율 0.75/0.85/0.95/1.05/1.15, Q쿨 6/5/4/3/2, Q마나 30. R +AD 35/50/65, R지속 8/10/12, R Q쿨감 0.30/0.40/0.50, R쿨 100/85/70, R마나 80.
- **최소 변경/순수 추가**(AGENTS.md §5): 엔진·기존 아이템·기존 아이템데이터·기존 챔피언 로직 무수정. **유일 베이스 예외** = `Champion.get_one_hit_damage`에 `self._last_damage_amp = mod_factor` stash 1줄(+`__init__` 초기화) — 값 저장뿐, 기존 반환/수치 불변(행위보존).
- **가설 태깅**(AGENTS.md §4): 신규 메커니즘 주석에 `[H-VAYNE-*]` 표기.
- **6튜플 계약**: `get_one_hit_damage` → `(phys_base, magic_base, phys_onhit, magic_onhit, true_base, true_onhit)`. 스킬 이벤트 튜플 → `(name, phys, magic, is_skill_hit)`.
- **커밋**: 각 Task 끝에 커밋. 메시지 말미에 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. 브랜치 = `feat/vayne`(이미 생성됨).
- **주의**: 작업트리에 사전 존재하는 미커밋 변경(settings.py·ashe.py·cogmaw.py·corki.py·ezreal.py·kaisa.py·power_compare.py·yunara.py)이 있다. **이 파일들을 `git add` 하지 말 것** — 각 커밋은 해당 Task가 만든/수정한 파일만 명시적으로 add.

---

### Task 1: 베이스 `_last_damage_amp` stash (은화살 증폭 토대)

**Files:**
- Modify: `adc_sim/champion.py` (`Champion.__init__` 및 `Champion.get_one_hit_damage`)
- Test: `tests/test_vayne_damage_amp_stash.py`

**Interfaces:**
- Produces: `Champion._last_damage_amp` (float) — 매 `get_one_hit_damage` 호출 시 그 공격의 일반 대미지증폭 `mod_factor(=1+damage_multiplier)`. 기본 1.0. Vayne이 은화살 증폭에 사용.

- [ ] **Step 1: Write the failing test**

`tests/test_vayne_damage_amp_stash.py`:
```python
"""Task 1: 베이스 _last_damage_amp stash 검증(행위보존·값 정확).
증폭 없는 공격이면 1.0, CutDown(고HP 8%) 활성이면 1.08."""
from adc_sim.champion import Ashe, Target
from adc_sim.runes import CutDown


def test_last_damage_amp_defaults_to_one_without_modifiers():
    ashe = Ashe(level=11, q_level=5)
    target = Target(hp=2000, armor=50, magic_resist=30, bonus_hp=500)
    ashe.get_one_hit_damage(target, time=0.0)
    assert abs(ashe._last_damage_amp - 1.0) < 1e-9


def test_last_damage_amp_reflects_cutdown_high_hp():
    # CutDown: 대상 체력 60%+ 에서 8% 증폭 → mod_factor 1.08
    ashe = Ashe(level=11, q_level=5)
    ashe.set_sub_rune(CutDown())
    target = Target(hp=2000, armor=50, magic_resist=30, bonus_hp=500)  # full HP → 60%+
    ashe.get_one_hit_damage(target, time=0.0)
    assert abs(ashe._last_damage_amp - 1.08) < 1e-9


def test_last_damage_amp_exists_before_first_attack():
    ashe = Ashe(level=1)
    assert ashe._last_damage_amp == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_vayne_damage_amp_stash.py -v`
Expected: FAIL — `AttributeError: 'Ashe' object has no attribute '_last_damage_amp'`.

- [ ] **Step 3: Add `_last_damage_amp` init in `Champion.__init__`**

`adc_sim/champion.py` — `Champion.__init__` 내부, `self._combat_time = 0.0`(현재 line 56) 바로 아래에 추가:
```python
        self._combat_time = 0.0
        self._last_damage_amp = 1.0  # [H-VAYNE-W] 직전 평타의 일반 대미지증폭(mod_factor). 은화살 true 증폭용 stash.
```

- [ ] **Step 4: Stash `mod_factor` in `Champion.get_one_hit_damage`**

`adc_sim/champion.py` — `mod_factor = 1.0 + damage_multiplier`(현재 line 362) 바로 아래에 추가:
```python
        mod_factor = 1.0 + damage_multiplier
        self._last_damage_amp = mod_factor  # [H-VAYNE-W] 값 저장만(반환 불변). Vayne 은화살이 읽어 true 증폭.
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_vayne_damage_amp_stash.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Quick regression smoke (기존 챔프 수치 불변)**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 기존 테스트 전부 PASS(신규 stash는 값 저장뿐이라 회귀 없음). 실패 시 stash 위치 재확인.

- [ ] **Step 7: Commit**

```bash
git add adc_sim/champion.py tests/test_vayne_damage_amp_stash.py
git commit -m "feat(vayne): 베이스 _last_damage_amp stash(은화살 증폭 토대·행위보존)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `Vayne` 클래스 — 기본 스탯 + W 은화살 + 엔진 인터페이스 골격

**Files:**
- Modify: `adc_sim/champion.py` (파일 끝, `CogMaw` 클래스 뒤에 `Vayne` 추가)
- Test: `tests/test_vayne_silverbolts.py`

**Interfaces:**
- Consumes: `Champion._last_damage_amp` (Task 1), `ANIM_CANCEL_CLIP`(champion.py 모듈 상수), `Target`.
- Produces: `Vayne(level, q_level, w_level, e_level, r_level)`; `get_one_hit_damage`(6튜플, W 은화살 포함); 엔진 인터페이스(`init_combat_state`/`advance_combat_time`/`get_time_to_next_skill_event`/`get_time_to_next_state_event`/`pop_due_skill_events`/`_cast_skill`/`_can_cast_skill`/`_cost`/`_q_cooldown`). Task 3(Q)·4(R)가 `_cast_q`/`_cast_r`·auto 설정을 채운다. 클래스 상수 `W_PCT`/`W_FLOOR`/`Q_AD_RATIO`/`Q_CD`/`Q_MANA`/`R_BONUS_AD`/`R_DURATION`/`R_Q_CDR`/`R_CD`/`R_MANA`.

- [ ] **Step 1: Write the failing tests (은화살 핵심)**

`tests/test_vayne_silverbolts.py`:
```python
"""Task 2: 베인 W 은화살 — 3타마다 max(floor,%maxHP) 고정피해, 증폭 O·경감 X, 구인수 2배 X."""
from adc_sim.champion import Vayne, Target
from adc_sim.runes import CutDown
from adc_sim.data.items_registry import create_item_from_key


def _true_component(champ, target, time=0.0):
    """get_one_hit_damage 6튜플의 고정피해 합(true_base+true_onhit) 반환."""
    p_base, m_base, p_onhit, m_onhit, true_base, true_onhit = champ.get_one_hit_damage(target, time)
    return true_base + true_onhit


def test_silverbolts_every_third_hit():
    v = Vayne(level=11, w_level=5)          # W5 → 10% maxHP, floor 110
    v.init_combat_state()
    target = Target(hp=3000, armor=0, magic_resist=0, bonus_hp=1500)
    # 평타 1,2 = 0, 평타 3 = 발동, 4,5 = 0, 6 = 발동
    trues = [_true_component(v, target) for _ in range(6)]
    assert trues[0] == 0 and trues[1] == 0
    assert trues[2] > 0
    assert trues[3] == 0 and trues[4] == 0
    assert trues[5] > 0


def test_silverbolts_uses_max_of_floor_and_pct():
    # 고HP 대상: 10%·3000 = 300 > floor 110 → 300
    v = Vayne(level=11, w_level=5)
    v.init_combat_state()
    big = Target(hp=3000, armor=0, magic_resist=0, bonus_hp=1500)
    v.get_one_hit_damage(big); v.get_one_hit_damage(big)
    assert abs(_true_component(v, big) - 300.0) < 1e-6
    # 저HP 대상: 10%·500 = 50 < floor 110 → 110
    v2 = Vayne(level=11, w_level=5)
    v2.init_combat_state()
    small = Target(hp=500, armor=0, magic_resist=0, bonus_hp=0)
    v2.get_one_hit_damage(small); v2.get_one_hit_damage(small)
    assert abs(_true_component(v2, small) - 110.0) < 1e-6


def test_silverbolts_amplified_by_damage_increase_not_mitigation():
    # CutDown(고HP 8%) 활성 → 은화살 300 × 1.08 = 324. 방어력은 은화살에 영향 없어야(경감 우회).
    v = Vayne(level=11, w_level=5)
    v.set_sub_rune(CutDown())
    v.init_combat_state()
    target = Target(hp=3000, armor=200, magic_resist=200, bonus_hp=1500)  # 방어 높아도 true 불변
    v.get_one_hit_damage(target); v.get_one_hit_damage(target)
    assert abs(_true_component(v, target) - 324.0) < 1e-6


def test_silverbolts_not_doubled_by_guinsoo():
    # 구인수 보유: 은화살은 3타마다 1회(구인수 proc_count 2배 안 됨).
    v = Vayne(level=11, w_level=5)
    v.init_combat_state()
    v.add_item(create_item_from_key("guinsoo"))
    target = Target(hp=3000, armor=0, magic_resist=0, bonus_hp=1500)
    # 은화살 발동 평타(3번째)의 true 는 정확히 max(floor,%maxHP) 1회분(=300), 증폭없음.
    v.get_one_hit_damage(target); v.get_one_hit_damage(target)
    assert abs(_true_component(v, target) - 300.0) < 1e-6


def test_smoke_autos_plus_w_runs():
    from adc_sim.engine import run_simulation
    from adc_sim.runes import LethalTempo
    v = Vayne(level=11, w_level=5, q_level=5, r_level=2)
    v.set_rune(LethalTempo()); v.set_sub_rune(CutDown())
    v.add_item(create_item_from_key("botrk"))
    target = Target(hp=2000, armor=50, magic_resist=30, bonus_hp=500)
    _, dps, kill_time = run_simulation(v, target, verbose=False, respawn_to_full_kills=1)
    assert dps > 0 and kill_time > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_vayne_silverbolts.py -v`
Expected: FAIL — `ImportError: cannot import name 'Vayne'`.

- [ ] **Step 3: Implement the `Vayne` class**

`adc_sim/champion.py` 파일 **끝**(`CogMaw` 클래스 뒤)에 추가:
```python
class Vayne(Champion):
    """Vayne — 물리 온힛/크리 하이퍼캐리. W 은화살(3타마다 %최대체력 고정피해) +
    Q 구르기(다음 평타 총AD% 강화·평타리셋) + R 결전(고정 추가AD·Q쿨감). [Hypothesis 다수 — spec §9]

    수치 출처: spec §3 (원본 game bin + LoL Wiki + DDragon 교차검증, patch 16.13).
    - AD growth 2.35 는 bin+Wiki(DDragon raw=0 은 데이터 버그 → 배제).
    """

    # W 은화살 [H-VAYNE-W]: 3번째 연속 타격마다 max(floor, %최대체력) 고정피해.
    W_PCT = [0.06, 0.07, 0.08, 0.09, 0.10]        # 최대체력 비율(랭크1~5)
    W_FLOOR = [50.0, 65.0, 80.0, 95.0, 110.0]     # 최소 고정피해(랭크1~5)

    # Q 구르기 [H-VAYNE-Q]: 다음 평타 추가 물리 = 총AD × ratio(랭크1~5). 치명 자연반영.
    Q_AD_RATIO = [0.75, 0.85, 0.95, 1.05, 1.15]
    Q_CD = [6.0, 5.0, 4.0, 3.0, 2.0]
    Q_MANA = 30.0

    # R 결전 [H-VAYNE-R]: 고정 추가AD·지속·Q쿨감%(랭크1~3).
    R_BONUS_AD = [35.0, 50.0, 65.0]
    R_DURATION = [8.0, 10.0, 12.0]
    R_Q_CDR = [0.30, 0.40, 0.50]
    R_CD = [100.0, 85.0, 70.0]
    R_MANA = 80.0

    def __init__(self, level=1, q_level=5, w_level=5, e_level=1, r_level=3):
        super().__init__(
            name="Vayne", base_ad=60, base_as=0.658, as_ratio=0.658,
            as_growth=3.3, base_range=550, level=level, ad_growth=2.35,
        )
        # 보관(비-DPS): 미래 1대1 모델용
        self.base_hp = 550; self.hp_growth = 103
        self.base_armor = 23; self.armor_growth = 4.6
        self.base_mr = 30; self.mr_growth = 1.3
        # 마나 (spec §3.1). base_mp5/mp5_growth = Champion.mana_regen_per_sec 가 읽는 이름.
        self.base_mana = 232.0; self.mana_growth = 35.0
        self.base_mp5 = 7.0; self.mp5_growth = 0.4

        self.q_level = q_level; self.w_level = w_level
        self.e_level = e_level; self.r_level = r_level

        self.mana_cost = {"q": self.Q_MANA, "r": self.R_MANA}

        # 상태 (init_combat_state 에서 리셋)
        self.sb_stacks = 0
        self.q_empowered = False
        self.q_reset_pending = False
        self.r_active = False
        self.r_end_time = 0.0
        self._r_bonus_applied = 0.0
        self.cooldowns_remaining = {"q": 0.0, "r": 0.0}
        self.manual_skill_casts = []
        self.manual_skill_index = 0
        self.auto_skill_enabled = {"q": False, "r": False}   # Task 3/4 에서 활성
        self.auto_skill_order = ["q"]

    # ---- W 은화살 (+ Q 강화 훅): get_one_hit_damage 오버라이드 ----
    def get_one_hit_damage(self, target, time=0):
        p_base, m_base, p_onhit, m_onhit, pt_base, pt_onhit = super().get_one_hit_damage(target, time)

        # Q 강화 평타: 총AD ratio 만큼 기본 물리 증폭(p_base 는 이미 치명기대·mod_factor 반영 →
        # 보너스도 치명·증폭 자연반영). 온힛은 미증폭(강화평타도 온힛 1회). [H-VAYNE-Q] (Task 3 에서 arm)
        if self.q_empowered:
            self.q_empowered = False
            p_base *= (1.0 + self.Q_AD_RATIO[self.q_level - 1])

        # W 은화살: 3번째 타격마다 고정피해 = max(floor, %maxHP). proc 루프 바깥이라 구인수 2배 안 됨.
        # 대미지증가(PtA/CutDown/LDR거인학살자=_last_damage_amp)로 증폭·경감(방/마저) 우회. [H-VAYNE-W]
        self.sb_stacks += 1
        if self.sb_stacks >= 3:
            self.sb_stacks = 0
            idx = self.w_level - 1
            sb = max(self.W_FLOOR[idx], self.W_PCT[idx] * target.max_hp)
            pt_onhit += sb * self._last_damage_amp

        return p_base, m_base, p_onhit, m_onhit, pt_base, pt_onhit

    def get_attack_interval(self):
        # Q(구르기) 직후 평타 리셋 근사: 다음 평타 간격을 ANIM_CANCEL_CLIP 로 상한 클리핑. [H-VAYNE-Q]
        if self.q_reset_pending:
            self.q_reset_pending = False
            return min(super().get_attack_interval(), ANIM_CANCEL_CLIP)
        return super().get_attack_interval()

    # ---- 엔진 주도 이벤트 인터페이스 (CogMaw 미러) ----
    def init_combat_state(self, skill_plan=None):
        super().init_combat_state(skill_plan)   # _combat_time=0, current_mana=total_mana
        self.sb_stacks = 0
        self.q_empowered = False
        self.q_reset_pending = False
        # R 버프 리셋(이전 전투 잔여 bonus_ad 원복)
        if self._r_bonus_applied:
            self.bonus_ad -= self._r_bonus_applied
            self._r_bonus_applied = 0.0
        self.r_active = False
        self.r_end_time = 0.0
        self.cooldowns_remaining = {"q": 0.0, "r": 0.0}
        plan = skill_plan or {}
        auto_cfg = plan.get("auto_cast", {})
        _defaults = {"q": False, "r": False}   # Task 3/4 에서 q/r 기본 True 로 전환
        self.auto_skill_enabled = {k: auto_cfg.get(k, _defaults[k]) for k in ("q", "r")}
        self.auto_skill_order = list(plan.get("auto_order", ["q"]))
        self.manual_skill_casts = sorted(list(plan.get("manual_casts", [])), key=lambda x: x[0])
        self.manual_skill_index = 0

    def advance_combat_time(self, delta_time, current_time, target):
        super().advance_combat_time(delta_time, current_time, target)   # regen
        if delta_time > 0:
            for k in self.cooldowns_remaining:
                self.cooldowns_remaining[k] = max(0.0, self.cooldowns_remaining[k] - delta_time)
        # R 만료 → bonus_ad 원복 (Task 4 에서 유효)
        if self.r_active and current_time >= self.r_end_time:
            self.r_active = False
            if self._r_bonus_applied:
                self.bonus_ad -= self._r_bonus_applied
                self._r_bonus_applied = 0.0

    def get_time_to_next_state_event(self, current_time):
        if self.r_active:
            return max(0.0, self.r_end_time - current_time)
        return float("inf")

    def _q_cooldown(self):
        """Q 기본 쿨(스킬가속) × R 활성 시 (1 - CDR). [H-VAYNE-Q/R]"""
        cd = self.apply_haste_to_cooldown(self.Q_CD[self.q_level - 1])
        if self.r_active:
            cd *= (1.0 - self.R_Q_CDR[self.r_level - 1])
        return cd

    def _cost(self, name):
        return self.mana_cost.get(name, 0.0)

    def _can_cast_skill(self, name):
        eps = 1e-9
        if self.cooldowns_remaining.get(name, float("inf")) > eps:
            return False
        if name == "r" and self.r_active:
            return False
        if not self.can_afford(self._cost(name)):
            return False
        return True

    def get_time_to_next_skill_event(self, current_time):
        eps = 1e-9
        cands = []
        if self.manual_skill_index < len(self.manual_skill_casts):
            t, _ = self.manual_skill_casts[self.manual_skill_index]
            cands.append(max(0.0, t - current_time))
        for name, enabled in self.auto_skill_enabled.items():
            if not enabled:
                continue
            if name == "r" and self.r_active:
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
        if name == "q":
            self._cast_q(time)
            return ("q", 0.0, 0.0, False)   # 무직접피해(강화는 다음 평타)
        if name == "r":
            self._cast_r(time)
            return ("r", 0.0, 0.0, False)   # 버프
        return (name, 0.0, 0.0, False)

    def _cast_q(self, time):
        """Q 구르기(Task 3 에서 본체): arm 강화 + 평타리셋 + 주문검 장전. 마나는 _cast_skill 차감."""
        self.q_empowered = True
        self.q_reset_pending = True
        self.cooldowns_remaining["q"] = self._q_cooldown()
        self.cast_spell(time)

    def _cast_r(self, time):
        """R 결전(Task 4 에서 본체): 고정 추가AD + Q쿨감 활성, 지속 R_DURATION. 만료 시 원복."""
        idx = self.r_level - 1
        bonus = self.R_BONUS_AD[idx]
        self.bonus_ad += bonus
        self._r_bonus_applied = bonus
        self.r_active = True
        self.r_end_time = time + self.R_DURATION[idx]
        self.cooldowns_remaining["r"] = self.apply_haste_to_cooldown(self.R_CD[idx])
        self.cast_spell(time); self.cast_ultimate(time)
```

주의: `_cast_q`/`_cast_r` 본체를 Task 2에 이미 넣되, auto 기본은 False(비활성)라 Task 2 테스트에선 평타+W만 돈다. Task 3/4는 auto 기본을 True 로 바꾸고 각 캐스트 동작을 검증한다(코드는 이미 존재하므로 Task 3/4는 활성화+검증 중심).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_vayne_silverbolts.py -v`
Expected: PASS (6 passed). 실패 시:
- `test_silverbolts_not_doubled_by_guinsoo` 실패 → 은화살이 proc 루프 안(get_champion_onhit)에 들어갔는지 확인. 반드시 `get_one_hit_damage` 오버라이드에서 직접 가산해야 함.
- `test_silverbolts_amplified...` 실패 → `_last_damage_amp` 곱 확인(Task 1 stash 필요).

- [ ] **Step 5: Commit**

```bash
git add adc_sim/champion.py tests/test_vayne_silverbolts.py
git commit -m "feat(vayne): Vayne 클래스 + W 은화살(3타 고정피해·증폭O·경감X·구인수 비2배)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Q 구르기 — 강화 평타 + 평타 리셋 + 마나 게이트

**Files:**
- Modify: `adc_sim/champion.py` (`Vayne.init_combat_state` 의 auto 기본값만 `q:True` 로)
- Test: `tests/test_vayne_tumble.py`

**Interfaces:**
- Consumes: Task 2 의 `Vayne` 전체.
- Produces: Q auto-cast 활성(skill_plan 미지정 시 q 자동). 강화 평타 = `p_base*(1+Q_AD_RATIO)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_vayne_tumble.py`:
```python
"""Task 3: 베인 Q 구르기 — 강화 평타(총AD ratio·치명반영)·평타리셋·마나게이트."""
from adc_sim.champion import Vayne, Target, ANIM_CANCEL_CLIP


def test_empowered_attack_scales_p_base():
    v = Vayne(level=11, q_level=5, w_level=5)   # Q5 → ratio 1.15
    v.init_combat_state()
    target = Target(hp=99999, armor=0, magic_resist=0, bonus_hp=0)  # 안 죽게 큰 HP
    # 비강화 평타 물리
    v.q_empowered = False
    p_normal = v.get_one_hit_damage(target)[0]
    # 강화 평타 물리(같은 상태에서 arm) — 새 인스턴스로 sb 카운터 영향 배제
    v2 = Vayne(level=11, q_level=5, w_level=5)
    v2.init_combat_state()
    v2.q_empowered = True
    p_emp = v2.get_one_hit_damage(target)[0]
    assert abs(p_emp - p_normal * (1.0 + 1.15)) < 1e-6


def test_empowered_flag_consumed_after_one_attack():
    v = Vayne(level=11, q_level=5)
    v.init_combat_state()
    target = Target(hp=99999, armor=0, magic_resist=0, bonus_hp=0)
    v.q_empowered = True
    v.get_one_hit_damage(target)          # 소비
    assert v.q_empowered is False
    p_after = v.get_one_hit_damage(target)[0]
    v2 = Vayne(level=11, q_level=5); v2.init_combat_state()
    p_plain = v2.get_one_hit_damage(target)[0]
    # sb 카운터 차이 없는 물리 base 만 비교(둘 다 비강화) → 근사 동일
    assert abs(p_after - p_plain) < 1e-6


def test_q_auto_casts_and_resets_attack_interval():
    from adc_sim.engine import run_simulation
    from adc_sim.runes import LethalTempo, CutDown
    v = Vayne(level=11, q_level=5, w_level=5, r_level=2)
    v.set_rune(LethalTempo()); v.set_sub_rune(CutDown())
    target = Target(hp=3000, armor=50, magic_resist=30, bonus_hp=1500)
    # skill_plan 미지정 → Q auto 기본 활성
    _, dps, _ = run_simulation(v, target, verbose=False, respawn_to_full_kills=1)
    assert dps > 0
    # Q 리셋 클리핑 상수 노출 확인
    assert ANIM_CANCEL_CLIP == 0.33


def test_q_mana_gate_blocks_when_insufficient():
    v = Vayne(level=11, q_level=5)
    v.init_combat_state()
    v.current_mana = 10.0            # Q 30 미만
    assert v._can_cast_skill("q") is False
    v.current_mana = 30.0
    assert v._can_cast_skill("q") is True


def test_q_dps_higher_than_autos_only():
    from adc_sim.engine import run_simulation
    from adc_sim.runes import LethalTempo, CutDown
    from adc_sim.data.items_registry import create_item_from_key
    def _run(q_on):
        v = Vayne(level=13, q_level=5, w_level=5, r_level=2)
        v.set_rune(LethalTempo()); v.set_sub_rune(CutDown())
        v.add_item(create_item_from_key("botrk"))
        v.add_item(create_item_from_key("pd"))
        t = Target(hp=2500, armor=60, magic_resist=40, bonus_hp=1000)
        plan = {"auto_cast": {"q": q_on, "r": False}, "auto_order": ["q"]}
        return run_simulation(v, t, verbose=False, skill_plan=plan, respawn_to_full_kills=2)[1]
    assert _run(True) > _run(False)   # Q 강화가 DPS 증가
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_vayne_tumble.py -v`
Expected: `test_q_dps_higher_than_autos_only` FAIL (Q auto 기본 False → q_on 무효, 두 값 동일). 나머지는 PASS 가능.

- [ ] **Step 3: Enable Q auto by default**

`adc_sim/champion.py` — `Vayne.init_combat_state` 의 `_defaults` 를 수정:
```python
        _defaults = {"q": True, "r": False}   # Q 오토 기본 활성(R 은 매뉴얼 t=0)
```
그리고 `Vayne.__init__` 의 `self.auto_skill_enabled = {"q": False, "r": False}` 를:
```python
        self.auto_skill_enabled = {"q": True, "r": False}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_vayne_tumble.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add adc_sim/champion.py tests/test_vayne_tumble.py
git commit -m "feat(vayne): Q 구르기 강화평타(총AD ratio·치명)·평타리셋·마나게이트

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: R 결전의 시간 — 고정 추가AD 버프 + Q 쿨감 + 만료

**Files:**
- Modify: `adc_sim/champion.py` (변경 없음 — 코드는 Task 2 에 이미 존재; 검증만. 필요 시 미세수정)
- Test: `tests/test_vayne_finalhour.py`

**Interfaces:**
- Consumes: Task 2/3 의 `Vayne`. R 은 `skill_plan={"manual_casts":[(0.0,"r")]}` 로 t=0 시전.
- Produces: R 활성 시 `total_ad += R_BONUS_AD[r-1]`, Q 쿨 `×(1-R_Q_CDR)`, 지속 후 원복.

- [ ] **Step 1: Write the failing tests**

`tests/test_vayne_finalhour.py`:
```python
"""Task 4: 베인 R 결전 — 고정 추가AD 버프·Q 쿨감·만료 원복·마나 80."""
from adc_sim.champion import Vayne, Target


def test_r_adds_bonus_ad_on_cast():
    v = Vayne(level=16, r_level=3)   # R3 → +65 AD
    v.init_combat_state()
    ad_before = v.total_ad
    v._cast_r(time=0.0)
    assert abs(v.total_ad - (ad_before + 65.0)) < 1e-6
    assert v.r_active is True


def test_r_reduces_q_cooldown():
    v = Vayne(level=16, q_level=5, r_level=3)   # Q5 쿨 2.0, R3 CDR 50%
    v.init_combat_state()
    cd_no_r = v._q_cooldown()          # R 비활성
    v._cast_r(time=0.0)
    cd_with_r = v._q_cooldown()        # R 활성 → ×0.5
    assert abs(cd_with_r - cd_no_r * 0.5) < 1e-6


def test_r_expires_and_reverts_bonus_ad():
    v = Vayne(level=16, r_level=3)     # 지속 12s
    v.init_combat_state()
    target = Target(hp=99999, armor=0, magic_resist=0, bonus_hp=0)
    ad_before = v.total_ad
    v._cast_r(time=0.0)
    assert v.total_ad > ad_before
    # 지속(12s) 경과 → 만료 원복
    v.advance_combat_time(delta_time=13.0, current_time=13.0, target=target)
    assert v.r_active is False
    assert abs(v.total_ad - ad_before) < 1e-6


def test_r_mana_cost_and_gate():
    v = Vayne(level=16, r_level=3)
    v.init_combat_state()
    assert v._cost("r") == 80.0
    v.current_mana = 50.0
    assert v._can_cast_skill("r") is False


def test_r_cast_at_t0_via_skill_plan():
    from adc_sim.engine import run_simulation
    from adc_sim.runes import LethalTempo, CutDown
    from adc_sim.data.items_registry import create_item_from_key
    def _run(r_on):
        v = Vayne(level=16, q_level=5, w_level=5, r_level=3)
        v.set_rune(LethalTempo()); v.set_sub_rune(CutDown())
        v.add_item(create_item_from_key("botrk"))
        t = Target(hp=2500, armor=60, magic_resist=40, bonus_hp=1000)
        plan = {"manual_casts": [(0.0, "r")] if r_on else [],
                "auto_cast": {"q": True, "r": False}, "auto_order": ["q"]}
        return run_simulation(v, t, verbose=False, skill_plan=plan, respawn_to_full_kills=2)[1]
    assert _run(True) > _run(False)   # R 추가AD 로 DPS 증가
```

- [ ] **Step 2: Run tests to verify they pass (또는 실패 시 수정)**

Run: `.venv/bin/python -m pytest tests/test_vayne_finalhour.py -v`
Expected: PASS (5 passed). Task 2 에 R 코드가 이미 있으므로 대개 바로 통과. 실패 시:
- 만료 원복 안 됨 → `advance_combat_time` 의 R 만료 블록·`_r_bonus_applied` 확인.
- 쿨감 미적용 → `_q_cooldown` 의 `r_active` 분기 확인.

- [ ] **Step 3: (필요 시) 수정 후 재실행**

수정이 필요하면 최소 변경 후 재실행. 없으면 스킵.

- [ ] **Step 4: Commit**

```bash
git add adc_sim/champion.py tests/test_vayne_finalhour.py
git commit -m "test(vayne): R 결전 버프(추가AD·Q쿨감·만료원복·마나) 검증

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: `simulations/vayne.py` — 빌드 탐색·랭킹·그래프

**Files:**
- Create: `adc_sim/simulations/vayne.py`
- Test: `tests/test_vayne_sim.py`

**Interfaces:**
- Consumes: `Vayne`, `run_simulation`, `create_item_from_key`, `ADC_PACKAGES`, `CORE_WEIGHTS_RAW/LABEL`, `LethalTempo`, `CutDown`, `build_ashe_like_core_report_meta`.
- Produces: `simulate_vayne_core_path(full_path, core_tier, doran_key, boots_key, rune_as_bonus)` → `(dps, cost)`; `CONTROL_PATH=("botrk","guinsoo","terminus","pd")`; `get_vayne_4core_top1_build(rank_by="dpg")` → dict(path/doran/boots/pkg_label/score/weighted_dpg/weighted_dps/control_*); `get_vayne_powercompare_builds()` → `(best, meta)` dict 쌍.

- [ ] **Step 1: Write the failing tests**

`tests/test_vayne_sim.py`:
```python
"""Task 5: vayne.py 시뮬 — 컨트롤 존재·RelDPG 정합·top1/powercompare 산출."""
from adc_sim.simulations.vayne import (
    simulate_vayne_core_path, CONTROL_PATH,
    get_vayne_4core_top1_build, get_vayne_powercompare_builds,
)


def test_control_path_is_expected():
    assert CONTROL_PATH == ("botrk", "guinsoo", "terminus", "pd")


def test_simulate_core_path_positive():
    dps, cost = simulate_vayne_core_path(list(CONTROL_PATH), core_tier=2,
                                         doran_key="doranblade", boots_key="berserker")
    assert dps > 0 and cost > 0


def test_top1_build_has_control_metadata():
    top1 = get_vayne_4core_top1_build(rank_by="dpg")
    assert "path" in top1 and len(top1["path"]) == 4
    assert top1["control_path"] == CONTROL_PATH
    assert top1["score"] > 0 and top1["weighted_dpg"] > 0


def test_powercompare_builds_shape():
    best, meta = get_vayne_powercompare_builds()
    for b in (best, meta):
        assert len(b["path"]) == 4
        assert b["doran"] and b["boots"]
    assert meta["path"] == CONTROL_PATH   # meta = 컨트롤(실전 기준)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_vayne_sim.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adc_sim.simulations.vayne'`.

- [ ] **Step 3: Implement `simulations/vayne.py`**

`adc_sim/simulations/vayne.py`:
```python
from adc_sim.champion import Vayne, Target
import matplotlib.pyplot as plt
from adc_sim.runes import LethalTempo, CutDown
from adc_sim.engine import run_simulation
from adc_sim.data.items_registry import create_item_from_key
from adc_sim.data.items_data import ADC_PACKAGES
from adc_sim.settings import CORE_WEIGHTS_RAW, CORE_WEIGHTS_LABEL
from adc_sim.simulations.ashe import build_ashe_like_core_report_meta

# 코어 단계별 고정 타겟 (Ashe/KaiSa/CogMaw 시뮬과 동일)
CORE_TARGET_STATS = {
    1: {"hp": 1700, "armor": 50, "mr": 25},
    2: {"hp": 1900, "armor": 70, "mr": 30},
    3: {"hp": 2400, "armor": 100, "mr": 50},
    4: {"hp": 2600, "armor": 120, "mr": 70},
}
CORE_VAYNE_LEVELS = {1: {"level": 9}, 2: {"level": 11}, 3: {"level": 13}, 4: {"level": 15}}


def build_target_for_core(core_tier):
    s = CORE_TARGET_STATS[core_tier]
    return Target(hp=s["hp"], armor=s["armor"], magic_resist=s["mr"],
                  bonus_hp=max(0, s["hp"] - 1500))


def _skill_levels_for_core(core_tier):
    """스킬 선마 Q→W→E, R=lvl 기반. spec §6 포인트정합표. [H-VAYNE-SKILL]
    core1(lvl9): q5/w3/r1 · core2(11): q5/w4/r2 · core3(13): q5/w5/r2 · core4(15): q5/w5/e3/r2.
    (E 는 DPS 미모델 → e_level 은 배열색인 하한 1 로 floor.)"""
    lvl = CORE_VAYNE_LEVELS[core_tier]["level"]
    q = 5
    w = {1: 3, 2: 4, 3: 5, 4: 5}[core_tier]
    e = {1: 1, 2: 1, 3: 1, 4: 3}[core_tier]
    r = 1 if lvl < 11 else (2 if lvl < 16 else 3)
    return q, w, e, r


def simulate_vayne_core_path(full_path, core_tier, doran_key="doranblade",
                             boots_key="berserker", rune_as_bonus=0.0):
    """Vayne DPS + total gold for a core timing. R@t=0, Q 쿨마다(마나 바운드). K=2.

    full_path: 코어 키 리스트. core_tier: 1~4. doran/boots/rune_as: 패키지.
    반환: (dps, total_cost).
    """
    target = build_target_for_core(core_tier)
    lvl = CORE_VAYNE_LEVELS[core_tier]["level"]
    q, w, e, r = _skill_levels_for_core(core_tier)
    vayne = Vayne(level=lvl, q_level=q, w_level=w, e_level=e, r_level=r)
    vayne.set_rune(LethalTempo())
    vayne.set_sub_rune(CutDown())

    items = ([create_item_from_key(doran_key)] if doran_key else []) + [create_item_from_key(boots_key)]
    for key in full_path[:core_tier]:
        # 윤탈 스택 가정: 구매 코어=10%, 다음 코어부터 25% (ashe.py 관례와 동일)
        if key == "yuntal25":
            idx = full_path.index(key) + 1
            yuntal_crit = 0.10 if idx == core_tier else 0.25
            items.append(create_item_from_key(key, yuntal_crit=yuntal_crit))
        else:
            items.append(create_item_from_key(key))
    total_cost = 0
    for it in items:
        total_cost += it.cost
        vayne.add_item(it)
    vayne.bonus_as_percent += rune_as_bonus

    skill_plan = {
        "manual_casts": [(0.0, "r")],          # R t=0 1회
        "auto_cast": {"q": True, "r": False},  # Q 쿨마다
        "auto_order": ["q"],
    }
    _, dps, _ = run_simulation(vayne, target, verbose=False, skill_plan=skill_plan, respawn_to_full_kills=2)
    return dps, total_cost


# 컨트롤(베이스라인) = 사용자 확정 실전 온힛+크리 빌드. 탐색공간에 반드시 존재해야 함.
CONTROL_PATH = ("botrk", "guinsoo", "terminus", "pd")
_VAYNE_TOP1_CACHE = {}

# 베인 전용 온힛+크리 풀 (spec §6). pen 배타 {ldr, mortal, terminus}.
CORE1_CANDIDATES = ["botrk", "guinsoo", "kraken", "terminus", "wit", "runaan", "pd",
                    "rfc", "statikk", "yuntal25", "c44", "storm", "collector"]
CORE2_CANDIDATES = ["botrk", "guinsoo", "kraken", "terminus", "wit", "runaan", "pd",
                    "ie", "rfc", "collector", "yuntal25", "statikk"]
CORE3_CANDIDATES = ["ie", "ldr", "guinsoo", "terminus", "pd", "collector", "wit", "kraken"]
CORE4_CANDIDATES = ["ie", "ldr", "pd", "runaan", "rfc", "collector", "kraken", "wit", "statikk", "terminus"]
PEN_EXCLUSIVE = {"terminus", "ldr", "mortal"}

ITEM_SHORT = {
    "botrk": "BotRK", "guinsoo": "Gui", "kraken": "Krk", "terminus": "Terminus",
    "wit": "Wit's", "runaan": "Runaan", "pd": "PD", "ie": "IE", "ldr": "LDR",
    "rfc": "RFC", "statikk": "Statikk", "yuntal25": "Yun", "c44": "C44",
    "storm": "Storm", "collector": "Collector",
}


def _build_all_paths():
    all_paths, seen = [], set()
    for c1 in CORE1_CANDIDATES:
        for c2 in CORE2_CANDIDATES:
            if len({c1, c2}) < 2:
                continue
            for c3 in CORE3_CANDIDATES:
                for c4 in CORE4_CANDIDATES:
                    if len({c1, c2, c3, c4}) < 4:
                        continue
                    if sum(1 for k in (c1, c2, c3, c4) if k in PEN_EXCLUSIVE) > 1:
                        continue
                    path = (c1, c2, c3, c4)
                    if path in seen:
                        continue
                    seen.add(path)
                    all_paths.append(path)
    # 컨트롤이 풀에서 안 나오면 강제 삽입(순서 고정)
    if CONTROL_PATH not in seen:
        all_paths.append(CONTROL_PATH)
    return all_paths


def _rank_rows(all_paths):
    """전 (경로×패키지) 시뮬 → dedup(정렬 combo 최고점) → 컨트롤 정규화 5:4:3:3 RelDPG. rows 반환."""
    dedupe_weight_raw = list(CORE_WEIGHTS_RAW)
    core_weight_raw = list(CORE_WEIGHTS_RAW)
    weight_sum = sum(core_weight_raw)
    core_weights = [w / weight_sum for w in core_weight_raw]
    ctrl_combo = tuple(sorted(CONTROL_PATH))

    rows = []
    for path in all_paths:
        for pkg in ADC_PACKAGES:
            kw = dict(doran_key=pkg["doran"], boots_key=pkg["boots"], rune_as_bonus=pkg["rune_as"])
            dps_list, cost_list = [], []
            for tier in range(1, 5):
                d, c = simulate_vayne_core_path(path, tier, **kw)
                dps_list.append(d); cost_list.append(c)
            dpg = [dps_list[i] / (cost_list[i] / 1000.0) if cost_list[i] > 0 else 0.0 for i in range(4)]
            rows.append({
                "path": path, "doran": pkg["doran"], "boots": pkg["boots"],
                "rune_as": pkg["rune_as"], "pkg_label": pkg["label"],
                "x": cost_list, "y": dps_list, "dpg": dpg,
                "is_control": tuple(sorted(path)) == ctrl_combo,
                "dedupe_eff": sum(dedupe_weight_raw[i] * dpg[i] for i in range(4)),
            })

    dedupe_best = {}
    for r in rows:
        key = tuple(sorted(r["path"]))
        if key not in dedupe_best or r["dedupe_eff"] > dedupe_best[key]["dedupe_eff"]:
            dedupe_best[key] = r
    rows_dedup = list(dedupe_best.values())

    # 컨트롤은 정규 순서(CONTROL_PATH)로 고정
    rows_dedup = [r for r in rows_dedup if not r["is_control"]]
    ctrl_cands = [r for r in rows if tuple(r["path"]) == CONTROL_PATH]
    if ctrl_cands:
        rows_dedup.append(max(ctrl_cands, key=lambda r: r["dedupe_eff"]))

    for r in rows_dedup:
        r["weighted_dpg"] = sum(core_weights[i] * r["dpg"][i] for i in range(4))
        r["weighted_dps"] = sum(core_weights[i] * r["y"][i] for i in range(4))

    control_rows = [r for r in rows_dedup if r["is_control"]]
    if not control_rows:
        raise RuntimeError(
            f"Control build {CONTROL_PATH} not found in search space. "
            "Check candidate pools contain botrk/guinsoo/terminus/pd."
        )
    best_control = max(control_rows, key=lambda r: r["weighted_dpg"])
    baseline_dpg_4 = best_control["dpg"][:4]

    for r in rows_dedup:
        core_rel_pct = [
            (r["dpg"][i] / baseline_dpg_4[i] * 100.0 if baseline_dpg_4[i] > 0 else 0.0)
            for i in range(4)
        ]
        r["core_rel_delta_pct_4"] = [p - 100.0 for p in core_rel_pct]
        r["rel_dpg_score"] = sum(core_weights[i] * core_rel_pct[i] for i in range(4))

    return rows_dedup, best_control


def get_vayne_4core_top1_build(rank_by="dpg"):
    """랭킹된 4코어 top1 빌드 + 컨트롤 메타 반환. rank_by: "dpg"(RelDPG) | "dps"(절대 가중DPS)."""
    if rank_by in _VAYNE_TOP1_CACHE:
        return _VAYNE_TOP1_CACHE[rank_by]
    rows_dedup, best_control = _rank_rows(_build_all_paths())
    sort_key = (lambda r: r["weighted_dps"]) if rank_by == "dps" else (lambda r: r["rel_dpg_score"])
    ranked = sorted(rows_dedup, key=sort_key, reverse=True)
    top1 = ranked[0]
    result = {
        "path": top1["path"], "doran": top1["doran"], "boots": top1["boots"],
        "rune_as": top1["rune_as"], "pkg_label": top1["pkg_label"],
        "score": top1["rel_dpg_score"], "weighted_dpg": top1["weighted_dpg"],
        "weighted_dps": top1["weighted_dps"],
        "control_path": best_control["path"], "control_doran": best_control["doran"],
        "control_boots": best_control["boots"], "control_rune_as": best_control["rune_as"],
        "control_pkg": best_control["pkg_label"], "control_weighted_dpg": best_control["weighted_dpg"],
    }
    _VAYNE_TOP1_CACHE[rank_by] = result
    return result


def build_vayne_core_report_meta(full_path, core_tier):
    """직렬화용 리포트 메타(Ashe-like 공용 헬퍼 재사용)."""
    return build_ashe_like_core_report_meta("Vayne", full_path, core_tier)


def get_vayne_powercompare_builds():
    """power_compare 연동용 (best, meta).
    - best: 절대 가중DPS top1(rank_by="dps") — power_compare 가 DPS 비교라.
    - meta: 컨트롤(botrk-guinsoo-terminus-pd, 최적 패키지) — 실전 기준.
    각 dict: path/doran/boots/rune_as/pkg_label/weighted_dpg 또는 weighted_dps.
    """
    best_src = get_vayne_4core_top1_build(rank_by="dps")
    best = {
        "path": best_src["path"], "doran": best_src["doran"], "boots": best_src["boots"],
        "rune_as": best_src["rune_as"], "pkg_label": best_src["pkg_label"],
        "weighted_dps": best_src["weighted_dps"],
    }
    dpg_src = get_vayne_4core_top1_build(rank_by="dpg")
    meta = {
        "path": dpg_src["control_path"], "doran": dpg_src["control_doran"],
        "boots": dpg_src["control_boots"], "rune_as": dpg_src["control_rune_as"],
        "pkg_label": dpg_src["control_pkg"], "weighted_dpg": dpg_src["control_weighted_dpg"],
    }
    return best, meta


if __name__ == "__main__":
    print("\n=== Vayne Build Path Power Spike (W/Q auto + R@0, 1->4 Core) ===")
    all_paths = _build_all_paths()
    print(f"Total unique paths in search space: {len(all_paths)}")
    rows_dedup, best_control = _rank_rows(all_paths)
    ranked = sorted(rows_dedup, key=lambda r: r["rel_dpg_score"], reverse=True)

    print(f"\nControl: {'-'.join(best_control['path'])} [{best_control['pkg_label']}] "
          f"| Weighted DPG {best_control['weighted_dpg']:.2f}")
    col_build, col_core, col_rep = 34, 18, 9
    header = (f"{'RK':>3} | {'BUILD(4C)':<{col_build}} | {'CTRL':>6} | "
              f"{'1C DPS/ΔDPG%':>{col_core}} | {'2C DPS/ΔDPG%':>{col_core}} | "
              f"{'3C DPS/ΔDPG%':>{col_core}} | {'4C DPS/ΔDPG%':>{col_core}} | {'RelDPG':>{col_rep}}")
    print(f"\nTop 30 + Control (RelDPG = control-normalised weighted DPG ×100, {CORE_WEIGHTS_LABEL})")
    print(header); print("-" * len(header))

    def _fmt_build(r):
        p = r["path"]
        return f"{'-'.join(ITEM_SHORT.get(k, k) for k in p)} [{r['pkg_label']}]"

    top_rows = ranked[:30]
    ctrl_rows = [r for r in ranked if r["is_control"]]
    out_rows = top_rows + [r for r in ctrl_rows if r not in top_rows]
    for rank, r in enumerate(out_rows, start=1):
        y = r["y"]; d = r["core_rel_delta_pct_4"]
        tag = "[CTRL]" if r["is_control"] else ""
        label = _fmt_build(r)
        label = label if len(label) <= col_build else label[:col_build - 3] + "..."
        cells = " | ".join(f"{y[i]:.1f}/{d[i]:+.1f}%".rjust(col_core) for i in range(4))
        print(f"{rank:>3} | {label:<{col_build}} | {tag:>6} | {cells} | {r['rel_dpg_score']:>{col_rep}.2f}")

    # 그래프: Top5 비컨트롤 + 컨트롤, 4코어 DPS 커브
    top5 = [r for r in ranked if not r["is_control"]][:5]
    plt.figure(figsize=(12, 8))
    colors = ["#E4572E", "#F3A712", "#54A24B", "#4C78A8", "#B279A2"]
    for i, r in enumerate(top5):
        lbl = f"Top{i+1} {_fmt_build(r)} (RelDPG {r['rel_dpg_score']:.2f})"
        plt.plot(r["x"], r["y"], color=colors[i % len(colors)], linewidth=2.4, marker="D", markersize=6, label=lbl)
    for r in ctrl_rows:
        lbl = f"[CTRL] {_fmt_build(r)} (RelDPG {r['rel_dpg_score']:.2f})"
        plt.plot(r["x"], r["y"], color="#111111", linewidth=2.8, marker="o", markersize=7, linestyle="--", label=lbl)
    plt.title("Vayne Power Spike: 4-Core Ranked Top5 + Control")
    plt.xlabel("Total Gold at Core Timing"); plt.ylabel("DPS (AA + W silverbolts + Q, R@0)")
    plt.grid(True, alpha=0.3); plt.legend(loc="best", fontsize=8); plt.tight_layout()
    plt.show()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_vayne_sim.py -v`
Expected: PASS (4 passed). 실패 시:
- Control not found → `CONTROL_PATH` 아이템이 후보 풀에 모두 존재하는지(botrk∈core1, guinsoo∈core2, terminus∈core3, pd∈core4) 확인. `_build_all_paths` 의 강제 삽입도 확인.
- `create_item_from_key` KeyError → 키 철자 확인(items_data.py 등록 키와 일치).

- [ ] **Step 5: Integration smoke (표 출력, 그래프는 헤드리스면 생략)**

Run(표만, 그래프 창은 수동 확인 — 헤드리스 CI 면 `plt.show()` 전까지 출력 확인):
`.venv/bin/python -c "import matplotlib; matplotlib.use('Agg'); import adc_sim.simulations.vayne as v; rows,ctrl=v._rank_rows(v._build_all_paths()); print('rows', len(rows), 'ctrl', '-'.join(ctrl['path']))"`
Expected: `rows N ctrl botrk-guinsoo-terminus-pd` (N>0).

- [ ] **Step 6: Commit**

```bash
git add adc_sim/simulations/vayne.py tests/test_vayne_sim.py
git commit -m "feat(vayne): simulations/vayne.py 빌드 탐색·5:4:3:3 RelDPG 랭킹·그래프(컨트롤 botrk-guinsoo-terminus-pd)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: `power_compare.py` 통합 (Top1 + Basic)

**Files:**
- Modify: `adc_sim/simulations/power_compare.py`
- Test: `tests/test_vayne_powercompare.py`

**Interfaces:**
- Consumes: `get_vayne_powercompare_builds`, `simulate_vayne_core_path`, `build_vayne_core_report_meta`.
- Produces: `compare_builds()` 출력·데이터에 "Vayne" 포함.

**참고**: 통합은 **CogMaw 분기를 그대로 미러**한다. `power_compare.py`에서 "CogMaw"가 등장하는 모든 지점(import, `_simulate_compare_stat` 분기, `compare_builds`의 top1/basic 딕트·출력라인, `_plot_combined_compare`의 색 맵·챔프 튜플)에 대응하는 "Vayne" 처리를 **추가**한다. 아래 각 지점의 구체 편집을 따른다. **기존 챔프 분기는 수정 금지**.

- [ ] **Step 1: Write the failing test**

`tests/test_vayne_powercompare.py`:
```python
"""Task 6: power_compare 에 Vayne 통합 확인(컴파일·데이터 산출)."""
from adc_sim.simulations import power_compare as pc


def test_simulate_compare_stat_supports_vayne():
    from adc_sim.simulations.vayne import CONTROL_PATH
    cfg = {"path": list(CONTROL_PATH), "doran": "doranblade", "boots": "berserker", "rune_as": 0.0}
    dps, cost, meta = pc._simulate_compare_stat("Vayne", cfg, core_tier=2)
    assert dps > 0 and cost > 0
    assert meta["champion"] == "Vayne"


def test_vayne_in_plot_color_map():
    # _plot_combined_compare 내부 색 맵에 Vayne 존재(리팩터 방지용 가드)
    import inspect
    src = inspect.getsource(pc._plot_combined_compare)
    assert "Vayne" in src
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_vayne_powercompare.py -v`
Expected: FAIL — `_simulate_compare_stat` 가 "Vayne" 미지원(else 분기 KeyError/미처리) 또는 색 맵에 Vayne 없음.

- [ ] **Step 3: Add import**

`adc_sim/simulations/power_compare.py` — CogMaw import 블록(`from adc_sim.simulations.cogmaw import (...)`) 아래에 추가:
```python
from adc_sim.simulations.vayne import (
    simulate_vayne_core_path,
    get_vayne_powercompare_builds,
    build_vayne_core_report_meta,
)
```

- [ ] **Step 4: Add `_simulate_compare_stat` Vayne 분기**

`_simulate_compare_stat` 의 CogMaw 분기(`elif champ_name == "CogMaw":`) **바로 아래**에 미러 추가. CogMaw 분기 형태를 참고해 아래를 삽입:
```python
    elif champ_name == "Vayne":
        dps, cost = simulate_vayne_core_path(
            cfg["path"], core_tier,
            doran_key=cfg.get("doran", "doranblade"),
            boots_key=cfg.get("boots", "berserker"),
            rune_as_bonus=cfg.get("rune_as", 0.0),
        )
        meta = build_vayne_core_report_meta(cfg["path"], core_tier)
        return dps, cost, meta
```
(정확한 반환 형태·변수명은 같은 함수 내 CogMaw 분기와 일치시킬 것.)

- [ ] **Step 5: Add Vayne to `compare_builds()` (top1 + basic)**

`compare_builds()` 에서 CogMaw 로딩부(`cogmaw_best, cogmaw_meta = get_cogmaw_powercompare_builds()`) 아래에 추가:
```python
    print("[Info] Loading Vayne top1/meta from simulation_vayne (can take some time)...")
    vayne_best, vayne_meta = get_vayne_powercompare_builds()
```
top1 configs 딕트(`"CogMaw": {...}` 항목이 있는 딕트)에 항목 추가:
```python
        "Vayne": {"path": vayne_best["path"], "doran": vayne_best["doran"],
                  "boots": vayne_best["boots"], "rune_as": vayne_best["rune_as"]},
```
basic configs 딕트에 항목 추가:
```python
        "Vayne": {"path": vayne_meta["path"], "doran": vayne_meta["doran"],
                  "boots": vayne_meta["boots"], "rune_as": vayne_meta["rune_as"]},
```
출력 라인(챔프별 print) CogMaw 아래에 추가:
```python
    print(f"- Vayne  : [{vayne_best.get('pkg_label','?')}] {'-'.join(vayne_best['path'])} / LT+CutDown (top1 by DPS)")
```
그리고 basic 출력부에 CogMaw 아래:
```python
    print(f"- Vayne  : {'-'.join(vayne_meta['path'])} / LT+CutDown (control botrk-guinsoo-terminus-pd)")
```

- [ ] **Step 6: Add Vayne to `_plot_combined_compare` 색 맵·챔프 튜플**

`_plot_combined_compare` 의 색 맵 딕트(`"CogMaw": "#17becf",` 가 있는 곳)에 추가:
```python
        "Vayne": "#d62728",
```
같은 함수의 챔프 순회 튜플(`for champ in ("Ashe", "Yunara", "KaiSa", "Corki", "CogMaw"):`)에 `"Vayne"` 추가:
```python
        for champ in ("Ashe", "Yunara", "KaiSa", "Corki", "CogMaw", "Vayne"):
```

- [ ] **Step 7: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_vayne_powercompare.py -v`
Expected: PASS (2 passed).

- [ ] **Step 8: Integration smoke (헤드리스)**

Run: `.venv/bin/python -c "import matplotlib; matplotlib.use('Agg'); from adc_sim.simulations import power_compare as pc; from adc_sim.simulations.vayne import CONTROL_PATH; print(pc._simulate_compare_stat('Vayne', {'path':list(CONTROL_PATH),'doran':'doranblade','boots':'berserker','rune_as':0.0}, 3)[:2])"`
Expected: `(<dps>, <cost>)` 양수 튜플.

- [ ] **Step 9: Commit**

```bash
git add adc_sim/simulations/power_compare.py tests/test_vayne_powercompare.py
git commit -m "feat(vayne): power_compare 통합(Top1 by DPS + Basic=컨트롤), CogMaw 분기 미러

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: 회귀 검증 + `CLAUDE.md` 갱신

**Files:**
- Modify: `CLAUDE.md`
- Test: 기존 회귀 스위트 전체(`tests/`)

**Interfaces:** 없음(문서·검증).

- [ ] **Step 1: Full test suite (회귀 — 기존 챔프 수치 불변)**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 전부 PASS. 특히 `test_regression_diff.py`/`regression_snapshot.py`(기존 챔프 DPS 스냅샷) 통과 = Task 1 stash·power_compare 추가가 기존 챔프 수치 불변임 확인. 실패(기존 챔프 diff) 시 Task 1 stash 가 값 저장만 하는지·power_compare 기존 분기 무수정인지 재점검.

- [ ] **Step 2: 시뮬 수동 확인(헤드리스)**

Run: `.venv/bin/python -c "import matplotlib; matplotlib.use('Agg'); import adc_sim.simulations.vayne as v; t=v.get_vayne_4core_top1_build('dpg'); print('top1', '-'.join(t['path']), 'RelDPG', round(t['score'],2), '| ctrl', '-'.join(t['control_path']))"`
Expected: top1 빌드·RelDPG·컨트롤 출력. RelDPG 는 컨트롤(=100 기준) 대비 값. 컨트롤 자신은 ≈100 근처.

- [ ] **Step 3: `CLAUDE.md` 갱신 — 챔피언 목록**

`CLAUDE.md` 의 "정의돼 있는 챔피언" 줄:
```
- 정의돼 있는 챔피언: Ashe / Jinx / Yunara / KaiSa / Corki / Ezreal / **Cog'Maw**.
```
을 다음으로 수정:
```
- 정의돼 있는 챔피언: Ashe / Jinx / Yunara / KaiSa / Corki / Ezreal / Cog'Maw / **Vayne**.
```

- [ ] **Step 4: `CLAUDE.md` 갱신 — 실행 목록**

"## 실행" 섹션의 시뮬 실행 예시 목록(`… adc_sim.simulations.yunara / .kaisa …` 부근)에 vayne 추가:
```
  - `… adc_sim.simulations.vayne` — 베인 4코어 랭킹(온힛+크리 풀, 컨트롤 botrk-guinsoo-terminus-pd)
```

- [ ] **Step 5: `CLAUDE.md` 갱신 — Vayne 도메인 섹션**

`### Cog'Maw ...` 섹션 뒤에 신규 섹션 추가:
```markdown
### Vayne (`champion.py` Vayne + `simulations/vayne.py`) [수치 3소스 교차검증·가설은 spec §9]
- **물리 온힛/크리 하이퍼캐리**. 킷: 평타 + **W 은화살**(3번째 연속 타격마다 `max(floor, %최대체력)`
  **고정(true)피해**; %maxHP 6/7/8/9/10, floor 50~110) + **Q 구르기**(다음 평타 **총AD** 75~115% 추가
  물리·치명·평타리셋) + **R 결전**(고정 추가AD 35/50/65 + Q쿨감 30/40/50%, 지속 8/10/12s).
  base AD 60(**+2.35**, DDragon raw=0 은 데이터버그 → bin+Wiki 채택), AS 0.658(ratio 0.658).
- **은화살 배치(핵심)** [H-VAYNE-W]: `get_one_hit_damage` 오버라이드에서 **proc 루프 바깥** `true_onhit`
  채널에 베인 전용 3타 카운터(`sb_stacks`)로 가산 → **구인수 2배 안 됨**. 고정피해는 **대미지증가
  (PtA/CutDown/LDR거인학살자=`mod_factor`)로 증폭**하되 **경감(방/마저)은 우회** — 베이스가 stash 한
  `_last_damage_amp` 를 곱해 반영. (베이스 `Champion.get_one_hit_damage` 에 `_last_damage_amp = mod_factor`
  stash 1줄 추가 = 유일한 베이스 변경, 값 저장뿐이라 기존 챔프 수치 불변. Corki/DHC true 증폭 일반화는 후속.)
- **Q/R 엔진 모델**: Q 는 스킬 이벤트(무직접피해)로 `q_empowered` arm + `q_reset_pending`(평타리셋
  `ANIM_CANCEL_CLIP`) + 마나30 게이트. 강화 평타는 `p_base×(1+ratio)`(치명·증폭 자연반영). R 은 t=0
  매뉴얼 시전(마나80): `bonus_ad += R_BONUS_AD`, Q쿨 `×(1-R_Q_CDR)`, 지속 만료 시 원복(짧은 버스트라 상시).
- **전용 sim**: cogmaw.py 단일-키스톤(LethalTempo) 미러. 온힛+크리 풀, 컨트롤 **`botrk-guinsoo-terminus-pd`**
  (탐색공간 필수·없으면 RuntimeError). 5:4:3:3 가중 RelDPG, ADC_PACKAGES A/B, K=2. **power_compare 통합**:
  top1=절대 DPS 최강, basic=컨트롤(실전 기준). 스킬 선마 Q→W→E, R=lvl 기반. E(콘뎀)·패시브(이속) 미모델.
```

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(vayne): CLAUDE.md 챔피언 목록·실행·Vayne 도메인 섹션 갱신

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 7: 최종 확인**

Run: `.venv/bin/python -m pytest tests/ -q && git log --oneline feat/vayne -8`
Expected: 전 테스트 PASS + 커밋 7~8개(spec + Task1~7). 작업트리에 사전존재 미커밋 파일은 그대로(건드리지 않음).

---

## Self-Review (계획 작성자 체크)

**1. Spec coverage:**
- §3 수치 → Task 2 클래스 상수(전 값)·§Global Constraints. ✓
- §4.2 은화살 proc 루프 바깥·true·증폭O·경감X → Task 1(stash)+Task 2(구현·테스트 4종). ✓
- §4.3 Q 온힛/치명 라우팅 → Task 2/3(p_base×(1+ratio), 온힛 미증폭, 리셋). ✓
- §4.4 R t=0·bonus_ad·Q쿨감·만료 → Task 2/4. ✓
- §5 클래스 설계 전 메서드 → Task 2. ✓
- §6 sim(풀·컨트롤·스킬레벨표·랭킹·top1·powercompare) → Task 5. ✓
- §7 power_compare → Task 6. ✓
- §8 검증(은화살 3타/비2배/증폭/Q강화/치명/R/마나/회귀) → Task 2~4 테스트 + Task 7 회귀. ✓
- §9 가설 태깅 → 코드 주석 [H-VAYNE-*]. ✓
- §10 구현 순서(Add-Before-Replace) → Task 1→7 순서. ✓

**2. Placeholder scan:** "TBD/TODO/적절히 처리" 없음. 모든 코드 스텝에 실제 코드. Task 6 의 power_compare 편집은 기존 CogMaw 분기 미러(존재 파일 참조) + 구체 삽입 코드 제공. ✓

**3. Type consistency:** `simulate_vayne_core_path(full_path, core_tier, doran_key, boots_key, rune_as_bonus)` — Task 5 정의·Task 6 호출 일치. `get_vayne_powercompare_builds() → (best, meta)` dict 키(path/doran/boots/rune_as/pkg_label) — Task 5 정의·Task 6 소비 일치. `_last_damage_amp` — Task 1 생성·Task 2 소비 일치. `Vayne(level,q_level,w_level,e_level,r_level)` 시그니처 — 전 Task 일관. ✓

---

## Execution Handoff

`docs/superpowers/plans/2026-07-01-vayne-champion.md` 저장 완료.
