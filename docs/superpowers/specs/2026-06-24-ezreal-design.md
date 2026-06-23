# Ezreal 챔피언 추가 — 설계 스펙 (2026-06-24)

> 본 문서는 brainstorming 합의 결과를 기록한 **설계 스펙**이다. 구현 전 사용자 리뷰 게이트용.
> 거버넌스: 운영 규칙은 `AGENTS.md`가 정본. 본 작업의 모든 신규 메커니즘은 §9 가설 레지스터에
> `Hypothesis`로 태깅한다(AGENTS.md §4). 수치는 추정 금지·교차검증 원칙을 따른다.

## 0. 거버넌스 메모
- **구조 변경 승인**: `docs/superpowers/specs/` 트리 생성과 신규 파일 `adc_sim/simulations/ezreal.py`
  추가는 사용자가 이 세션에서 명시 승인함(AGENTS.md §2). 단, 별도 예약 문서인
  `docs/architecture.md`·`docs/assumptions.md`는 **생성하지 않는다**(별도 승인 대상).
  그 결과 AGENTS.md §2의 "architecture.md 변경로그 추가" 절차는 해당 문서 부재로 보류하며,
  구조 변경 승인 근거는 본 스펙 §0에 기록한다.
- **최소 변경 원칙**(AGENTS.md §5): 엔진(`engine.py`)·기존 아이템(`items.py`)·기존 챔피언은
  수정하지 않는 것을 1순위 목표로 한다. 불가피한 베이스 클래스 보조 추가가 필요하면
  §5에서 "행위 보존(behavior-preserving) 추출"로 명시 선언하고 회귀검증한다.

## 1. 목표 / 범위
- **목표**: 기존 이벤트 기반 엔진 위에서 이즈리얼을 "풀 로테이션(평타 + 스킬)" DPS 레이스로
  모델링하고, 코어 빌드 랭킹을 산출한다.
- **범위**(사용자 확정):
  - `adc_sim/champion.py`: `class Ezreal(Champion)` 추가(Corki 패턴 미러링).
  - `adc_sim/simulations/ezreal.py`: 신규 — 4코어 빌드 전수 탐색 + 5:4:3:3 가중 상대-DPG 랭킹
    표·그래프, `simulate_ezreal_core_path`, `get_ezreal_4core_top1_build`.
  - **제외**: `power_compare.py` 통합, `case_ranking.py` 연계(추후 별도 작업).
- **패치 기준**: DDragon 16.12.1 + CDragon(live client) + LoL Wiki 교차검증(아래 §3).

## 2. brainstorming 확정 사항
1. **전투 모델**: 평타 연속 + Q/W/E 쿨마다 시전(엔진 이벤트 시스템). DPS = 누적피해/처치시간.
2. **v1 스킬 범위**: 패시브 + 평타 + **Q + W + E**. **R(궁) 제외**
   (장쿨 글로벌 버스트가 kill-time 기반 DPS를 왜곡 → Corki가 W를 랭킹서 빼는 것과 동일 논리).
3. **Q 치명타 여부**: **Q는 치명타가 적용되지 않음**(사용자 확정). 치명타/무한대검은 **평타에만** 이득.
   → 모델상 이즈리얼에서 크리 빌드의 가치가 약화됨. 패치 변동 시 손쉽게 뒤집도록 가설 태깅(§9).
4. **Q 온힛 적용**: Q는 온힛 효과를 적용함(확정). 라우팅은 §4 참조.
5. **Q 쿨 환급 루프**: Q 적중 시 모든 스킬 쿨 −1.5초(시뮬상 Q는 더미에 항상 적중).
6. **수치 출처**: CDragon pull + DDragon/Wiki 교차검증 → 사용자 확정(§3).

## 3. 확정 수치 테이블 (Hypothesis 기본값 포함)
출처 표기: ✓=2개+ 소스 일치, [user]=사용자 확정, [H]=가설 기본값(저영향, 추후 손쉽게 교체).

### 3.1 기본 스탯 (엔진이 사용)
| 항목 | 값 | 근거 |
|---|---|---|
| `base_ad` | 60 | DDragon+Wiki ✓ |
| `ad_growth` | **3.75** | [user] (DDragon raw=0은 데이터 오류로 판단, Wiki=3.75 채택) |
| `base_as` | 0.625 | DDragon+Wiki ✓ |
| `as_ratio` | 0.625 | [H] DDragon 미노출, 프로젝트 관례(=base_as). **스펙 리뷰서 확인 요청** |
| `as_growth` | 2.5 (%/레벨) | DDragon+Wiki ✓ |
| `base_range` | 550 | DDragon ✓ |
| `base_mana` | 375 | DDragon+bin ✓ |
| `mana_growth` | 70 | DDragon+bin ✓ |
| (보관, 비-DPS) | HP 600(+102), Armor 24(+4.2), MR 30(+1.3) | DDragon ✓ |
| `crit_damage_modifier` | 2.0 | 베이스 클래스 기본값 ✓ |

