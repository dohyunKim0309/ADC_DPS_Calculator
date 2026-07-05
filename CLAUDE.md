# CLAUDE.md

> 이 파일은 Claude Code가 매 세션 자동으로 읽는다. 운영 규칙(승인/변경 절차)은 **`AGENTS.md`가 우선**이며, 이 문서는 프로젝트 구조·도메인 지식·패치 갱신 흐름을 다룬다. 둘이 충돌하면 `AGENTS.md`를 따른다.

## 목적
롤(LoL) 전투를 **이벤트 기반(event-driven)** 으로 시뮬레이션해서, **패치마다 어떤 아이템트리(코어 순서)가 수학적으로 가장 뛰어난지**를 DPS·골드효율로 정량 비교·랭킹하는 도구.
- 핵심 산출물: 챔피언별 코어 빌드 랭킹, 챔피언 간 파워 비교, CSV/JSON 리포트, matplotlib 그래프.
- 결론은 "이론상 DPS 모델" 위에서 나온다. 실측이 아니라 **모델/가설의 합**이라는 점을 항상 기억할 것(→ 가설 태깅 규칙).

## 실행
- 환경: **`.venv` 하나로 통일**(Python 3.10). 의존성은 `requirements.txt` 한 줄 = **matplotlib**(numpy 등은 matplotlib가 끌어옴; 그 외는 표준 라이브러리 `csv/json/datetime/pathlib/itertools`).
  - 셋업: `python3.10 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt`
  - ⚠️ 시스템 `python3`(3.9)나 다른 인터프리터로 돌리지 말 것. 항상 **`.venv/bin/python`** 사용.
- 시뮬은 패키지 모듈이라 **repo 루트에서 `-m`으로 실행**한다:
  - `.venv/bin/python -m adc_sim.simulations.ashe` — 애쉬 4코어 랭킹(+1~3코어 5:4:3 별도 랭킹)
  - `… adc_sim.simulations.yunara` / `.kaisa` / `.corki` / `.ezreal` / `.cogmaw`
  - `… adc_sim.simulations.vayne` — 베인 4코어 랭킹(온힛+크리 풀, 컨트롤 botrk-guinsoo-terminus-pd)
  - `… adc_sim.simulations.jinx` — 징크스 4코어 랭킹(미니건+W, Get Excited OFF, Ashe 크리풀·컨트롤 kraken-pd-ie-ldr 재사용)
  - `… adc_sim.simulations.power_compare` — 챔피언 간 Top1/Basic 비교
  - `… adc_sim.simulations.case_ranking ["케이스필터"]` — **애쉬 케이스 기반 빌드 랭킹**(비-방어 전 아이템 전수조사, 14케이스). 표만 출력(그래프/`plt.show()` 없음)이라 **헤드리스 안전**. 인자로 케이스명 부분일치 필터(예: `"alldps/nohc"`). 전체 ~45초.
- 각 시뮬 모듈은 `if __name__ == "__main__"` 진입점을 가진다. (`case_ranking` 제외) 실행 끝에 `plt.show()`가 **블로킹**으로 창을 띄운다(헤드리스/자동화 시 유의). import만으로는 안 뜸 — 실행 코드가 main 가드 안에 있어 import 스모크 테스트는 안전.
- 리포트 저장은 기본 **꺼져 있음**. `adc_sim/settings.py`의 `SIMULATION_SETTINGS['result_export_enabled'] = True`로 켜면 **루트 `reports/`** 에 UTC 타임스탬프로 `.csv`/`.json` 저장(`result_export_format`: `csv`/`json`/`both`). `graph_style`은 `step`/`linear`. (`PROJECT_ROOT`는 `parent.parent`로 repo 루트를 가리키므로 출력은 항상 루트 기준.)

