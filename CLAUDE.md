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
  - `… adc_sim.simulations.yunara` / `.kaisa` / `.corki`
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
    ashe.py · yunara.py · kaisa.py · corki.py ─ 빌드 탐색·랭킹·리포트·그래프 (챔피언별)
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
1. 룬 `on_attack` 발동 → 기대 평타 물리 = `total_ad*(crit_dmg_mod*crit + (1-crit))`
2. 온힛 합산: 아이템 `on_hit` + 룬 `get_on_hit_damage` + 챔피언 `get_champion_onhit`. `get_onhit_proc_count`로 횟수 확장(**구인수=2회**).
3. 증폭 합산(아이템 `get_damage_modifier` + 룬). **C44는 별도 배수**, **Shadowflame은 타깃 HP≤40%에서만**, **Rabadon은 AP ×1.30**.
4. `engine.calculate_mitigation`에서 방어력/마저 + 관통 적용: `eff = stat*(1-%pen) - flat_pen`(음수 클램프), `실피해 = raw * 100/(100+eff)`. 고정(true) 피해는 경감 없이 합산.

## 핵심 지표·개념
- **DPS** = 누적 피해 / 처치 시간.
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

## 패치마다 갱신 (이 프로젝트의 일상)
새 패치가 나오면 보통 아래를 손본 뒤 시뮬을 다시 돌려 랭킹을 갱신한다. **변경 전 `AGENTS.md`의 승인 절차를 따른다.**
1. **아이템 스탯/가격 변경** → `adc_sim/data/items_data.py`의 `ITEMS[key]`(`stats`/`cost`). 숫자의 단일 출처.
2. **신규 아이템** → `adc_sim/data/items_data.py`의 `ITEMS`에 키 추가(name/cost/stats/behavior). 특수 메커니즘이 있을 때만 `adc_sim/items.py`에 동작 클래스를 추가해 `behavior`로 지정. 생성은 **통합 `create_item_from_key`**(`adc_sim/data/items_registry.py`) 하나가 처리 — 시뮬별 복제 없음(윤탈 crit 은 런타임 파라미터 `yuntal_crit`).
   - 새 키를 **탐색 후보 풀**(`ashe.py`의 `_build_ashe_4core_all_paths` 내 `coreN_candidates`, kaisa/corki의 대응 풀)에 넣어야 해당 시뮬 랭킹에 등장한다. `pen_exclusive_keys = {terminus, ldr, mortal}`는 한 빌드에 1개까지만 허용.
   - **케이스 랭킹(`case_ranking`)은 풀 자동수집**: 비-방어 DPS템은 `ITEMS`에 추가만 하면 자동 포함. 단 **방어템이면** `sim_settings.NON_DPS_KEYS`에 넣고 방어 축(`DEFENSIVE_ITEMS`)에 추가해야 한다. 슬롯/스택 특수 아이템은 `SLOT_RESTRICTED_ITEMS`/`STACK_ITEMS`도 점검.
   - **`STAT_KEYS`(items_data)**: 엔진이 읽는 DPS 스탯 키 목록. `mr`/`armor`는 현재 DPS 무영향이지만 인스턴스에 **보존**(미래 1대1 모델용)되도록 포함됨 — 여기 없는 키는 `_apply_data`가 인스턴스로 복사하지 않고 버린다. 방어막·옴니뱀 같은 조건부 패시브는 스탯이 아니라 동작 클래스 속성으로(예: `MawOfMalmortius.lifeline_*`).