### 3.2 패시브 — Rising Spell Force
- 스킬 적중 1회당 공속 스택 +1, 스택당 **+10%** 공속, **최대 5스택**(=+50%), **6초** 지속(적중 시 갱신).
- 근거: Wiki + DDragon("up to 5 times") ✓. [H] 스택당 % / 지속은 패치 변동 가능 → 가설 태깅.

### 3.3 Q — Mystic Shot (물리 · 온힛 적용 · 비치명 · 쿨환급)
| 항목 | 값 | 근거 |
|---|---|---|
| base | 20/45/70/95/120 | Wiki ✓ |
| AD 계수 | **1.30 × TOTAL AD** | Wiki ✓ (총AD 확정 — 빌드 핵심) |
| AP 계수 | 0.15 | [H] CDragon=0.15 vs Wiki=0.40 충돌. AD빌드 저영향 → 기본 0.15, §8 확인 |
| 쿨 환급(적중) | 모든 스킬 −1.5초 | Wiki+DDragon ✓ |
| 쿨다운 | 5.5/5.25/5.0/4.75/4.5 | DDragon ✓ |
| 치명타 | **없음** | [user] |
| 온힛 적용 | **예** | Wiki ✓ (§4 라우팅) |

### 3.4 W — Essence Flux (마법 · 표식+기폭, 단순화)
- base 80/135/190/245/300, **+1.0 추가AD**, **+0.9 AP**, 쿨 8.0. (Wiki; CDragon blank → [H])
- **단순화 가정**[H]: 단일 고정 더미가 표식을 받고 즉시 다음 스킬/평타로 기폭된다고 보아,
  W 시전을 "1회 마법 피해"로 처리(표식 지속/기폭 타이밍 미세모델 생략). Corki W 트레일 단순화와 동궤.

### 3.5 E — Arcane Shift (마법)
- base 80/130/180/230/280, **+0.6 추가AD**, **+0.75 AP**, 쿨 26/23/20/17/14. (Wiki+CDragon ✓; AD계수 CDragon=0.5 vs Wiki=0.6 → [H] 0.6 채택)

### 3.6 R — Trueshot Barrage (v1 제외, 추후용 기록)
- base 350/550/750, **+1.0 추가AD**(Wiki+CDragon ✓), +AP 0.9(CDragon)/1.1(Wiki)[H], 쿨 120/105/90.
- v1에서는 **모델·랭킹 모두 제외**. 클래스에 `r_level`만 보관(미사용) 또는 추후 추가.

## 4. 엔진 통합 & "Q 온힛" 결정 (핵심)
### 4.1 엔진의 두 경로 (조사 결과)
- **스킬 경로**(`pop_due_skill_events`→`is_skill_hit=True`): 엔진이 `get_on_skill_hit_damage`
  (=아이템 `on_skill_hit` 훅) + 룬 스킬 훅만 호출. **평타 `on_hit` 번들은 실행 안 함.**
- **평타 경로**(`get_one_hit_damage`): 아이템 `on_hit`, 주문검 발동, proc_count 확장, 증폭, 치명타.

### 4.2 기존 아이템에서 확인된 사실 (수정 불필요)
- **Manamune/Muramana**: `on_hit`·`on_skill_hit` **둘 다** 구현.
  → Q/W/E(스킬 적중)가 **자동으로** 마나무네 스택을 충전하고 무라마나 충격(스킬 3%)을 발동.
  ⚠ 따라서 Q 온힛 번들에서 **Manamune은 제외**해야 함(이중 계산 방지).
- **주문검(Trinity/EssenceReaver)**: `on_spell_cast`로 **장전**, 다음 `on_hit`(평타)에서 **발동**.
  → Q/W/E는 `cast_spell`로 **장전만** 하고, 발동은 **다음 평타**가 담당. Q 자체는 주문검 발동 안 함.
- **에너자이즈드(Statikk/RFC/Stormrazor)**: 평타 기반 → **Q에 적용 안 함**.