## 아키텍처 (데이터 흐름)
```
adc_sim/                  ← 소스 패키지 (코어 모듈끼리는 서로 import 안 함)
  settings.py ─ 전역 설정(그래프 스타일, export 토글/경로; PROJECT_ROOT=repo 루트) + 케이스랭킹 출력설정 `CASE_RANKING_OUTPUT`(top_n/대상케이스/prune)
  items.py    ─ Item 베이스 + 동작 서브클래스(on_hit 등 효과 훅). 스탯/가격은 data/items_data.py 가 출처
  runes.py    ─ Rune 베이스 + 룬 서브클래스(효과 훅)
  champion.py ─ Target(더미), Champion 베이스(데미지 모델·스탯·이벤트 인터페이스) + 챔피언 서브클래스
  engine.py   ─ run_simulation(): 이벤트 루프 / calculate_mitigation(): 방저·관통 적용
  simulations/
    ashe.py · yunara.py · kaisa.py · corki.py · ezreal.py · cogmaw.py · vayne.py · jinx.py ─ 빌드 탐색·랭킹·리포트·그래프 (챔피언별)
    power_compare.py ─ 각 챔피언 Top1을 모아 교차 비교 (simulations만 `adc_sim.*` import)
    sim_settings.py ─ 케이스랭킹 '모델' 설정 데이터(가중 프로파일/축/제약/풀 제외세트/컨트롤 오프닝). 순수 설정·헬퍼(코어 import 안 함)
    case_ranking.py ─ 케이스 기반 빌드 랭킹 엔진(집합 메모이즈 시뮬 + 14케이스 전수). 현재 Ashe 전용(레벨표/타깃은 ashe.py 재사용)
  data/
    items_data.py ─ 아이템 스탯/가격 데이터(숫자의 단일 출처)   ← 패치마다 가장 자주 바뀜
    items_registry.py ─ 키→인스턴스 통합 create_item_from_key(데이터 주입; 시뮬별 복제 제거)
    cdragon.py ─ Community Dragon에서 패치 데이터 받아오기(소스 연동만; 계수→sim 매핑은 추후)
results/{ashe,yunara}/ ─ 결과 PNG(생성물, git 제외)    reports/ ─ export 리포트(생성물, git 제외)
experiments/ ─ 비패키지 스크래치(옛 테스트)   Archive/ ─ 수동 보관용   docs/ ─ 예약(미생성)
```
**이벤트 루프(`engine.run_simulation`)**: 매 스텝에서 `next_attack` / `skill_dt`(다음 스킬) / `state_dt`(다음 상태 변화) 중 **최소 시간(dt)** 만큼 시간을 진행시키고, 그 시점에 도달한 이벤트만 처리한다. 동시 시각이면 **스킬을 평타보다 먼저** 처리. `eps`(1e-9) 넛지로 같은 시각 고착을 방지. 타깃 HP가 0 이하가 되면 종료, `dps = 누적피해 / 처치시간`.

**데미지 모델(`Champion.get_one_hit_damage`)** 의 적용 순서(특수 케이스 다수):
1. 룬 `on_attack` 발동 → 기대 평타 물리 = `total_ad*(crit_dmg_mod*crit + (1-crit))`. **치명타 확률은 `add_item`에서 100% 캡(초과분 무효)** — 이 모델엔 초과 치확→AD 환산 아이템이 없으므로.
2. 온힛 합산: 아이템 `on_hit` + 룬 `get_on_hit_damage` + 챔피언 `get_champion_onhit`. 적용 횟수 = `get_onhit_proc_count`(**구인수=2회**, max 합성) **+** `get_extra_onhit_applications`(가산). 주문검류 '온힛 1회 추가'는 가산이라 구인수와 겹쳐도 살아남음(**황혼과 새벽=+1** → 강화평타 온힛 2+1=3회). 미보유 빌드는 가산 0이라 기존 동작 불변.
3. 증폭 합산(아이템 `get_damage_modifier` + 룬). **C44는 별도 배수**, **Shadowflame은 타깃 HP≤40%에서만**, **Rabadon은 AP ×1.30**.
4. `engine.calculate_mitigation`에서 방어력/마저 + 관통 적용: `eff = stat*(1-%pen) - flat_pen`(음수 클램프), `실피해 = raw * 100/(100+eff)`. 고정(true) 피해는 경감 없이 합산.

