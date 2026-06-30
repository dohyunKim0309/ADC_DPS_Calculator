# 마나 자원 모델링 + 코그모(Kog'Maw) 추가 — 설계 스펙 (2026-06-29)

> 본 문서는 brainstorming 합의 결과를 기록한 **설계 스펙**이다. 구현 전 사용자 리뷰 게이트용.
> 거버넌스: 운영 규칙은 `AGENTS.md`가 정본. 모든 신규/변경 메커니즘은 §7 가설 레지스터에
> 태깅한다(AGENTS.md §4). 수치는 **추정 금지·교차검증** 원칙(데이터 워크플로)을 따른다.

## 0. 거버넌스 메모
- **가정 변경 승인**(AGENTS.md §1): "**마나 = 소비 자원**"은 기존 *무한마나* 가정(예: Ezreal
  스펙 H-EZ-9 "무한마나 DPS 레이스")을 **대체**한다. 사용자가 이 세션에서 명시 승인함. 영향은
  §3.6 회귀검증으로 정량 측정·보고한다.
- **구조 변경 승인**(AGENTS.md §2): 신규 파일 `adc_sim/simulations/cogmaw.py`, 신규 챔피언
  `CogMaw`, 신규 아이템 Archangel/Seraph, 엔진(`engine.py`)·베이스(`champion.py`) 보조 추가는
  사용자 승인함. 예약문서 `docs/architecture.md`·`docs/assumptions.md`는 **생성하지 않으며**
  (사용자 확인), 구조/가정 변경 근거는 본 스펙에 기록한다.
- **최소 변경 + Add-Before-Replace + 행위 보존**(AGENTS.md §5): 기존 챔피언 평타 루프와 DPS는
  보존이 1순위. 마나 도입으로 인한 변화는 *의도된 것*(OOM·마나템)만 남도록 §3.6에서 검증한다.

## 1. 목표 / 범위 / 동기
### 1.1 동기 (사용자)
1. **Manamune/대천사의 지팡이(Archangel's→Seraph's) 정확 모델** — 마나 소비/스택/마나기반
   AD·AP는 마나를 자원으로 봐야 정확하다.
2. **Cog'Maw 추가** — 풀킷. R(리빙 아틸러리)의 *증가하는 마나비용*이 마나 자원화로 **자연 스로틀**
   → 기존 "무한마나면 R 과대평가" 문제가 구조적으로 해소.
3. **전 챔피언 마나 정확화** — base/성장 마나 + 초당 마나재생 + 스킬 마나비용.
4. (부수) 메모 todo "Ashe base_mana 픽스"를 흡수.

### 1.2 범위 (Phase 분할)
- **Phase 0 — 마나 자원 엔진(기반, 먼저 강제).** 엔진/베이스 메커니즘 + 전 챔프 마나 데이터 + 검증.
- **Phase 1 — Cog'Maw.** 풀킷 클래스 + 전용 sim 파일. (R은 마나램프로 스로틀.)
- **Phase 2 — 마나 아이템.** Manamune→Muramana 정확화 + Archangel/Seraph 신규.
- 순서: Phase 0 → 1 → 2 (Phase 1↔2는 유연; 기본은 Cog'Maw 먼저).

### 1.3 비목표 (이번 작업 제외)
- `power_compare.py`에 Cog'Maw **통합**(별도 후속 — sim 파일이 제공하는 `get_cogmaw_4core_top1_build`
  등으로 추후 연결).
- `case_ranking.py` Cog'Maw 연계(현재 Ashe 전용 유지).
- 마나 외 자원(분노/기력 등) — 해당 챔프 없음.

