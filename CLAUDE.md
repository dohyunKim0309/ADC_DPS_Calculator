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
  - `.venv/bin/python -m adc_sim.simulations.ashe` — 애쉬 4코어 랭킹
  - `… adc_sim.simulations.yunara` / `.kaisa` / `.corki`
  - `… adc_sim.simulations.power_compare` — 챔피언 간 Top1/Basic 비교
- 각 시뮬 모듈은 `if __name__ == "__main__"` 진입점을 가진다. 실행 끝에 `plt.show()`가 **블로킹**으로 창을 띄운다(헤드리스/자동화 시 유의). import만으로는 안 뜸 — 실행 코드가 main 가드 안에 있어 import 스모크 테스트는 안전.
- 리포트 저장은 기본 **꺼져 있음**. `adc_sim/settings.py`의 `SIMULATION_SETTINGS['result_export_enabled'] = True`로 켜면 **루트 `reports/`** 에 UTC 타임스탬프로 `.csv`/`.json` 저장(`result_export_format`: `csv`/`json`/`both`). `graph_style`은 `step`/`linear`. (`PROJECT_ROOT`는 `parent.parent`로 repo 루트를 가리키므로 출력은 항상 루트 기준.)

## 아키텍처 (데이터 흐름)
```
adc_sim/                  ← 소스 패키지 (코어 모듈끼리는 서로 import 안 함)
  settings.py ─ 전역 설정(그래프 스타일, export 토글/경로; PROJECT_ROOT=repo 루트)
  items.py    ─ Item 베이스 + 동작 서브클래스(on_hit 등 효과 훅). 스탯/가격은 data/items_data.py 가 출처
  runes.py    ─ Rune 베이스 + 룬 서브클래스(효과 훅)
  champion.py ─ Target(더미), Champion 베이스(데미지 모델·스탯·이벤트 인터페이스) + 챔피언 서브클래스
  engine.py   ─ run_simulation(): 이벤트 루프 / calculate_mitigation(): 방저·관통 적용
  simulations/
    ashe.py · yunara.py · kaisa.py · corki.py ─ 빌드 탐색·랭킹·리포트·그래프 (챔피언별)
    power_compare.py ─ 각 챔피언 Top1을 모아 교차 비교 (simulations만 `adc_sim.*` import)
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
- **DPS** = 누적 피해 / 처치 시간. (엔진 `run_simulation(respawn_to_full_kills=K)`: 처치 시 오버킬 이월+풀피 리필로 K개 체력바를 처치하는 지속딜 측정 — 시작 버스트(W/궁캔슬) 분산, 바 크기 유지로 몰왕검(현재체력%) 과대평가 방지. **기본 K=2(리스폰 1회)가 프로젝트 표준**; `respawn_to_full_kills=1`로 단일 처치 복원.)
- **DPG** = `DPS / (gold/1000)` — 1000골드당 DPS, 즉 골드 효율.
- **rel_dpg_score**(주 랭킹 지표) = 각 코어 구간의 `row_DPG / control_DPG` 비율을 **코어 1~4 가중치 5:4:3:3**으로 가중합 ×100. 즉 **컨트롤 빌드 대비 상대 골드효율**.
- **Control(기준) 빌드** = `kraken-pd-ie-ldr` 로 하드코딩. 탐색 경로 안에 반드시 존재해야 하며 없으면 `RuntimeError`. 후보 풀이나 키 이름을 바꿀 때 이 빌드가 빠지지 않게 할 것.
- **코어 티어 1~4** = 아이템 1/2/3/4개 시점의 파워 스파이크. 티어마다 타깃 스탯(`CORE_TARGET_STATS`)과 챔피언 레벨/스킬 레벨(`CORE_<CHAMP>_LEVELS`)이 고정.
- 같은 4개 아이템 "집합"은 순서 후보 중 **최고 점수 하나로 dedup**(`combo_best`).

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
- **Jinx는 전용 시뮬 파일이 없다** — `adc_sim/simulations/ashe.py` 안의 레퍼런스 빌드로만 등장.
- 정의돼 있는 챔피언: Ashe / Jinx / Yunara / KaiSa / Corki. 룬: LethalTempo / PressTheAttack / CoupDeGrace / CutDown / Conqueror.

## 거버넌스
- 변경 절차·승인은 **`AGENTS.md`** 가 정본(특히: 최소 변경·무단 리팩터 금지, 가정/구조 변경 시 사전 승인).
- `docs/assumptions.md`, `docs/architecture.md`는 `AGENTS.md`가 참조하지만 **아직 미생성**된 예약 문서다. **만들기 전에 사용자에게 확인**할 것.

## 이 문서 유지
구조·핵심 개념·갱신 흐름이 바뀌면 이 `CLAUDE.md`도 같이 갱신한다(특히 챔피언/시뮬 파일 추가, 랭킹 지표·컨트롤 빌드 변경, 새 아이템 키 규약). 오래된 안내는 함정이 된다.
