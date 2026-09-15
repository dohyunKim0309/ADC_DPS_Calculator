# Azir 챔피언 추가 — 설계 스펙 (2026-08-27)

> 사용자 결정(2026-08-27 AskUserQuestion) 기록 + 3소스 교차검증 수치 + 가설 레지스터.
> 거버넌스: `AGENTS.md` 정본. 신규 메커니즘은 §9 에 `[H-AZIR-n]` 로 태깅.

## 0. 거버넌스 메모
- **구조 변경**(AGENTS.md §2): 신규 `adc_sim/simulations/azir.py`, `tests/test_azir.py`, 본 스펙.
  `docs/architecture.md` 변경로그에 추가. 사용자 지시 "아지르를 추가하자 … 구현하자"(2026-08-27)로 승인.
- **최소 변경**: `engine.py` 무수정. `champion.py` = `Azir` 클래스 **순수 추가**(베이스 무수정).
  `runes.py` 무수정. `items_data.py` = 신규 키 추가 + `STAT_KEYS` 에 `mana_regen` 1개 추가
  (모든 기존 아이템 기본 0 → 기존 수치 불변). `core_items.py`/`utility_items.py` = 신규 클래스 추가만.
  `power_compare.py` = Azir 분기 추가.
- **소유권**: 위 파일 + `CLAUDE.md`, `docs/architecture.md`.

## 1. 확정 결정 (사용자 2026-08-27)
1. **병사 모델 = 이벤트 기반 충전/지속 추적**. W 2충전, 재충전 12/10.5/9/7.5/6s(스킬가속 적용 [H-AZIR-1]),
   병사 수명 10s 를 엔진 상태이벤트로 추적. 시작 시 2병사(t=0, t=1.5 — W 쿨 1.5s), 이후 충전되는 대로 재소환.
   병사 n 마리 → 소환수 공격 피해 ×(1 + 0.25·(n−1)) [bin `SubsequentDamageMod`=25].
2. **스킬 범위 = W + Q + E + R** 전부 자동. Q 쿨마다, E 쿨마다(챔피언 충돌 → 충전 +1), R t=0 1회.
3. **아이템 = 대거 추가**(§4). 3티어 신발(미드 퀘스트) + 미드 퀘스트 보상(AP 8%, 추가AD 8%) 포함.
4. **룬 = PtA·LT 2종**(보조 CutDown 고정, 코그모/베인 미러). **컨트롤 = `nashor-shadowflame-rabadon-void`**.
   시작 = 도란의 반지 + 마법사의 신발(ADC A/B 패키지 미사용).

## 2. 수치 테이블 (✓ = 나무위키 2026-08-27 + LoL Wiki V26.16 + CDragon bin latest 3소스 일치)
### 2.1 기본 스탯
| 항목 | 값 | 근거 |
|---|---|---|
| base_ad / ad_growth | 56 / **3.5** | bin `damagePerLevelModifiable=3.5`+Wiki+나무 ✓ (DDragon raw=0 은 데이터버그, Vayne 과 동일) |
| base_as / as_ratio / as_growth | 0.625 / **0.694** / 5.0 %/lvl | bin `attackSpeedRatioModifiable=0.694`+Wiki ✓ (나무위키는 ratio 미표기) |
| base_range | 525 | ✓ |
| base_mana / mana_growth | 320 / 40 | ✓ |
| base_mp5 / mp5_growth | 8 / 0.8 | bin 1.6/s×5, 0.16/s×5 = DDragon ✓ |
| HP / Armor / MR (EHP 전용) | 575(+108) / 25(+5) / 30(+1.3) | ✓ |
| 적응형 | AP (`mAdaptiveForceToAbilityPowerWeight=1`) | bin |

### 2.2 W — 일어나라! (Arise!) — 핵심
| 항목 | 랭크 1/2/3/4/5 | 근거 |
|---|---|---|
| 기본 마법 | 50/65/80/95/110 | bin `BaseDamage`[1..5] ✓ |
| 레벨 보너스 | **0 (lv≤9), +8/lv (lv≥10) → lv18=72** | bin `TotalDamage` breakpoint(lv10, +8) = Wiki "0−72 based on level" ✓ |
| AP 계수 | 0.35/0.425/0.5/0.575/0.65 | bin `APRatio` ✓ |
| 온힛 효과 | **50%** (첫 대상, 공격당 1회) | bin `OnHitMultiplier=0.5` ✓ |
| 추가 병사 | 2번째부터 **25%** (온힛·온어택 미적용) | bin `SubsequentDamageMod=25` ✓ |
| 병사 수명 | 10s | bin `SoldierDuration` ✓ |
| 충전 | 최대 2, 재충전 12/10.5/9/7.5/6s | bin `mAmmoRechargeTime`/`mMaxAmmo` ✓ |
| 쿨 / 마나 / 시전 | 1.5s / 40·35·30·25·20 / 0.25s | ✓ |
| 판정 | 기본 공격(공속 적용) **+ 스킬 효과(광역)**: 리안드리·리치베인·루덴·라일라이 적용 | Wiki "applies ability effects as area damage", 나무 ✓ |
| 치명타 | 불가(마법 스킬 피해) | Wiki |