## 2. brainstorming 확정 사항
1. **Cog'Maw 산출물**: 전용 sim 파일 먼저(풀 빌드랭킹) → 이후 power_compare는 별도.
2. **Cog'Maw 킷**: **풀킷**(평타 + W + Q패시브/액티브 + E + R).
3. **마나 적용 범위**: **전 챔프 적용 + before/after 검증**(보존이 아니라 정확성 우선, 단 회귀 측정).
4. **버프형 Q 처리**: **이산(마나-게이트) 캐스트로 리팩터** — 단, *정확/최소* 적용:
   - **Ashe Q**(Ranger's Focus, ~50마나)·**Yunara Q**(비용 확정 필요) → 활성 시점을 마나-게이트.
   - **Jinx Q**(Switcheroo)는 **0마나 토글**로 파악 → 게이팅 무의미 → **데이터만**, Q 게이트 제외.
   - (Ashe Q 50 / Jinx Q 0 / Yunara Q 비용은 모두 **출처 확정 대상**, 추정 아님.)
5. **assumptions.md/architecture.md 미생성** — 본 spec에만 기록.

---

# Phase 0 — 마나 자원 엔진

## 3.1 베이스 클래스 (`Champion`) 보조 (행위 보존 추가)
- 신규 상태: `self.current_mana`(전투 중 현재 마나).
- 신규 헬퍼:
  - `can_afford(cost) -> bool`: `self.current_mana + eps >= cost`.
  - `spend_mana(cost)`: `self.current_mana = max(0.0, self.current_mana - cost)`.
  - `regen_mana(dt)`: `self.current_mana = min(self.total_mana, self.current_mana + self.mana_regen_per_sec * dt)`.
  - `mana_regen_per_sec` (property): §3.2.
- `init_combat_state(skill_plan)`(베이스): **풀충전 리셋** `self.current_mana = self.total_mana`.
  - ⚠ `total_mana`는 아이템 보너스(Manamune +500 등)·동적(마나무네 스택)을 포함하므로, 전투 시작
    시점의 풀로 채워진다. Manamune→Muramana 전환 등으로 `total_mana`가 줄면 `current_mana`를
    상한 클램프(`regen_mana(0)` 호출로 보장).
- 베이스 `get_one_hit_damage`(평타)는 **마나 무비용**(평타 루프 불변 — 회귀 0 목표).

## 3.2 초당 마나 재생 모델 [H-MANA-1]
- `mana_regen_per_sec = (base_mp5 + mp5_growth*(level-1)) / 5.0 + (아이템 mp5 합) / 5.0`.
- LoL의 마나재생 단위는 **MP5(5초당)** → /5로 초당 환산.
- **[가설] 단순화**: "최대마나/잃은마나 비례 회복" 등 복합 패시브는 **무시**(기본 MP5만). 짧은 전투
  영향 미미. 아이템 MP5: 현재 풀에 MP5 부여 아이템 거의 없음 → 보통 0. 필요 시 `STAT_KEYS`에
  `mana_regen`(MP5) 키 추가(items_data 단일 출처 규약 유지).

## 3.3 캐스트 마나 게이팅 + 0-dt 스핀 방지 (핵심)
대상: 이벤트 캐스트 시스템 보유 챔프(Kai'Sa·Corki·Ezreal·Cog'Maw).
- **게이팅**: 각 챔프 `_can_cast_skill(name)`에 `and self.can_afford(self.mana_cost[name])` 추가.
- **소비**: `_cast_<skill>`(또는 `pop_due_skill_events` 시전 지점)에서 `self.spend_mana(cost)`.
- **재생 적분**: 각 챔프 `advance_combat_time(dt, ...)`(또는 베이스 공통)에서 `self.regen_mana(dt)`.
- **0-dt 스핀 방지** [핵심 함정]: `get_time_to_next_skill_event`는 스킬이 *쿨은 찼지만 마나가
  부족*할 때 0을 반환하면 엔진이 eps 넛지로 무한 미세전진한다. 후보 시간을 다음으로 보정:
  ```
  cd_left   = cooldowns_remaining[name]
  afford_in = 0.0 if can_afford(cost) else (cost - current_mana) / mana_regen_per_sec
              (mana_regen_per_sec == 0 이고 부족 → inf)
  candidate = max(cd_left, afford_in)
  ```
  → 마나가 정확히 차는 시점에 재시도. 엔진 `run_simulation` 루프 구조 자체는 **무수정**(min-dt
  스텝이 그대로 동작).

## 3.4 버프형 챔프 이산화 (Ashe·Yunara) / Jinx 데이터온리
- **Ashe Q / Yunara Q**: 현재 "활성" 로직(`activate_q`)을 **마나-게이트 이산 활성**으로:
  - 활성 조건 충족 *그리고* `can_afford(q_cost)`일 때만 `activate_q` + `spend_mana(q_cost)`.
  - 마나 부족이면 활성 **지연**(그 사이 버프 미적용). Ashe는 평타가 계속 활성조건을 재평가하므로
    스핀 위험 없음; Yunara도 동일(스택/평타 구동).
  - **버프 효과 모델 자체는 보존**(공속/피해증폭/온힛). = 활성 지점에만 비용·게이트 추가(최소변경).
  - [확인] "리팩터 깊이": 본 안은 *활성=이산 마나 캐스트*(버프 효과 유지). 만약 Q를 이벤트
    캐스트 시스템으로 **완전 이전**(평타 리듬과 분리)을 원하면 더 큰 변경 — §6 스펙리뷰서 확정.
- **Jinx Q**: 0마나 토글(파악값, 출처확정) → 게이트/비용 **없음**. base_mana/성장/MP5 데이터만 채움.
- 그 외 버프형 비-DPS 스킬(Ashe W/E·Jinx W/E·Yunara E 등)은 현재 DPS 루프 미모델 → 마나 비용도
  미부과(모델 일관성). 데이터(존재 비용)는 참고로 기록만.

## 3.5 전 챔피언 마나 데이터 — 확정 (DDragon 16.13.1 + 사용자 확정 2026-06-29)
스키마(챔프별): `base_mana, mana_growth, base_mp5, mp5_growth, mana_cost{skill: 값}`.
출처 표기: ✓=DDragon 16.13.1 확정값(사용자 2026-06-29 확정). Cog'Maw는 4소스 §4.1.

| 챔프 | base_mana | mana_growth | base_mp5 | mp5_growth | 모델 스킬 마나비용 |
|---|---|---|---|---|---|
| **Cog'Maw** | 325 ✓ | 40 ✓ | 8.75 ✓ | 0.7 ✓ | Q 40 · W 40 · E [40,55,70,85,100] · R 40+40/스택(≤9, 40–400) *(Phase 1)* |
| Kai'Sa | 345 ✓ | 40 ✓ | 8.2 ✓ | 0.7 ✓ | Q 55 · W 75(@5) · E 30 · R 100 |
| Corki | 350 ✓ | 40 ✓ | 7.4 ✓ | 0.7 ✓ | Q 80(@5) · W 100(@5) · E 70(@5) · R 35/미사일 |
| Ezreal | 375 ✓ | 70 ✓ | 8.5 ✓ | 1.0 ✓ | Q 40(@5) · W 50 · E 70 · R 100(미모델) |
| Ashe | 280 ✓ | 35 ✓ | 7.0 ✓ | 0.65 ✓ | **Q(Ranger's Focus) 30** |
| Jinx | 260 ✓ | 50 ✓ | 6.7 ✓ | 1.0 ✓ | **평타 무비용**(미니건 기준; Fishbones 20/평타는 [user 결정] 미모델 — Jinx는 데이터만) |
| Yunara | 275 ✓ | 45 ✓ | 7.5 ✓ | 0.75 ✓ | **Q(Cultivation of Spirit) 30** |

- **소싱·확정 완료(2026-06-29)**: 전 챔프 base/성장/MP5 + 모델 스킬비용을 DDragon 16.13.1 교차검증,
  사용자 확정. 소싱이 잡은 **가정 정정 3건**: Ashe Q `50→30`, Kai'Sa E `0→30`(W 75@5), Jinx fishbones
  `무료→20/평타`(단 [user 결정] '평타 무비용' 원칙 유지 위해 미모델). H-MANA-3/4 갱신.
- 데이터 위치: 챔프 base/성장/MP5 + `mana_cost`는 각 챔프 서브클래스(`champion.py`)에 둔다(기존
  base_mana/growth가 거기 있는 관례 유지).

## 3.6 검증 (회귀 방지 — AGENTS.md §5)
- **스냅샷 하니스**(비-플롯): `simulate_<champ>_core_path`를 대표 (빌드,tier) 집합에 대해 호출해
  `(dps, gold)`를 변경 **전** 기록 → 변경 **후** 동일입력 재실행 **diff**.
  - 대상: ashe·yunara·kaisa·corki·ezreal 의 각 컨트롤/대표 빌드 × tier 1~4.
  - 기대: **마나무네/무라마나 미포함 빌드 + 짧은 처치시간**은 Δdps ≈ 0(부동소수 허용오차).
    OOM이 실제로 발생하는 케이스(있으면)·마나템 빌드만 변동 → 변동분 **목록화·보고**.
- **스모크**: 각 챔프 1회 `run_simulation` → DPS 양수·유한, 마나 음수 없음, `current_mana ≤ total_mana`.
- **0-dt 방지 단언**: 마나 부족 상태를 강제(예: base_mana 임시 0)해도 시뮬이 유한 스텝에 종료.

## 3.7 Phase 0 가설
- H-MANA-1: 재생 = 기본 MP5/5(복합 패시브 무시).
- H-MANA-2: 평타 무비용. **마나 하드 바운드(사용자 확정)**: `비용 > 현재마나`면 시전 **불가**(스킵),
  마나가 충분히 찰 때까지 대기. **마나 한도를 넘는 스킬 사용은 절대 발생하지 않음.** §3.3 게이팅으로 강제.
- H-MANA-3: 버프형(Ashe/Yunara) = 활성 지점 마나-게이트(버프효과 보존); Jinx Q=0(게이트 없음).
- H-MANA-4: 비-DPS 스킬(루프 미모델)은 마나 비용도 미부과(모델 일관성).
- H-MANA-5: 엔진의 **"스킬=평타시간 미소비 즉시피해"** 모델을 그대로 유지(사용자 확정, 전 챔프 공통).
  Cog'Maw R(시전+착탄 0.85s)도 평타 수를 줄이지 않으나, 마나 하드바운드(H-MANA-2)가 R 빈도를 제한.

---

# Phase 1 — Cog'Maw (CogMaw 클래스 + 전용 sim)

## 4.1 확정 수치 (출처: LoL Wiki + DDragon 16.13.1 + Meraki + **나무위키**(2026-06-26) 4소스 교차검증)
출처 표기: ✓=2소스+ 일치, [user?]=사용자 확정 필요, [H]=가설 기본값.
> **교차검증 기록**: Meraki는 Q패시브공속(❌[10..30])·Q액티브AP(❌0.8)·W AP계수(❌1%/100AP)에서
> 오류 → wiki+나무위키 일치값 채택. AD성장은 나무위키 최종치(113.87)로 **3.11** 확정(wiki "3.1"은
> 반올림). Q 마나=40 확정([src?] 해소). W 쿨다운 17s·R 잃은체력 연속배율은 나무위키서 신규 확인.

### 4.1.1 기본 스탯
| 항목 | 값 | 근거 |
|---|---|---|
| `base_ad` | 61 | DDragon+Wiki ✓ |
| `ad_growth` | **3.11** | 나무위키 최종치 113.87 ⇒ (113.87−61)/17=**3.11** ✓. Wiki "3.1"은 반올림 표기, DDragon raw=0은 데이터 결함(Ezreal H-EZ-1 선례) |
| `base_as` | 0.665 | DDragon+Wiki ✓ |
| `as_ratio` | 0.665 | [H] DDragon 미노출, 프로젝트 관례(=base_as) |
| `as_growth` | 2.65 (%/레벨) | DDragon+Wiki ✓ |
| `base_range` | 500 | DDragon+Wiki ✓ |
| `base_mana` / `mana_growth` | 325 / 40 | DDragon+Wiki ✓ (§1.1 동기 충족) |
| `base_mp5` / `mp5_growth` | 8.75 / 0.7 | Wiki ✓ |
| (보관, 비-DPS) | HP 635(+99), Armor 24(+4.45), MR 30(+1.3) | DDragon ✓ |

### 4.1.2 스킬 (rank 배열)
- **Q 부식침(Caustic Spittle)**: 패시브 공속 `[5,10,15,20,25]%` · 액티브 마법 `[80,125,170,215,260] + 0.9·AP` ·
  **방어력+마저 −`[16,20,24,28,32]%`, 4초** · 쿨 7s · **마나 40 ✓**.
- **W 바이오아케인(Bio-Arcane Barrage)**: 온힛 마법 = 대상 **최대체력의 `[3,3.75,4.5,5.25,6]%` + (100AP당 1.5%)** ·
  몹 캡 100(더미=챔피언이라 미적용) · **지속 8s · 쿨 17s** · 마나 40. (쿨>지속 → §4.2 쿨관리형 버프)
- **E 공허진흙(Void Ooze)**: 마법 `[70,110,150,190,230] + 0.65·AP` · 쿨 12s · 마나 [40,55,70,85,100] (슬로우=DPS무관).
- **R 리빙아틸러리(Living Artillery)**: 마법 = `(base + 0.75·추가AD + apMin·AP) × mult`,
  base=`[100,140,180]`, apMin=`[0.35,0.4,0.45]`, **mult = `1+(5/6)·잃은체력비율`(40%HP서 ×1.5 도달) / `2.0`(HP≤40%)** ·
  쿨 `[2,1.5,1]s` · 마나 **40 + 40/스택(≤9스택, 40–400), 스택 8s** · 발사후 0.6s.
- 패시브 Icathian Surprise(사망 폭발 true) = **DPS 무관, 미모델**.

## 4.2 클래스 모델링 (`CogMaw(Champion)`) — 각 가설 §4.4
- **W(시그니처)** → `get_champion_onhit(target)` 반환 `(0, w_magic)` **(W 활성 중에만)**,
  `w_magic = (w_pct[idx] + 0.00015·total_ap) · target.max_hp` (w_pct=[.03,.0375,.045,.0525,.06]).
  - **[수정] 쿨관리형 버프**(교차검증 반영): 쿨 17s > 지속 8s라 항시유지 불가(나무위키 명시). →
    Kai'Sa E식 상태버프로 모델: t=0 시전, 8s 활성, 쿨(17s, 스킬가속 적용) 후 재시전, **마나 40 게이트**.
    활성 중 평타만 %최대체력 온힛 획득; 비활성 구간엔 미적용. (구 "항시활성"안은 W 기여를
    ~40–50% 과대평가 → **폐기**.)
  - 구인수 `proc_count=2`로 **자동 2배** + mod_factor/Shadowflame(≤40%) 증폭에 그대로 올라탐
    (코드베이스 기존 온힛 단순화 계승; 코그모 실제 구인수 시너지와 정합).
- **Q 패시브 공속** → 생성 시 상수 `bonus_as_percent += q_passive_as[idx]`. **[H] 시전 시 순간해제 무시**.
- **Q 액티브 / E / R** → 이벤트 캐스트 시스템(Kai'Sa·Corki·Ezreal 미러), 쿨마다 자동 시전 + **마나 게이트(§3.3)**.
  - Q 액티브: 마법 넛지 + **방/마저 %감소 디버프**(Corki E 셔레드 패턴을 %로; 감소→관통 순서 정합 →
    본인 평타/마법 전부 증폭). 디버프는 target.armor/mr 임시 차감 후 만료 복원.
  - R: `추가AD = total_ad − base_attack_ad`(현재레벨 기본AD). 피해 =
    `(base[r] + 0.75·추가AD + apMin[r]·total_ap) × mult`, `mult = 2.0 (대상 HP≤40%) /
    1 + (5/6)·(1−hp_ratio) (그 외; 40%HP서 ×1.5 도달)`. base=[100,140,180]·apMin=[.35,.4,.45].
    시뮬이 current_hp/max_hp를 추적하므로 매 R 시전 시 정확 산정(잃은체력↑ → 배율↑).
    **마나 램프(§3.5)로 자연 스로틀** → 더 이상 무한 R 과대평가 없음(Phase 0의 핵심 수혜).

## 4.3 `simulations/cogmaw.py` 설계 (kaisa.py 미러)
- `CORE_TARGET_STATS`(1~5, kaisa와 동일 HP/방/마저) + `CORE_COGMAW_LEVELS`(9/11/13/15/17),
  `build_target_for_core`.
- `simulate_cogmaw_core_path(full_path, core_tier, doran_key, boots_key, rune_as_bonus)`:
  레지스트리로 아이템 생성, 룬(§4.3 컨트롤), skill_plan(**Q/W/E/R 오토 쿨마다 시전** — W는 8s버프 재시전),
  `run_simulation` → (dps, gold).
- 4코어 전수 탐색 → dedup(combo_best) → `rel_dpg_score`(5:4:3:3 가중, 컨트롤 대비 ×100) → 표 +
  matplotlib 그래프(`__main__` 끝 `plt.show()` 블로킹 — 헤드리스 유의, 기존 관례 동일).
- 후속 power_compare 연동용 `get_cogmaw_4core_top1_build()` / `build_cogmaw_core_report_meta()` 포함.
- **빌드 후보 풀**[H]: guinsoo·kraken·nashor·terminus·bot·rfc·pd·ie·yuntal·statikk·storm (1~3코어) +
  4코어에 rabadon·shadowflame(W의 AP 스케일 반영). `pen_exclusive={terminus,ldr,mortal}` ≤1.
- **컨트롤 빌드**[H]: `kraken-guinsoo-nashor-terminus`(온힛 표준, kaisa CTRL1과 동일 — 탐색 경로 내 필수).
- **룬**[H]: LethalTempo + CutDown(다른 온힛 챔프 일관). §6서 확정.

## 4.4 Phase 1 가설
- H-KOG-1: ad_growth=**3.11**(나무위키 최종치 확정; Wiki 3.1=반올림, DDragon 결함).
- H-KOG-2: W **쿨관리형 버프(지속8s/쿨17s/마나40 게이트)**·`(pct+0.00015·AP)·maxHP` 온힛·구인수 2배·증폭/Shadowflame.
- H-KOG-3: Q 패시브 공속 상수(시전 해제 무시).
- H-KOG-4: Q 액티브 방/마저 %감소(감소→관통 순서)·E·R 쿨마다 시전.
- H-KOG-5: R 추가AD=total_ad−base_attack_ad, **잃은체력 연속배율**(≤40%HP ×2, 그 외 1+(5/6)·잃은체력≤×1.5), 마나램프.
- H-KOG-6: 빌드풀/컨트롤/룬 §4.3.

---

# Phase 2 — 마나 아이템

## 5.1 Manamune → Muramana 정확화
현재 구현(조사): `mana_stacked` **프록시**(실제 마나소비 아님)로 충전, `max_mana_stack=360`에서
Muramana 전환, Muramana Shock·경탄(AD)은 **`total_mana`(풀) 기반**.
- **정확화**:
  - 충전(Mana Charge)을 **실제 마나 소비 + 평타/스킬 적중** 기반으로(LoL 실제 규칙 — [src?] 정확 규칙
    확정). 전환 시 `total_mana` 변동 → `current_mana` 클램프(§3.1).
  - **Muramana Shock 기준 마나**: 현재 코드=풀(total_mana). 실제 규칙(현재마나 vs 최대마나)을
    **[src?] 확정** 후 반영. *현재마나 기반이면 기존 무라마나 빌드 결과가 바뀜* → §3.6 회귀에 포함·보고.
  - 경탄(Awe) AD = bonus 마나 비례 — 풀 기반 유지(또는 실제 규칙대로).
- **[확인]**: 정확화 깊이(실제 충전식 vs 기존 "풀스택 가정 유지")는 §6서 확정. 기본 추천=실제 충전식.

## 5.2 Archangel's Staff → Seraph's Embrace 신규 [src?]
- 신규 아이템 키(items_data) + 동작 클래스(items.py): 마나/AP/AH 스탯, 경탄(AP=마나 비례),
  Mana Charge 충전·Seraph's 전환, (Seraph's) 보호막/추가효과 중 **DPS 관련만** 모델.
- 수치(스탯/마나/충전/AP비율)는 [src?] 교차검증 후 확정. AP 아이템이므로 Cog'Maw(W의 AP스케일)·
  AP 온힛 빌드 탐색에 의미.

## 5.3 Phase 2 가설/확인
- H-ITEM-1: Manamune 실제 충전식·전환·Shock 기준마나([src?] 규칙 확정).
- H-ITEM-2: Archangel/Seraph 신규(DPS 관련 효과만).
- (확인) 무라마나 Shock 기준(현재/최대 마나) — 기존 빌드 결과 변동 가능.

---

## 6. 스펙 리뷰 — 확인 요청 항목
1. ~~Cog'Maw `ad_growth`~~ → **3.11 확정**(나무위키 4소스 교차검증 완료).
2. **버프형 Q 리팩터 깊이**(§3.4): *활성=마나-게이트, 버프효과 보존*(추천) vs *이벤트 캐스트 완전이전*.
3. ~~W 항시활성~~ → **쿨관리형 버프 확정**(§4.2; 쿨17>지속8 교차검증 → 항시활성안 폐기).
4. **Cog'Maw 컨트롤/빌드풀/룬**(§4.3) 추천값 수용?
5. **Manamune 정확화 깊이 + Muramana Shock 기준마나**(§5.1): 실제 충전식(추천) vs 풀스택 가정 유지.
6. **마나 데이터 표**(§3.5) 누락분 — 구현 1단계서 교차검증·확정 후 재확인(절차 동의?).

## 7. 가설 레지스터 (통합 — AGENTS.md §4)
- Phase 0: H-MANA-1..4 (§3.7).
- Phase 1: H-KOG-1..6 (§4.4).
- Phase 2: H-ITEM-1..2 (§5.3).
- 갱신: 본 작업은 Ezreal **H-EZ-9(무한마나)**를 폐기/대체한다(마나=자원). Ezreal은 이제 실제 마나
  보유; 짧은 전투라 결과 불변 예상이나 §3.6서 검증.

## 8. 구현 순서 (검증 레이어 — Add-Before-Replace)
1. **마나 데이터 소싱**(§3.5 누락분 교차검증 → 표 확정 → 사용자 확인).
2. **Phase 0 엔진**: 베이스 헬퍼(§3.1) + 재생(§3.2) + 캐스트 게이팅·0-dt 방지(§3.3) +
   기존 캐스트챔프(Kai'Sa/Corki/Ezreal) 비용 배선 + 버프형(Ashe/Yunara) 이산화 + Jinx 데이터.
   → **스냅샷 회귀(§3.6) 통과**(의도된 변화만).
3. **Phase 1**: `CogMaw` 클래스(풀킷) + 스모크/유닛 → `simulations/cogmaw.py`(탐색·랭킹·표·그래프) → 통합검증.
4. **Phase 2**: Manamune 정확화 + Archangel/Seraph 신규 → 회귀·통합검증.
각 레이어는 다음 진행 전 검증 통과를 전제로 한다(AGENTS.md §5).