## 핵심 지표·개념
- **DPS** = 누적 피해 / 처치 시간. (엔진 `run_simulation(respawn_to_full_kills=K)`: 처치 시 오버킬 이월+풀피 리필로 K개 체력바를 처치하는 지속딜 측정 — 시작 버스트(W/궁캔슬) 분산, 바 크기 유지로 몰왕검(현재체력%) 과대평가 방지. **기본 K=2(리스폰 1회)가 프로젝트 표준**; `respawn_to_full_kills=1`로 단일 처치 복원.)
- **DPG** = `DPS / (gold/1000)` — 1000골드당 DPS, 즉 골드 효율.
- **rel_dpg_score**(주 랭킹 지표) = 각 코어 구간의 `row_DPG / control_DPG` 비율을 **코어 1~4 가중치 5:4:3:3**으로 가중합 ×100. 즉 **컨트롤 빌드 대비 상대 골드효율**.
- **Control(기준) 빌드** = `kraken-pd-ie-ldr` 로 하드코딩. 탐색 경로 안에 반드시 존재해야 하며 없으면 `RuntimeError`. 후보 풀이나 키 이름을 바꿀 때 이 빌드가 빠지지 않게 할 것.
- **코어 티어 1~4** = 아이템 1/2/3/4개 시점의 파워 스파이크. 티어마다 타깃 스탯(`CORE_TARGET_STATS`)과 챔피언 레벨/스킬 레벨(`CORE_<CHAMP>_LEVELS`)이 고정. (케이스 랭킹은 티어 1~5 사용 — `CORE_ASHE_LEVELS[5]`/`CORE_TARGET_STATS[5]`.)
- 같은 4개 아이템 "집합"은 순서 후보 중 **최고 점수 하나로 dedup**(`combo_best`).
- **`ashe.py` 보조 랭킹**: 메인 1~4(5:4:3:3) 표와 **별도로** 1~3코어 5:4:3 가중 랭킹을 같이 출력(`rel_dpg_score_3c`). 1~3 오프닝(앞 3아이템 집합)별 1행으로 dedup. 근거: 4코어는 실전상 보통 방어템이라 DPS-골드 랭킹에서 1~3코어가 더 현실적.

### 케이스 기반 랭킹 (`case_ranking.py` / `sim_settings.py`)
- **케이스 = 축들의 (조건부) 곱**: 방어 타이밍 {def@4, def@5, alldps} × (방어 타이밍이면) 방어템 {maw, ga, mercurial} × 치유감소 {nohc, hc} × zeal {zealfree, zealreq} = **28케이스**. 각 케이스 별도 랭킹. 축 추가 시 자동 확장(`build_ranking_cases`). 출력은 `settings.CASE_RANKING_OUTPUT['exclude']`(name 부분일치, 현재 alldps·mercurial)로 일부 끔 — 엔진/케이스 정의는 유지.
- **전수조사 풀**: `ITEMS`에서 `NON_DPS_KEYS`(방어/신발/도란/중복키)만 뺀 비-방어 전 아이템(현재 23종). 슬롯 제약 `SLOT_RESTRICTED_ITEMS`(윤탈/마나무네=1~2코어만, statikk=1~3코어만). `hc`는 펜 슬롯을 `mortal`로 강제. `zealreq`는 오프닝(1~3코어)에 zeal 아이템(`ZEAL_ITEMS`={pd,runaan,rfc}; 윤탈·스태틱 제외) 1개+ 강제. 방어템은 케이스 슬롯(4/5)에 고정 삽입.
- **점수 = 1~5코어 가중 상대-DPG**: `WEIGHT_PROFILES`(callable(n)→가중치 또는 명시벡터, 기본 `early_heavy`)로 코어별 rel-DPG 가중합·정규화 ×100. 표에는 **DPG(랭킹 지표)와 DPS(절대 파워) 점수·vsCTRL 둘 다** 표시. 컨트롤 = `CONTROL_OPENING`(kraken-pd-ie) + 같은 케이스 구조(최적 연계). 오프닝마다 최적 연계 1빌드 평가, 같은 DPS 집합은 dedup.
- **스택 아이템**: 구매코어=약/다음코어=풀을 resolved-key 로 인코딩(윤탈 crit 10%→25%, 마나무네 100스택→무라마나). **DPS는 장착 '집합'에만 의존**하므로 (집합, 패키지) 단위 메모이즈 — 각 고유 셋 1회만 시뮬. 채점은 오프닝 prefix(1~3) 재사용으로 중복 제거.
- 모델 설정은 전부 `sim_settings.py` 데이터(하드코딩 가중치 없음), 출력 정책은 `settings.CASE_RANKING_OUTPUT`.

