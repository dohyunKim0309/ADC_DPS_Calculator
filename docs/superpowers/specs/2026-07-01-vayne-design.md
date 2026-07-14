# Vayne 챔피언 추가 — 설계 스펙 (2026-07-01)

> 본 문서는 brainstorming 합의 결과를 기록한 **설계 스펙**이다. 구현 전 사용자 리뷰 게이트용.
> 거버넌스: 운영 규칙은 `AGENTS.md`가 정본. 본 작업의 모든 신규 메커니즘은 §9 가설 레지스터에
> `Hypothesis`로 태깅한다(AGENTS.md §4). 수치는 추정 금지·교차검증 원칙을 따른다(§3 출처 표기).

## 0. 거버넌스 메모
- **구조 변경 승인**: 신규 파일 `adc_sim/simulations/vayne.py` 추가, `docs/superpowers/specs/`에
  본 스펙 작성은 사용자가 이 세션에서 명시 승인함(AGENTS.md §2). 별도 예약 문서인
  `docs/architecture.md`·`docs/assumptions.md`는 **생성하지 않는다**(별도 승인 대상). 따라서
  AGENTS.md §2의 "architecture.md 변경로그" 절차는 문서 부재로 보류하고, 구조 변경 근거는 본 §0에 기록.
- **최소 변경·순수 추가**(AGENTS.md §5): 엔진(`engine.py`)·기존 아이템(`items.py`)·기존 아이템 데이터는
  **수정하지 않는다**. `power_compare.py`는 기존 챔피언 로직을 건드리지 않고 Vayne 분기만 **추가**(Cog'Maw
  통합과 동일). **단 하나의 베이스 예외**: `Champion.get_one_hit_damage`에 `self._last_damage_amp =
  mod_factor` **stash 1줄**을 추가(§4.2 은화살 증폭용). 값 저장뿐이라 **모든 기존 챔피언의 반환·수치 불변**
  (행위보존) → AGENTS.md §5.2 대로 명시 선언하고 회귀검증(§8)한다.
- **소유권 선언**(AGENTS.md §6): 대상 파일 = `adc_sim/champion.py`(신규 클래스 추가),
  `adc_sim/simulations/vayne.py`(신규), `adc_sim/simulations/power_compare.py`(Vayne 분기 추가),
  `tests/test_vayne_*.py`(신규), `CLAUDE.md`(문서 갱신). 작업 중 배타 소유.

## 1. 목표 / 범위
- **목표**: 기존 이벤트 기반 엔진 위에서 베인을 "풀 로테이션(평타 + W 은화살 + Q 구르기 + R 결전)"
  DPS 레이스로 모델링하고, 베인 전용 온힛·크리 풀에서 4코어 빌드 랭킹을 산출한다.
- **범위**(사용자 확정 2026-07-01):
  - `adc_sim/champion.py`: `class Vayne(Champion)` 추가.
  - `adc_sim/simulations/vayne.py`: 신규 — 4코어 전수 탐색 + 5:4:3:3 가중 상대-DPG 랭킹 표·그래프,
    `simulate_vayne_core_path`, `get_vayne_4core_top1_build`, `get_vayne_powercompare_builds`.
  - `adc_sim/simulations/power_compare.py`: **Vayne 통합**(Top1 + Basic), Cog'Maw 미러.
  - **제외**: E(콘뎀) 데미지 모델링(넉백/스턴 유틸 — 지속 DPS 기여 미미), 패시브(야밤의 추적자=이속),
    `case_ranking.py` 연계(애쉬 전용 유지).
- **킷 범위**(사용자 확정): **W + Q + R**.
- **패치 기준**: DDragon 16.13.1 + CDragon(patch 16.13, id=67) + 원본 bin + LoL Wiki 교차검증(§3).
  16.13.1 = 현재 최신 패치(프로젝트 다른 챔피언과 동일 기준).

## 2. brainstorming 확정 사항
1. **전투 모델**: 평타 연속 + W(패시브 은화살, 3타마다 자동) + Q(쿨마다 자동, 평타 강화·리셋) +
   R(t=0 1회 시전, 버프 지속). DPS = 누적피해/처치시간, K=2(리스폰 1회) 프로젝트 표준.