### 2.3 Q / E / R
| 스킬 | 피해 | 쿨 | 마나 | 시전 |
|---|---|---|---|---|
| Q 사막의 맹습 | 75/95/115/135/155 + 0.35/0.4/0.45/0.5/0.55 AP 마법 | 14/12/10/8/6 | 70/80/90/100/110 | 0.25s |
| E 신기루 | 70/110/150/190/230 + 0.6 AP 마법 (+동량 보호막 1.5s) | 22/20.5/19/17.5/16 | 60 | 돌진(1700/s) |
| R 황제의 진영 | 200/400/600 + 0.75 AP 마법 | 120/105/90 | 100 | 0.5s |
(bin+Wiki+나무 3소스 ✓)

## 3. 전투 모델
- **평타 = 병사 공격**: `get_one_hit_damage` 오버라이드. `phys_base=0`, `magic_base = W(lv,rank,AP) × (1+0.25(n−1))`.
  온힛(아이템 `on_hit`: 내셔·리치베인·구인수 proc·황혼 가산) ×0.5, **PtA 3타 폭발 ×1.0** — LT 풀스택 온힛 ×0.5 포함 **전부 사용자 확정 2026-08-27**.
  증폭(PtA/CutDown/리안드리 고난/균열/지평선)=`mod_factor` 곱연산 그대로. 그림자불꽃 ≤40%: 소환수 피해 +20%(베이스 SF 층).
- **스킬 효과 훅**: 병사 타격·Q·E·R·벨트 액티브에 `_apply_spell_effects(target, time)` 1회 → 루덴 메아리(12s 쿨),
  리안드리 고통 DoT 갱신, 어둠불꽃 DoT 갱신, 핏빛 저주 마저 감소 스택, 지평선 초강력(스킬만, 병사 제외).
- **DoT**: 0.5s 틱을 스킬 이벤트(`is_skill_hit=True`)로 방출 → 엔진이 마저 경감·누적. 틱 중엔 `get_on_skill_hit_damage`=0
  (틱이 루덴 등을 재발동하지 않도록). 리안드리 1%최대체력/0.5s×6, 어둠불꽃 10+1%AP/0.5s×6, 악의 15+1.25%AP/0.25s→0.5s 환산(R 적중 후 3s, MR−10).
- **시전 시간**: Q 0.25s, W 0.25s, R 0.5s, E 돌진 0.3s [H-AZIR-3] — 전부 **흡수형** `cast_lockout_until`(평타 타이머는 흐름).
- **로테이션**: t=0 W → E(충돌 가정, 충전+1 → 3병사) → R → Q 쿨마다; W 는 충전 있으면 즉시(병사 최대 유지). 마나 하드 바운드.
- **레벨/스킬**: 코어 1~5 = lv 9/11/13/15/17, W>Q>E 선마: (Q,W,E,R) = (3,5,1,1),(5,5,1,2),(5,5,3,2),(5,5,5,2),(5,5,5,3).
- **미드 퀘스트 [H-AZIR-4]**: 코어 1 = 2티어 신발(마관신 12)·퀘스트 미완, **코어 ≥2 = 3티어 주문투척자(마관 20+8%) 무료 승급 + 총AP ×1.08 + 추가AD ×1.08**(Wiki V26.11). Rabadon 과 곱연산.
- **타깃**: `CORE_TARGET_STATS` 공용(마저 25/30/50/70/90). K=2.