### 마나 자원 모델 (전 챔피언)
- **마나는 하드 바운드 소비 자원**(`champion` 베이스): 전투 시작 `current_mana=total_mana` 충전, 매 스텝 `mana_regen_per_sec=(base_mp5+성장+아이템mp5)/5` 재생, 스킬은 `can_afford`/`spend_mana` 게이트 — **비용>현재마나면 시전 불가**(off-CD라도 충전까지 대기; `get_time_to_next_skill_event`가 `_afford_in`으로 0-dt 스핀 방지). 평타는 무비용. (K개 처치 지속딜 동안 마나 지속·재생, init 1회.)
- 챔프별 `base_mana/mana_growth/base_mp5/mp5_growth/mana_cost{skill}`는 각 서브클래스(`champion.py`, DDragon 16.13.1 교차검증). 캐스트형(KaiSa/Corki/Ezreal/CogMaw/Jinx)=`mana_cost` 게이트, 버프형(Ashe/Yunara)=`activate_q` 게이트.

### Cog'Maw (`champion.py` CogMaw + `simulations/cogmaw.py`) [수치 4소스 교차검증·가설은 spec 참조]
- **W 바이오아케인**(쿨관리 버프 8s/17s/마나40): 활성 중 평타가 **대상 최대체력 `[3,3.75,4.5,5.25,6]%` + 0.00015·AP 마법 온힛**(`get_champion_onhit`→구인수 2배·증폭·Shadowflame 적용). **Q 패시브**=공속 상수, **Q 액티브**=마법넛지+방/마저 %셔레드(Corki E식), **E**=마법넛지, **R**=`(base+0.75추가AD+apMin·AP)×잃은체력배율`(≤40%HP ×2) + 마나램프(40→400)로 자연 스로틀. ad_growth=3.11.
- **전용 sim**: kaisa.py 미러(4코어 전수→`rel_dpg` 5:4:3:3). 컨트롤 `guinsoo-navori-terminus-wit`(실전 메타 빌드 — RelDPG를 '메타 대비'로 측정; 풀에 존재해야 함). 풀=온힛+AP(guinsoo/kraken/nashor/terminus/bot/rfc/pd/ie/yuntal/statikk/storm + 4코어 rabadon/shadowflame; **shadowflame은 1~4코어 전부**, **void 2~4코어**, **황혼과 새벽(`dawn`)·나보리(`navori`)·마법사의최후(`wit`)·**C44(`c44`)** 1~4코어 전부**; c44는 26.13 버프(확대: 500거리부터 최대 10% 증폭, `items.py` 반영) 편입). 후보 풀은 `COGMAW_CORE_CANDIDATES` 상수로 중앙화(top1·`__main__` 공유). 랭킹 표 뒤에 **패키지 A/B(도란검+광전사+핏빛길 vs 도란활+피흡신발+민첩함) RelDPG 비교표**(상위 10+컨트롤)를 룬별로 출력. **룬 2종 평가**: `__main__`이 `_run_cogmaw_ranking`을 **치명적속도(LethalTempo)·집중공격(PressTheAttack)** 두 keystone으로 각각 호출(룬별 표 2개; `simulate_cogmaw_core_path(keystone_cls=...)`, 보조룬 CutDown 고정). **power_compare 연동 완료**: top1=룬무관 최강(`get_cogmaw_powercompare_builds` — LT·PtA top1 중 절대 weighted-DPG 우위), basic=메타빌드(치속). skill-level 튜닝은 미완(todo).
- **황혼과 새벽(`dawn`, 주문검)** [H-DAWN-1, 나무위키/LoL Wiki V26.09/CDragon id2510 교차검증]: 3100G·AP60/AS20%/AH20(체력300은 STAT_KEYS 미포함→DPS 미반영, 가격엔 포함). 스킬 시전 후 다음 평타에 **(기본AD75%+AP10%) 마법 버스트**(`DuskAndDawn.on_hit`, 1회 소비) + **온힛 효과 1회 추가**(`get_extra_onhit_applications`=가산 → 코그모 W 최대체력%·나셔 온힛 시너지). 쿨2s는 시전시각 기준(EssenceReaver와 동일), 회복은 DPS 모델 무시. Q/E/R/W 시전 모두 `cast_spell`→`on_spell_cast`로 arm. 테스트 `tests/test_dusk_dawn.py`.
- **나보리(`navori`) / 마법사의최후(`wit`)** [H-NAVORI-1, LoL Wiki/CDragon 교차검증]: **navori** 2650G·AS40%/치확25%(이속4% 미모델) — 패시브 **평타마다 기본스킬 Q/W/E 남은 쿨 ×0.85**(궁 R 제외, 치명타 무관). `on_hit` 이 아니라 **엔진 평타훅 `champion.on_basic_attack(time)`**(base=no-op, `CogMaw`만 적용)에서 **평타당 1회** — 구인수 proc_count 에 안 곱해지도록. **wit** 2800G·AS50%/MR45(보존,DPS무영향)/인내20%(미모델) — 온힛 **45 마법**(`WitsEnd.on_hit`, 구인수×2·dawn 가산 적용). 테스트 `tests/test_navori_witend.py`.

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