2. **W 은화살 = 핵심 메커니즘**: 3번째 연속 타격마다 **고정(true) 피해 = max(최소, 대상 최대체력%)**.
   → `true_onhit` 채널. **proc 루프 바깥**에서 베인 전용 카운터로 가산(§4 핵심).
3. **Q 구르기**: 다음 평타에 **총 AD 비례** 추가 물리(치명 적용) + 평타 리셋(애니캔슬 클리핑).
   엔진 스킬 이벤트로 시전, 마나 게이트(30).
4. **R 결전의 시간**: 고정 추가 AD + Q 쿨감. t=0 시전, 짧은 버스트 동안 상시 활성. 은화살 % **미증가**
   (현 패치 확인). 스텔스/이속 미모델.
5. **아이템 풀/컨트롤**(사용자 확정): 베인 전용 온힛+크리 풀, **컨트롤 = `botrk-guinsoo-terminus-pd`**.
6. **power_compare 통합**: **예**(Top1 + Basic).
7. **수치 출처**: bin + Wiki + DDragon 교차검증(§3). 사용자가 "동일 패치·교차검증" 명시 선택.

## 3. 확정 수치 테이블
출처 표기: ✓=2개+ 소스 일치, [bin]=원본 게임 bin(권위), [wiki]=LoL Wiki, [user]=사용자 확정, [H]=가설.
인덱싱 규약 검증: bin `mSpell/DataValues[i]/values` 는 **index[1..5]=랭크1..5**
(Tumble `cooldownTime=[6,6,5,4,3,2,2]` → 랭크1~5=6/5/4/3/2 가 DDragon 권위값 "6/5/4/3/2"와 일치로 확정).

### 3.1 기본 스탯 (엔진이 사용)
| 항목 | 값 | 근거 |
|---|---|---|
| `base_ad` | 60 | bin(`baseDamageModifiable=60`)+DDragon+Wiki ✓ |
| `ad_growth` | **2.35** | bin(`damagePerLevelModifiable=2.35`)+Wiki ✓. **⚠ DDragon 16.13.1 raw=0 은 데이터 버그** — 채택 안 함 |
| `base_as` | 0.658 | bin(`attackSpeedModifiable`)+DDragon ✓ |
| `as_ratio` | 0.658 | bin(`attackSpeedRatioModifiable=0.658`) ✓ (프로젝트 별도 필드, bin에서 명시 확인) |
| `as_growth` | 3.3 (%/레벨) | bin+DDragon ✓ |
| `base_range` | 550 | bin+DDragon ✓ |
| `base_mana` | 232 | bin(`primaryAbilityResource`)+DDragon ✓ |
| `mana_growth` | 35 | bin+DDragon ✓ |
| `base_mp5` | 7.0 | DDragon(`mpregen=7`)=bin(1.4/s×5) ✓ |
| `mp5_growth` | 0.4 | DDragon(`mpregenperlevel=0.4`)=bin(0.08/s×5) ✓ |
| (보관, 비-DPS) | HP 550(+103), Armor 23(+4.6), MR 30(+1.3) | bin+DDragon ✓ |
| `crit_damage_modifier` | 2.0 | bin(`critDamageMultiplier=2.0`)=베이스 기본 ✓ |

### 3.2 W — Silver Bolts (은화살, 패시브 · 고정피해 · 3타마다)
| 항목 | 랭크 1/2/3/4/5 | 근거 |
|---|---|---|
| 최대체력% (true) | **6 / 7 / 8 / 9 / 10 %** | bin `SilveredBolts/DataValues[0]`(idx1..5)+Wiki ✓ |
| 최소 피해 (floor) | 50 / 65 / 80 / 95 / 110 | bin `DataValues[1]`+Wiki ✓ |
| (몬스터 피해, 미사용) | 140/155/170/185/200 | bin `DataValues[2]` |
| 발동 조건 | **3번째 연속 타격**(평타 또는 스킬) | Wiki+bin ✓ |
| 실제 피해식 | `max(floor[rank], pct[rank]·target.max_hp)` (고정피해) | Wiki("min damage")+bin ✓ |
| R 상호작용 | **은화살 % 미증가** | Wiki(현 패치 명시 없음) ✓ / [H] 패치 변동 추적 |