3. **챔피언 기본 스탯/스킬 계수 변경** → `adc_sim/champion.py`의 해당 서브클래스. 코어별 레벨표(`CORE_*_LEVELS`)·타깃 스탯(`CORE_TARGET_STATS`)도 패치 메타에 맞게 점검.
4. **룬 변경** → `adc_sim/runes.py`.
5. 갱신 후 시뮬 재실행 → 그래프/리포트 확인. 리포트를 남기려면 export 토글을 켠다.
- 📥 패치 수치 출처는 **Community Dragon** — `python -m adc_sim.data.cdragon`로 연결 점검(전 챔피언+유나라 커버), `snapshot()`으로 raw JSON 덤프. **지금은 소스 연동까지만**(수동 대조용, items/champion 자동 반영 안 함). CDragon 클라 데이터의 스킬 계수는 불완전(궁 0 등)하니 정밀 base 스탯은 DDragon으로 교차검증.

## 시뮬레이션 함정·규칙 (수정 시 주의)
- **반환 튜플 모양을 정확히 맞출 것**: 아이템 `on_hit` → `(phys, magic, true_base, true_onhit)` 4-튜플 / 챔피언·룬 온힛 → `(phys, magic)` 2-튜플 / 스킬 `on_skill_hit` → `(phys, magic, true)` 3-튜플 / `get_one_hit_damage` → `(phys_base, magic_base, phys_onhit, magic_onhit, true_base, true_onhit)` 6-튜플.
- **아이템 스탯의 단일 출처는 `adc_sim/data/items_data.py`**. items.py 동작 클래스에 남은 레거시 스탯 리터럴은 런타임에 데이터가 덮어쓴다(2b에서 제거 예정) — 스탯 수정은 반드시 items_data.py 에서.
- **윤탈 치명타 가정**: `simulate_*_core_path`(ashe/yunara)는 구매/다음 코어에 따라 0%/12%/5%/25%로 분기. **케이스 랭킹은 다른 가정**(구매코어 10% → 다음코어부터 25%, 마나무네는 구매 100스택 → 다음 무라마나). 둘 다 가정이지 실측 아님.
- **케이스 랭킹은 현재 Ashe 전용**: 레벨표/타깃/패키지를 `ashe.py`에서 import. 컨트롤 = `sim_settings.CONTROL_OPENING`(kraken-pd-ie). 챔피언 일반화·컨트롤 다변화는 미완(todo). 점수는 DPG 기반이므로 절대 DPS와 순위가 다를 수 있음(표에 DPS·DPG·골드 함께 표기).
- **유나라 시뮬**은 전투 시작과 동시에 `activate_q(0.0)`로 Q 활성 상태 가정.
- **방어구 관통**은 `add_item`에서 곱연산으로 합치지만 주석상 "단순화" 영역 — 정밀화하려면 모델 가정부터 합의.
- **가설은 가설로 표시**: 모델 안에 이미 가설 코드가 있다(예: `adc_sim/champion.py`의 유나라 패시브 재귀 증폭, Shadowflame 상호작용). 새 메커니즘은 `AGENTS.md` 4장대로 `Hypothesis/Experimental/Unsupported`로 명시하고 단정하지 말 것.
- **Jinx는 전용 시뮬 파일이 없다** — `adc_sim/simulations/ashe.py` 안의 레퍼런스 빌드로만 등장.
- 정의돼 있는 챔피언: Ashe / Jinx / Yunara / KaiSa / Corki. 룬: LethalTempo / PressTheAttack / CoupDeGrace / CutDown / Conqueror.

## 거버넌스
- 변경 절차·승인은 **`AGENTS.md`** 가 정본(특히: 최소 변경·무단 리팩터 금지, 가정/구조 변경 시 사전 승인).
- `docs/assumptions.md`, `docs/architecture.md`는 `AGENTS.md`가 참조하지만 **아직 미생성**된 예약 문서다. **만들기 전에 사용자에게 확인**할 것.

## 이 문서 유지
구조·핵심 개념·갱신 흐름이 바뀌면 이 `CLAUDE.md`도 같이 갱신한다(특히 챔피언/시뮬 파일 추가, 랭킹 지표·컨트롤 빌드 변경, 새 아이템 키 규약). 오래된 안내는 함정이 된다.