### 4.3 결정: Q 온힛 충실도 — **풀 allow-list 확정**(§8.1, 사용자 2026-06-24)
이즈리얼의 주력 피해(스팸되는 Q)가 온힛 아이템을 못 살리면 **온힛 빌드가 과소평가**되어
랭킹이 왜곡된다. 따라서 v1 **확정안**:
- Q는 스킬 이벤트로 방출(엔진이 Manamune/Muramana + 룬 스킬훅 자동 처리).
- **추가로**, `Ezreal._cast_q` 내부에서 **명시적 allow-list**의 "진짜 온힛 피해" 아이템만
  로컬 호출해 Q 온힛 피해에 합산: **Kraken / BotRK / Guinsoo(+proc_count) / Wit's End /
  Terminus / Nashor's**. (가설 태깅; 각 아이템 포함 여부가 가설)
- **제외**: 주문검(장전만), Manamune(스킬경로서 처리), 에너자이즈드/평타전용.
- 엔진·아이템 **무수정**. 필요 시 베이스 클래스에 **행위보존 보조 메서드**
  `_assemble_q_onhit(target)` 하나만 추가(기존 동작 불변, 회귀검증).
- **대안(축소 v1)**: "스킬경로만"(Manamune/Muramana·룬만, 평타전용 온힛은 Q서 미적용).
  더 단순하나 온힛 빌드를 과소평가. → §8에서 사용자 선택.
- **반환 튜플 제약**[주의]: 스킬 이벤트 튜플은 `(name, phys, magic, is_skill_hit)`로 **고정(true)
  피해 슬롯이 없음**. allow-list 온힛에 고정피해 성분(예: Kraken 모델에 따라)이 있으면 그대로
  전달 불가 → 구현 시 (a) 해당 아이템을 allow-list서 제외하거나 (b) 사전 경감 환산해 phys로
  합산하는 등 별도 처리 필요. §7 유닛검증에 포함.

## 5. 클래스 구현 설계 (`Ezreal(Champion)`)
Corki/Kai'Sa의 이벤트 인터페이스를 그대로 미러링:
- 상태: `cooldowns_remaining={"q","w","e"}`, 패시브 스택(`spell_stacks`, `stack_expire_time`),
  `auto_skill_*`, `manual_skill_casts`.
- `init_combat_state(skill_plan)`: 쿨/스택 초기화, skill_plan 반영(매뉴얼/오토).
- `advance_combat_time`: 쿨 감소, 패시브 스택 만료(6초) 시 공속 환원.
- `get_time_to_next_skill_event` / `get_time_to_next_state_event`: 쿨/스택만료 기준 dt.
- `pop_due_skill_events`: 매뉴얼+오토로 `_cast_q/w/e` 호출, `(name,phys,magic,is_skill_hit)` 반환.
- `_cast_q(time)`:
  1. Q 물리 = base[q] + 1.30·total_ad + 0.15·total_ap **(치명타 미적용)**.
  2. **쿨 환급 루프**: `cooldowns_remaining` 전 항목 −1.5초(0 클램프).
  3. `cast_spell(time)`로 주문검 **장전**.
  4. §4.3 allow-list 온힛 합산(권고안 채택 시).
  5. 패시브 스택 +1·갱신(공속 버프 적용).
  6. 반환 `("q", q_phys, q_magic, True)` — `q_phys`=Q기본물리 + allow-list 물리온힛,
     `q_magic`=allow-list 마법온힛. Manamune/Muramana·룬 스킬훅은 엔진 스킬경로
     (`get_on_skill_hit_damage`)가 자동 처리(이중호출 금지). true 성분은 §4.3 제약 참조.
- `_cast_w(time)` / `_cast_e(time)`: 각 마법 피해(§3.4/§3.5) + `cast_spell` 장전 + 패시브 스택 +1.
- `get_one_hit_damage(target,time)` 오버라이드:
  - 패시브 스택 만료 점검(시간 경과 시 환원) — 평타 시점 동기화.
  - 부모 호출(평타 물리/온힛/주문검 발동/증폭/치명타는 **평타에만**).
  - **Q 비치명**은 `_cast_q`에서 별도 계산하므로 부모 평타 로직은 손대지 않음(평타는 정상 치명).
- **마나**: 시뮬은 자원 고갈 미모델(무한마나 DPS 레이스, 기존 sim과 동일). 단 마나무네 스택은
  on_skill_hit/on_hit로 충전되어 경탄(AD)·무라마나가 빌드별로 정확히 반영됨.

## 6. `simulations/ezreal.py` 설계
`corki.py`를 템플릿으로:
- `CORE_TARGET_STATS`, `CORE_LEVELS`(1:lvl9,2:11,3:13,4:15), `EZREAL_SKILL_LEVELS`(Q선마: 예
  core1 q5/e1/w1 … 튜닝 가능), `build_target_for_core`.