### Jinx (`champion.py` Jinx + `simulations/jinx.py`) [수치 3소스 교차검증 patch16.13·가설 태그]
- **미니건 크리 평타 캐리 + W 넛지**. Q 스위쳐루=미니건(평타 최대 3스택 +130% 공속, 2.5s 감쇠)/로켓 토글 —
  **단일 더미선 로켓 전략적 열세(미니건 스택 상실 + 20마나/발)라 미니건 고정**. base AD 59(**+3.25**, CDragon+Wiki+Meraki),
  AS 0.625(ratio 0.625, +1%/lvl — V26.01 너프). 마나 260(+50)/mp5 6.7(+1.0). 공속캡은 엔진 3.0(의도된 값 — 건드리지 말 것).
- **W(Zap!) 엔진 스킬 넛지**(Ezreal 미러): 마나[40~60]+쿨[8~4] 게이트, **base[10~210] + 140% *추가*AD 순수 물리**
  (크리·평타온힛 미적용 = `get_on_skill_hit_damage` 미오버라이드; manamune류 스킬훅만 base가 처리). `_cast_w`. 테스트 `tests/test_jinx.py`.
- **Get Excited! 패시브 미모델(OFF, 사용자 합의)** — 처치 조건이라 더미 시뮬엔 안 뜸 + 타 챔프 조건부 스틸과 일관.
  → **Jinx 저평가**(리셋/AoE/궁 강점이 모델 밖; Vayne 사거리 캐비엇의 거울상). E·R 미모델.
- **전용 sim**: vayne.py 미러. Ashe 크리풀(`_build_ashe_4core_all_paths`)·컨트롤 `kraken-pd-ie-ldr` 재사용,
  스킬 선마 로컬 계산(Q선마). power_compare 7번째 챔프 연동(best=RelDPG top1, meta=컨트롤). Top1=`윤탈-C44-LDR-무한`(Ashe와 동일 크리코어).

## 패치마다 갱신 (이 프로젝트의 일상)
새 패치가 나오면 보통 아래를 손본 뒤 시뮬을 다시 돌려 랭킹을 갱신한다. **변경 전 `AGENTS.md`의 승인 절차를 따른다.**
1. **아이템 스탯/가격 변경** → `adc_sim/data/items_data.py`의 `ITEMS[key]`(`stats`/`cost`). 숫자의 단일 출처.
2. **신규 아이템** → `adc_sim/data/items_data.py`의 `ITEMS`에 키 추가(name/cost/stats/behavior). 특수 메커니즘이 있을 때만 `adc_sim/items.py`에 동작 클래스를 추가해 `behavior`로 지정. 생성은 **통합 `create_item_from_key`**(`adc_sim/data/items_registry.py`) 하나가 처리 — 시뮬별 복제 없음(윤탈 crit 은 런타임 파라미터 `yuntal_crit`).
   - 새 키를 **탐색 후보 풀**에 넣어야 실제 랭킹에 등장한다. **유나라는 자체 풀 `_build_yunara_4core_all_paths`(yunara.py, AP 아이템 포함)**, 애쉬는 `ashe.py`의 `_build_ashe_4core_all_paths`, kaisa/corki는 대응 풀. **pen 배타(챔피언 무관 필수)**: 방관 `{ldr, mortal, terminus}` 한 빌드 1개 + 마관 `{void, terminus}` 한 빌드 1개(terminus는 양쪽 겸비 → 공허와도 공존 불가).
   - **%마법관통** 스탯은 `magic_pen_percent`(STAT_KEYS 포함, `add_item`에서 곱연산). 예: 공허의 지팡이(`void`, AP95/마관40%).