### 3.3 Q — Tumble (구르기 · 물리 · 온힛 · 치명 · 평타 리셋)
| 항목 | 랭크 1/2/3/4/5 | 근거 |
|---|---|---|
| 다음 평타 추가 물리 | **총 AD의 75 / 85 / 95 / 105 / 115 %** | bin `Tumble/DataValues[0]`(idx1..5=0.75..1.15)+Wiki("total AD") ✓ |
| (AP 계수, 미사용) | +50% AP | Wiki (베인 AP 빌드 없음 → DPS 무영향) |
| 쿨다운 | 6 / 5 / 4 / 3 / 2 s | bin `cooldownTime`+DDragon ✓ |
| 마나 | 30 | bin+DDragon ✓ |
| 온힛 적용 | **예**(다음 평타가 온힛 발동) | Wiki("triggers spell effects") ✓ |
| 치명타 | **적용**(강화 평타가 치명 시 보너스도 치명) | Wiki ✓ |
| 평타 리셋 | 예(구르기 후 즉시 강화평타) | Wiki ✓ → `ANIM_CANCEL_CLIP` 클리핑 |

### 3.4 E — Condemn (콘뎀 · v1 제외, 기록만)
- base 50/85/120/155/190 (+50% **추가**AD), 벽 충돌 시 75/127.5/180/232.5/285 (+75% 추가AD) + 스턴.
  근거: Wiki+bin. **v1 모델·랭킹 제외**(유틸 · 지속 DPS 미미). 클래스에 `e_level` 보관만.

### 3.5 R — Final Hour (결전의 시간 · 버프)
| 항목 | 랭크 1/2/3 | 근거 |
|---|---|---|
| 추가 AD (고정) | **35 / 50 / 65** | bin `Inquisition/DataValues[0]`(idx1..3)+Wiki ✓ |
| 지속시간 | 8 / 10 / 12 s | bin `DataValues[1]`+Wiki ✓ (킬 시 연장 — 미모델) |
| Q 쿨감소 % | 30 / 40 / 50 % | bin `DataValues[6]`+Wiki ✓ |
| 쿨다운 | 100 / 85 / 70 s | bin+DDragon ✓ |
| 마나 | 80 | bin+DDragon ✓ |
| 은화살 상호작용 | 없음(§3.2) | Wiki ✓ |

## 4. 엔진 통합 & "은화살 배치" 결정 (핵심)
### 4.1 데미지 모델의 두 온힛 경로 (조사 결과)
- **proc 루프 안**(`get_one_hit_damage` §2.2): 아이템 `on_hit` + 룬 온힛 + `get_champion_onhit`.
  이 번들은 `total_applications = proc_count(구인수 max 2) + extra(주문검 가산)` **회 반복**된다.
  즉 **구인수 3타 강타에서 2배**로 실행됨.
- **고정(true) 채널**: `get_one_hit_damage` 반환 6튜플의 `true_base`/`true_onhit` 는 **증폭·경감·
  proc 루프 모두 우회**(엔진이 무경감 가산). 프로젝트의 기존 고정피해 관례.

### 4.2 결정: 은화살은 **proc 루프 바깥 · 고정 채널**에 베인 전용 카운터로 가산 [H-VAYNE-W]
- **근거(핵심)**: 은화살을 `get_champion_onhit`(2-튜플 물리/마법)로 넣으면 **proc 루프 안**이라
  구인수 3타에서 **2배로 잘못 발동**한다. 또한 은화살은 물리/마법이 아닌 **고정피해**다.
  → `Vayne.get_one_hit_damage` 오버라이드에서 **직접** `true_onhit` 성분으로 가산한다.
- **카운터**: `self.sb_stacks`(전용). `init_combat_state`에서 0 리셋, **평타 1회당 +1**
  (강화 Q평타 포함 — 1개 평타이므로 1스택). 3 도달 시 `max(floor, pct·max_hp)` 를 `true_onhit`에
  더하고 0 리셋. 구인수 proc_count 와 **독립**(은화살은 타격 수를 세지 온힛 적용 횟수를 세지 않음).