- `simulate_ezreal_core_path(full_path, shoe, rune, core_tier, doran)`:
  레지스트리로 아이템 생성, skill_plan(매뉴얼 오프닝 q/w/e + 오토 q/w/e, **R 없음**) 구성,
  `run_simulation` 호출 → (dps, cost).
- `get_ezreal_4core_top1_build()` + `__main__`: 5:4:3:3 가중 상대-DPG 랭킹 표 + matplotlib 그래프
  (기존 sim과 동일 출력 관례; `__main__` 끝 `plt.show()` 블로킹 — 헤드리스 유의).
- **아이템 풀**: Corki AD-캐리 풀 재사용(Trinity, Manamune→Muramana, IE, Collector, 크리, 온힛,
  관통, BotRK…). Q 비치명이므로 크리는 평타에만 이득 → 랭킹이 자연히 반영.
- **컨트롤 빌드**[H]: 후보 `trinity-muramana-ie-ldr`(탐색 경로 내 필수). §8서 확정.

## 7. 검증 절차 (AGENTS.md §5)
- **스모크**: Ezreal 인스턴스화 → `run_simulation` 1회 → DPS 양수·유한, 공속 정상 단언.
- **유닛**:
  - Q 적중 시 `cooldowns_remaining` 전 항목 −1.5초 확인(루프 가속).
  - 패시브 스택 누적/6초 만료/공속 환원 확인.
  - **주문검은 평타에서 발동, Q에서는 미발동** 확인(타이밍).
  - 마나무네가 Q/W/E로 충전됨(무라마나 전환·경탄 AD) 확인.
  - allow-list 온힛이 Q에 적용, 주문검/Manamune/에너자이즈드는 Q서 제외 확인.
- **회귀**: 기존 챔피언(Ashe/Corki/Kai'Sa/Yunara/Jinx 레퍼런스) DPS 불변
  (특히 베이스 클래스 보조 메서드 추가 시 — 행위보존 보장).
- **통합**: `python -m adc_sim.simulations.ezreal` 실행 → 표 육안검사(컨트롤 존재, 코어별 DPG 정합).

## 8. 스펙 리뷰 — 확정 (2026-06-24 사용자)
1. **Q 온힛 충실도**: ✅ **풀 allow-list 채택**(§4.3). Kraken/BotRK/Guinsoo/Wit's/Terminus/
   Nashor's 로컬 적용 + Manamune/Muramana·룬은 엔진 스킬경로.
2. **컨트롤 빌드**: ✅ `trinity-muramana-ie-ldr`(탐색 경로 내 필수).
3. **`as_ratio`**: ✅ 0.625.
4. **Q AP 계수**: ✅ 0.15(CDragon). (Wiki 0.40은 저영향, 가설 H-EZ-4로 추적.)
5. **EZREAL_SKILL_LEVELS**: ✅ Q선마 가정 채택. 구현 시 코어별 표 명시(튜닝 가능).

## 9. 가설 레지스터 (AGENTS.md §4 — 전부 `Hypothesis`)
- H-EZ-1: `ad_growth=3.75`(DDragon raw=0 충돌, Wiki 채택).
- H-EZ-2: 패시브 10%/스택·5스택·6초.
- H-EZ-3: Q **비치명**(사용자 확정이나 게임 메커니즘상 역사적으로 치명 가능 → 가설로 추적).
- H-EZ-4: Q AD계수 1.30×**총**AD, AP 0.15.
- H-EZ-5: Q 적중 시 전 스킬 −1.5초(시뮬상 항상 적중 가정).
- H-EZ-6: Q 온힛 allow-list(Kraken/BotRK/Guinsoo/Wit's/Terminus/Nashor's)·주문검 장전·Manamune
  이중계산 방지·에너자이즈드 제외.
- H-EZ-7: W 단일 더미 즉시 기폭 단순화, 계수 1.0 추가AD/0.9 AP.
- H-EZ-8: E 계수 0.6 추가AD/0.75 AP.
- H-EZ-9: 무한마나 DPS 레이스(자원 고갈 미모델), 단 마나무네 스택은 정확 반영.
- H-EZ-10: R v1 제외.

## 10. 구현 순서(검증 레이어)
1. `Ezreal` 클래스(패시브+Q+W+E, 쿨/스택/루프) + 스모크·유닛 테스트 → 검증.
2. `simulations/ezreal.py`(탐색·랭킹·표·그래프) → 통합 실행 검증.
3. (회귀) 기존 챔피언 DPS 불변 확인.
각 레이어는 다음 진행 전 검증 통과를 전제로 한다(AGENTS.md §5 Add-Before-Replace).