## 4. 신규 아이템 (수치: CDragon items.json latest = 나무위키 2026-07-30 교차, 차이는 CDragon 채택)
| 키 | 이름 | 가격 | 스탯 | 동작 |
|---|---|---|---|---|
| doranring | 도란의 반지 | 400 | AP18/HP90/mp5 10(전투 중 2/s) | 스탯 |
| sorcerer | 마법사의 신발 | 1100 | 마관12 | 스탯 |
| spellslinger | 주문투척자의 신발(3티어) | 1100(승급 무료) | 마관 20 + 8% | 스탯 |
| ionian / crimson | 명석함 / 핏빛 명석함 | 900 | AH10 / AH20 | 스탯 |
| gunmetal | 건메탈 군화(3티어) | 1100 | AS45%/LS5% | 스탯 |
| swift / swiftmarch | 신속 / 신속행진 | 1000 | MS55 / MS65 + MS×5% 적응형(AP) | 스탯(+AP 환산) |
| liandry | 리안드리의 고통 | 3000 | AP60/HP300 | 고통 DoT 2%최대체력/s 3s + 고난 2%/s ≤6% 증폭 |
| lichbane | 리치베인 | 2900 | AP100/AH10 | 주문검 75%기본AD+45%AP 마법 온힛(쿨1.5s) + 준비 중 AS+50% |
| cryptbloom | 무덤꽃 | 3000 | AP75/마관30%/AH20 | 스탯(마관 배타 void 와 공존불가) |
| bloodletter | 핏빛 저주 | 2500 | AP60/HP350/AH15 | 마법피해 시 마저 −7.5%/스택 ≤4 (6s, 지속전투 만료 없음 [H-AZIR-5]) |
| stormsurge | 폭풍 쇄도 | 2800 | AP90/마관15 | 2.5s 내 25%최대체력 → 2s 후 125+10%AP, 쿨30s |
| ludens | 루덴의 메아리 | 2750 | AP100/마나600/AH10 | 스킬 피해 시 (75+5%AP)×2 (메아리 6 = 본체+5×20%), 쿨12s |
| blackfire | 어둠불꽃 횃불 | 2800 | AP80/마나600/AH20 | DoT 10+1%AP/0.5s 3s + 불타는 중 AP +4% |
| malignance | 악의 | 2700 | AP90/마나600/AH15 | R 적중 시 3s 지면 180+15%AP + MR−10 |
| archangel / seraph | 대천사 / 세라핀 | 2900 | AP70/마나600·1000/AH25 + 추가마나 1%·2% AP | 마나무네식 구매코어/다음코어 |
| rylai | 라일라이 | 2600 | AP65/HP400 | 스탯(둔화 미모델) |
| belt | 로켓 벨트 | 2650 | AP60/HP350/AH20 | 액티브 100+10%AP t=0 1회(쿨40s) |
| banshee | 밴시의 장막 | 3000 | AP105/MR40 | 스탯, defense 태그 |
| horizon | 지평선의 초점 | 2700 | AP75/AH25 | Q/E/R 시 6s 동안 모든 피해 +10% [H-AZIR-6: Q 시전거리 ≥600 가정] |
| cosmic | 우주의 추진력 | 3000 | AP70/HP350/AH25 | 스탯 |
| riftmaker | 균열 생성기 | 3100 | AP70/HP350/AH15 | 2%/s ≤8% 증폭 + 추가HP 2% AP + 최대 시 옴니뱀프 6%(조건부 지표) |
기존: nashor/rabadon/shadowflame/void/zhonya/dawn/guinsoo/wit.

## 5. 탐색
- `simulations/azir.py`: cogmaw.py 미러 — `simulate_azir_core_path`, receding-horizon 기본(γ=0.8, 5코어),
  `legacy-ranking` 4코어 전수(컨트롤 필수·RuntimeError), 룬 2종(PtA·LT) × 신발 고정. power_compare 9번째 챔프.
- 후보 슬롯: 딜 아이템 전 슬롯, 유틸/방어(zhonya/banshee/rylai/belt/cosmic)는 3~5코어. 마관 배타 `MAGIC_PEN_EXCLUSIVE` 에 cryptbloom 추가.

## 9. 가설 레지스터
- [H-AZIR-1] W 재충전 시간에 스킬가속 적용(LoL 충전형 스킬 일반 규칙).
- [H-AZIR-2] ~~PtA 100% / 내셔·리치베인 50% / LT 50%~~ → **전부 확정(사용자 2026-08-27)**. 남은 가정: 구인수 팬텀히트도 50%.
- [H-AZIR-3] E 돌진 0.3s 평타 불가(흡수형). E 는 항상 챔피언 충돌(충전 +1).
- [H-AZIR-4] 미드 퀘스트 완료 시점 = 코어 2 이후. 보상 AP 8% 는 총AP 곱(라바돈과 곱연산).
- [H-AZIR-5] 핏빛 저주 스택 지속전투 중 만료 없음(공격 간격 < 6s).
- [H-AZIR-6] 지평선의 초점: 아지르 Q/E/R 은 항상 600+ 거리에서 시전. 병사 피해는 발동 안 함(Wiki: 소환수 제외), 증폭은 전 피해.
- [H-AZIR-7] 시작 2병사: t=0, t=1.5 W. 실전 사전 배치 병사는 무시.
- [H-AZIR-8] DoT 틱은 그림자불꽃 ≤40% +20% 적용(도트 판정). Q/E/R 도 SF 적용(스킬 치명타) — 기존 코그모는 스킬에 SF 미적용이라 챔프 간 차이 있음(문서화).