- **증폭 적용(사용자 정정 2026-07-01)**: 고정(true)피해도 **대미지 증가 효과(damage amplification)에는
  적용된다** — 집중공격(PtA 8%)/최후의일격(CutDown 8%)/은총(CoupDeGrace 8%)/**도미닉 거인학살자
  (LDR `get_damage_modifier`, 추가체력 비례 ≤15% — `items.py:720`)**. 이 셋 모두 이미 `damage_multiplier`에
  합산됨 → `mod_factor` stash 하나로 자동 커버(사용자가 든 세 예시 정확히 반영). 단 **경감(방어력/마저)은
  우회**(true의 본질). 즉 은화살은 `mod_factor(=1+damage_multiplier)`로 증폭하되 경감·관통은 받지 않는다.
  - **구현(최소·회귀안전)**: 베이스 `Champion.get_one_hit_damage`가 이미 계산하는 `mod_factor`를
    반환 직전 **`self._last_damage_amp = mod_factor` 로 stash**(값만 저장 — 기존 반환/동작 불변 →
    회귀 0). `Vayne.get_one_hit_damage`가 `super()` 호출 후 이 값을 읽어 은화살에 곱한다.
  - **범위 제외**: `c44_multiplier`(별도 배수·니치)와 `Shadowflame`(마법 전용·≤40%HP)은 은화살 증폭서 제외.
    [H-VAYNE-W-2: C44/Shadowflame 미적용은 단순화].
  - **⚠ 발견된 별도 이슈(본 작업 범위 밖)**: 현재 엔진은 true 채널을 raw 반환 → **Corki 패시브 고정피해
    (`champion.py:1496`)·Demon Hunter's Crossbow(`items.py:685`) 의 true 도 증폭 미적용** 상태.
    이는 동일 원리상 부정확하나, 일반 엔진 수정 시 기존 Ashe(DHC 포함 레퍼런스 빌드)·Corki DPS 가
    바뀌어 **회귀·별도 승인 대상**. 본 스펙은 **Vayne 국소 처리만** 하고 일반화는 후속 과제로 남긴다.
- **Q-roll 스택**: 은화살은 "타격 또는 스킬"에 스택되나, 모델상 Q 구르기 자체는 무피해→ 스택은
  **강화 평타**가 담당(별도 스택 안 셈). 콘뎀 미모델. → 실질 "평타 3회마다 발동". [H-VAYNE-W]

### 4.3 Q 구르기 온힛/치명 라우팅
- Q는 **엔진 스킬 이벤트로 방출하되 직접 피해 0** — 실제 강화 물리는 **다음 평타**(`get_one_hit_damage`)에서
  발생. 즉 Q 시전 = (a) `q_empowered=True` arm, (b) `q_reset_pending=True`(평타 리셋), (c) `cast_spell`
  (주문검 장전 등), (d) 마나 30 차감, 쿨 설정. 스킬 이벤트 튜플 `("q",0,0,False)`(버프형, 무피해).
- **강화 평타**(`get_one_hit_damage`): armed 이면 `p_base *= (1 + ratio[q_level])`. `p_base`는 부모가
  이미 치명 기대값(`total_ad·(crit_dmg·crit+(1-crit))`)을 반영 → ratio 곱으로 **보너스도 치명 자연 반영**.
  온힛(`p_onhit`)은 **미증폭**(강화평타도 온힛은 1회) — 애쉬 Q 관례와 동일. armed 소비.
- **주문검/에너자이즈드**: Q는 `cast_spell`로 장전만, 발동은 다음(강화) 평타의 on_hit. 베인 컨트롤·풀엔
  주문검 없음(트리니티/에센스는 풀 제외) → 영향 경미하나 훅은 정확히 유지.

### 4.4 R 결전의 시간
- t=0 매뉴얼 시전(마나 80). 활성 시 `self.bonus_ad += r_bonus_ad[r_level]`, `q_cd_reduction` 설정.
  지속 8/10/12s. 짧은 버스트(K=2, 보통 <12s)라 **만료 전 처치** → 사실상 상시. 만료 이벤트는
  `get_time_to_next_state_event`로 등록하되(정확성), 만료 시 bonus_ad 원복. [H-VAYNE-R]
- Q 쿨감: `apply_haste_to_cooldown` 후 추가로 `×(1 - q_cd_reduction)` 적용(R 활성 시).

## 5. 클래스 구현 설계 (`Vayne(Champion)`)
Cog'Maw 이벤트 인터페이스 미러링 + Ashe 평타-리셋 관례:
- **생성자**: `Vayne(level=1, q_level=5, w_level=5, e_level=1, r_level=3)`. §3 base 스탯,
  스킬 데이터 배열(`q_ad_ratio`, `w_pct`, `w_floor`, `r_bonus_ad`, `r_duration`, `r_q_cdr`),
  마나비용 `{"q":30}`(R은 80, 1회). 상태: `cooldowns_remaining={"q","r"}`, `sb_stacks`,
  `q_empowered`, `q_reset_pending`, `r_active`, `r_end_time`, `auto_skill_*`, `manual_skill_casts`.
- `init_combat_state(skill_plan)`: `super()`(마나 풀충전) + 쿨/`sb_stacks=0`/버프 리셋 + skill_plan 반영.
- `advance_combat_time`: `super()`(마나재생) + 쿨 감소 + R 만료 점검(만료 시 bonus_ad 원복).
- `get_time_to_next_skill_event`: Q 오토(쿨·마나 `_afford_in`) + 매뉴얼(R@0). Cog'Maw 패턴.
- `get_time_to_next_state_event`: R 만료 dt.
- `pop_due_skill_events`: 매뉴얼(R) + 오토(Q) → `_cast_skill`.
- `_cast_skill`: `q`→`_cast_q`(arm+리셋+cast_spell, 마나30, 쿨), `("q",0,0,False)`.
  `r`→`_cast_r`(bonus_ad+= , r_active, 마나80, 쿨), `("r",0,0,False)`.
- `get_attack_interval`: `q_reset_pending`이면 `min(super(), ANIM_CANCEL_CLIP)` 후 소비(Ashe 미러).
- `get_one_hit_damage(target,time)` 오버라이드:
  1. 부모 호출 → 6튜플(평타 물리/온힛/증폭/치명 정상).
  2. **Q 강화**: `q_empowered`면 `p_base *= (1+q_ad_ratio[q_level-1])`, 소비.
  3. **은화살**: `sb_stacks += 1`; `==3`이면 `sb = max(w_floor[w-1], w_pct[w-1]*target.max_hp)`,
     `pt_onhit += sb * self._last_damage_amp`(대미지 증가 룬/아이템 증폭 반영·경감 우회, §4.2), `sb_stacks=0`.
  4. 반환 `(p_base, m_base, p_onhit, m_onhit, pt_base, pt_onhit)`(true_onhit에 증폭된 은화살 합산).
- **베이스 최소 추가**(회귀안전): `Champion.get_one_hit_damage` 반환 직전 `self._last_damage_amp = mod_factor`
  stash 1줄 추가(값 저장만 — 기존 반환·동작·수치 불변). AGENTS.md §5.2 대로 **명시 선언**, 회귀검증.
- **마나**: 하드 바운드(현 엔진 Phase 0). Q 30/시전, R 80/1회. Cog'Maw 와 동일 게이트.
- **Q 선마 가정**: `q_level` 우선. 코어별 스킬레벨 표는 §6.

## 6. `simulations/vayne.py` 설계
`cogmaw.py`를 템플릿으로(단일 키스톤 LethalTempo — Ashe/Yunara 계열):
- `CORE_TARGET_STATS`(공용), `CORE_VAYNE_LEVELS`(1:lvl9,2:11,3:13,4:15), `build_target_for_core`.
- `_skill_levels_for_core(core)`: **Q 선마 → W 차선마 → E 후마**, R=lvl 기반(6~10→1, 11~15→2, 16+→3).
  포인트 정합 표(E는 DPS 미모델 → 값 무관, `e_level`은 배열 색인용 하한 1로 floor):
  | core | level | q / w / e / r |
  |---|---|---|
  | 1 | 9 | 5 / 3 / 1* / 1 |
  | 2 | 11 | 5 / 4 / 1* / 2 |
  | 3 | 13 | 5 / 5 / 1* / 2 |
  | 4 | 15 | 5 / 5 / 3 / 2 |
  (`*`=실제 0포인트지만 floor 1; E 미모델이라 DPS 무영향. 튜닝 가능.) [H-VAYNE-SKILL]
- `simulate_vayne_core_path(full_path, core_tier, doran_key, boots_key, rune_as_bonus)`:
  레지스트리로 아이템 생성, `set_rune(LethalTempo())`, `set_sub_rune(CutDown())`,
  skill_plan = `{"manual_casts":[(0.0,"r")], "auto_cast":{"q":True,"r":False}, "auto_order":["q"]}`
  (R은 t=0 1회, Q 오토), `run_simulation(K=2)` → (dps, cost).
- **아이템 풀**(베인 온힛+크리):
  - core1: `botrk, guinsoo, kraken, terminus, wit, runaan, pd, rfc, statikk, yuntal25, c44, storm, collector`
  - core2: 위 + (2코어부터 크리 코어) — botrk/guinsoo/kraken/terminus/wit/runaan/pd/ie/rfc/collector/yuntal25/statikk
  - core3: `ie, ldr, guinsoo, terminus, pd, collector, wit, kraken`
  - core4: `ie, ldr, pd, runaan, rfc, collector, kraken, wit, statikk, terminus`
  - **pen 배타** `{ldr, mortal, terminus}` ≤1. **컨트롤 `botrk-guinsoo-terminus-pd` 는 탐색공간 필수**
    (없으면 RuntimeError). yuntal25 는 §스택 관례(구매코어 10%→다음 25%).
- `get_vayne_4core_top1_build(rank_by="dpg")`: dedup(정렬 combo 최고점) + 컨트롤 정규화 5:4:3:3
  RelDPG. Cog'Maw `get_cogmaw_4core_top1_build` 미러(단, 키스톤 LT 고정).
- `get_vayne_powercompare_builds()`: (best, meta) 반환 — best=Top1(rank_by="dps"),
  meta=컨트롤(botrk-guinsoo-terminus-pd, 최적 패키지). Cog'Maw `get_cogmaw_powercompare_builds` 미러.
- `__main__`: 5:4:3:3 랭킹 표 + matplotlib 그래프(Top5+컨트롤, DPS 라벨). `plt.show()` 블로킹(헤드리스 유의).

## 7. `power_compare.py` 통합 (추가 전용)
- `_simulate_compare_stat`에 `elif champ_name == "Vayne":` 분기 추가(Cog'Maw 분기 미러 —
  `simulate_vayne_core_path` 호출, 자체 패키지).
- `compare_builds()`: `get_vayne_powercompare_builds()` 로드, top1/basic 딕트에 "Vayne" 추가,
  출력 라인·색상(`_plot_combined_compare`의 색 맵 + 챔피언 튜플에 "Vayne") 추가.
- **기존 챔피언 분기·로직 무수정**(순수 추가). 회귀: 기존 챔피언 DPS·랭킹 불변 확인(§8).

## 8. 검증 절차 (AGENTS.md §5)
- **스모크**: Vayne 인스턴스화 → `run_simulation` 1회 → DPS 양수·유한, 공속/마나 정상 단언.
- **유닛**(`tests/test_vayne_*.py`):
  - **은화살 3타 주기**: 무구인수 빌드에서 평타 1·2 는 고정피해 0, 평타 3 에
    `max(floor, pct·max_hp)` 정확히 발생. 4·5 다시 0, 6 발생.
  - **은화살 × 구인수 비-2배**: 구인수 보유 빌드에서도 은화살은 3타마다 **1회**(proc_count 2배 안 됨).
  - **은화살 증폭**: PtA 활성(8%)·CutDown(고HP 8%) 시 은화살 고정피해 `×mod_factor` 정확히 증가;
    **방어력만 바꿔도 은화살 불변**(경감 우회 확인). 베이스 `_last_damage_amp` stash 가 기존 챔프 수치 불변임도 단언.
  - **Q 강화 평타**: armed 평타 물리 ≈ 부모물리×(1+ratio), 다음 평타 정상. Q 후 평타간격 클리핑 확인.
  - **Q 치명 상호작용**: 치명 빌드에서 Q 보너스도 치명 기대값 반영(p_base 배수 검증).
  - **R 버프**: R 시전 시 `total_ad` += r_bonus_ad, Q 쿨 감소 반영. 지속 만료 시 원복.
  - **마나 게이트**: Q 마나 부족 시 시전 지연(off-CD라도), R 80 차감.
- **회귀**(AGENTS.md §5.3): 기존 챔피언(Ashe/Yunara/Kai'Sa/Corki/Cog'Maw/Jinx) DPS 불변
  (`tests/regression_snapshot.py`·`test_regression_diff.py`). 베인은 순수 추가 → 기존 스냅샷 불변 기대.
  power_compare 변경 후 기존 5챔프 출력 불변 확인.
- **통합**: `python -m adc_sim.simulations.vayne` 표 육안검사(컨트롤 존재, 코어별 DPG 정합),
  `python -m adc_sim.simulations.power_compare` 에 Vayne 행 등장·정합.

## 9. 가설 레지스터 (AGENTS.md §4 — 전부 `Hypothesis`)
- **H-VAYNE-W-1**: 은화살 = proc 루프 바깥 고정채널, 베인 전용 3타 카운터, **구인수 2배 안 됨**.
- **H-VAYNE-W-2**: 은화살 고정피해는 **대미지 증가 효과에 증폭됨**(PtA/CutDown/CoupDeGrace/아이템 amp =
  `mod_factor`), **경감(방/마저)은 우회**. C44·Shadowflame은 제외(단순화). 베이스 `_last_damage_amp` stash 경유.
  (사용자 정정: 실게임에서 true는 증폭 O·경감 X.) 일반 엔진화(Corki/DHC true 증폭)는 후속 과제.
- **H-VAYNE-W-3**: Q 구르기는 무피해→은화살 스택은 강화평타가 담당(실질 평타 3회마다), 콘뎀 미모델.
- **H-VAYNE-Q-1** *(2026-07-14 정정)*: Q 강화 = 평타 본체 `p_base`(크리 기대값·C44 포함) + Q 추가딜
  `total_ad × ratio × _last_damage_amp` (**크리·C44 둘 다 미반영** — 실 LoL 동작).
  대미지증가(PtA/CutDown/거인학살자) 는 적용. 온힛 미증폭(1회), 평타 리셋=ANIM_CANCEL_CLIP.
  이전 스펙은 "보너스 치명 자연반영" 로 잘못 기술 → 크리 코어(IE/Yun/PD/C44) Q 이득이 실측보다 크게
  계산돼 랭킹을 과대평가하고 있었음. C44 %증폭은 오로지 기본 평타 AA(phys_base) 에만 적용(사용자 확인).
- **H-VAYNE-R-1**: R t=0 시전·상시(짧은 버스트), bonus_ad 고정 가산 + Q 쿨감, 은화살 % 미증가, 스텔스/이속 미모델.
- **H-VAYNE-SKILL-1**: 스킬 선마 Q→W→E, R=lvl 기반(코어별 표). W선마 선호 시 손쉽게 교체.
- **H-VAYNE-DATA-1**: `ad_growth=2.35`(DDragon raw=0 버그 배제, bin+Wiki 채택).
- **H-VAYNE-CTRL-1**: 컨트롤 `botrk-guinsoo-terminus-pd`(사용자 확정), 탐색공간 필수.

## 10. 구현 순서(검증 레이어 — Add-Before-Replace)
1. `Vayne` 클래스(W+Q+R, 쿨/스택/버프/마나) + 스모크·유닛 테스트 → 검증.
2. `simulations/vayne.py`(탐색·랭킹·표·그래프) → 통합 실행 검증(컨트롤 존재).
3. `power_compare.py` Vayne 통합 → 5+1 챔프 비교 검증.
4. (회귀) 기존 챔피언 DPS·랭킹 불변 확인.
5. `CLAUDE.md` 갱신(챔피언 목록 + Vayne 섹션 + 새 sim 파일).
각 레이어는 다음 진행 전 검증 통과를 전제로 한다(AGENTS.md §5).