3. **챔피언 기본 스탯/스킬 계수 변경** → `adc_sim/champion.py`의 해당 서브클래스. 코어별 레벨표(`CORE_*_LEVELS`)·타깃 스탯(`CORE_TARGET_STATS`)도 패치 메타에 맞게 점검.
4. **룬 변경** → `adc_sim/runes.py`.
5. 갱신 후 시뮬 재실행 → 그래프/리포트 확인. 리포트를 남기려면 export 토글을 켠다.
- 📥 패치 수치 출처는 **Community Dragon** — `python -m adc_sim.data.cdragon`로 연결 점검(전 챔피언+유나라 커버), `snapshot()`으로 raw JSON 덤프. **지금은 소스 연동까지만**(수동 대조용, items/champion 자동 반영 안 함). CDragon 클라 데이터의 스킬 계수는 불완전(궁 0 등)하니 정밀 base 스탯은 DDragon으로 교차검증.

## 시뮬레이션 함정·규칙 (수정 시 주의)
- **반환 튜플 모양을 정확히 맞출 것**: 아이템 `on_hit` → `(phys, magic, true_base, true_onhit)` 4-튜플 / 챔피언·룬 온힛 → `(phys, magic)` 2-튜플 / 스킬 `on_skill_hit` → `(phys, magic, true)` 3-튜플 / `get_one_hit_damage` → `(phys_base, magic_base, phys_onhit, magic_onhit, true_base, true_onhit)` 6-튜플.
- **아이템 스탯의 단일 출처는 `adc_sim/data/items_data.py`**. items.py 동작 클래스에 남은 레거시 스탯 리터럴은 런타임에 데이터가 덮어쓴다(2b에서 제거 예정) — 스탯 수정은 반드시 items_data.py 에서.
- **윤탈 치명타 가정**: 구매 코어/다음 코어 여부에 따라 0%/12%/5%/25%로 분기(`simulate_*_core_path` 내부). 가정이지 실측이 아님.
- **유나라 시뮬 코드는 `adc_sim/simulations/yunara.py`에 자체 보관**(타깃 스탯/레벨표/`simulate_yunara_*` 모두). 애쉬 파일에 두지 말 것. 공유 인프라(`_build_ashe_4core_all_paths`/`build_ashe_like_core_report_meta`)만 ashe.py에서 import. 레벨표(`CORE_YUNARA_LEVELS`)는 Ashe 참조 없이 독립.
- **유나라 로테이션**(`adc_sim/champion.py` Yunara): 첫 평타(궁 전이라 Q 비활성) → 직후 궁=초월(Q 활성) + **첫 평타 딜레이 캔슬**(다음 평타 간격 1/AS를 0.33s로 클리핑) → 둘째 평타 이후 평타 지속 + W는 쿨마다. 평타 윈드업은 모델 없음(첫 평타 t=0 즉시). (구 가정 `activate_q(0.0)` 강제활성은 폐기)
- **Q 평캔/재적립 규칙(Ashe·Yunara 공통)**: Q 만료 후 평타로 **전용 스택**을 재적립해야 재사용(Ashe `q_stacks`≥4, Yunara `q_stacks`≥8=4평타; 활성 시 0 리셋). Ashe Q는 전역 `hit_count`가 아닌 전용 스택 사용(과거 즉시 재활성 버그 수정). **모든 스킬 평캔(Q (재)활성·유나라 W 시전 등) 직후** 다음 평타 간격을 **`ANIM_CANCEL_CLIP`(=0.33s, `champion.py` 모듈 상수)** 로 상한 클리핑(평타캔슬 가정).
- **유나라 W**(`adc_sim/champion.py`)는 엔진 스킬 이벤트로 모델링: Q활성(초월)이면 강화 W(파멸의 궤적, 궁 레벨 색인 160/320/480 +1.2추가AD +0.75AP, 쿨5s), 비활성이면 기본 W(심판의 궤적, W 레벨 색인, 적중+6초 DoT, 쿨10s). **`[Hypothesis]` 나무위키 수치(CDragon API 미검증)**. W 레벨/궁 레벨은 `CORE_YUNARA_LEVELS`의 `w_level`/`r_level`(Q선마→W차선마 가정). `Yunara(w_enabled=False)`로 W 이전 동작 복귀(검증/AB용). 평타는 안 끊는 가정(스킬/평타 타이머 독립).
- **방어구 관통**은 `add_item`에서 곱연산으로 합치지만 주석상 "단순화" 영역 — 정밀화하려면 모델 가정부터 합의.
- **가설은 가설로 표시**: 모델 안에 이미 가설 코드가 있다(예: `adc_sim/champion.py`의 유나라 패시브 재귀 증폭, Shadowflame 상호작용). 새 메커니즘은 `AGENTS.md` 4장대로 `Hypothesis/Experimental/Unsupported`로 명시하고 단정하지 말 것.
- **Jinx 전용 시뮬 `simulations/jinx.py` 있음**(미니건+W, §Jinx 참조). `ashe.py` 안의 옛 `simulate_jinx_reference_path`(Ashe 대비 그래프용)도 잔존하나, 랭킹/파워비교 정본은 `jinx.py`.
- 정의돼 있는 챔피언: Ashe / Jinx / Yunara / KaiSa / Corki / Ezreal / Cog'Maw / **Vayne**. 룬: LethalTempo / PressTheAttack / CoupDeGrace / CutDown / Conqueror. **LT·PtA 온힛 보너스는 적응형**(`runes._adaptive_split`: bonus AP>bonus AD 면 마법, 아니면 물리) — AP 빌드(코그모 등)는 마법으로 들어가 마저 경감·마관(공허/그불)·Shadowflame 증폭 경로를 탄다. 물리 ADC는 그대로 물리.

## 거버넌스
- 변경 절차·승인은 **`AGENTS.md`** 가 정본(특히: 최소 변경·무단 리팩터 금지, 가정/구조 변경 시 사전 승인).
- `docs/assumptions.md`, `docs/architecture.md`는 `AGENTS.md`가 참조하지만 **아직 미생성**된 예약 문서다. **만들기 전에 사용자에게 확인**할 것.

### Git·IDE 위생 — `.idea/` 등 로컬 설정은 절대 트랙 금지
- **`.idea/`(PyCharm)·`.venv/`·생성물(`results/`·`reports/`)은 `.gitignore` 대상 — 절대 커밋/트랙하지 말 것**(로컬·재생성 가능). `.idea/`는 재구조화 커밋 `5e4189f`에서 추적 해제됨.
- **⚠️ 근본 함정**: 재구조화 *이전* 옛 커밋(예: `afa4a7b`)은 아직 `.idea/`를 트랙한다 → 그 커밋으로 `git checkout`하면 옛 `.idea/`가 워킹트리에 풀렸다가 이후(추적해제) 커밋으로 넘어갈 때 git이 삭제 → **사용자의 PyCharm 인터프리터/모듈/run-config 소실**(증상: "PyCharm에서 바로 실행 안 됨"). 실제 사고: 머지 중 stale local main 체크아웃→ff.
- **규칙**: ① `.idea/`를 트랙하던 옛 커밋/브랜치로 `git checkout` 금지 — 히스토리는 `git fetch` + `git log/show/diff <ref>`로만 검사. ② 머지 전 로컬 타깃 브랜치를 먼저 origin과 동기화(`git fetch && git branch -f main origin/main`)해 stale 스냅샷 체크아웃 방지(round-trip 체크아웃 최소화). ③ 망가지면 `.idea/` 재생성(`misc.xml` SDK=프로젝트 `.venv`, `.iml` content root=repo root, `modules.xml`; `workspace.xml`은 보존).

## 이 문서 유지
구조·핵심 개념·갱신 흐름이 바뀌면 이 `CLAUDE.md`도 같이 갱신한다(특히 챔피언/시뮬 파일 추가, 랭킹 지표·컨트롤 빌드 변경, 새 아이템 키 규약). 오래된 안내는 함정이 된다.
