# Cog'Maw C44 풀 추가 + C44 버프 반영 + 패키지 A/B 비교표 — 설계

날짜: 2026-07-05 · 상태: 사용자 승인됨 (대화 중 구두 승인)

## 배경 / 요구사항

사용자 요청 (2026-07-05):
1. 코그모 시뮬에 "도란활+피흡신발+민첩함 vs 도란검+광전사+핏빛길" 비교 추가.
2. C44(Hextech Scope C44)를 코그모 1~4코어 후보 풀에 추가.

조사 결과 확정된 사실:
- `ADC_PACKAGES`(items_data.py)에 A=Bld+Zerk+핏빛길, B=Bow+Glut+민첩함이 이미 정의돼 있고,
  cogmaw.py는 이미 전 빌드를 두 패키지로 평가한 뒤 **빌드별 우수 패키지만 남기고 dedup**한다.
  → (1)의 실체는 "추가"가 아니라 **A/B 비교의 가시화**. 사용자 선택: **별도 비교표 추가**
  (랭킹 표 불변, 패키지별 행 분리 방식은 기각).
- C44는 **버프됨**: 확대 패시브가 "**500 거리일 때 최대**(10%) 피해"로 변경
  [출처: 사용자 인게임 툴팁 직접 확인, 26.13]. 현행 코드는 `min(1, range/600)×10%` — 구식.
  버프 반영 시 코그모(사거리 500)도 풀 10% 증폭 → W 사거리 증가 모델링 불필요
  (사용자 질문 무응답 → 추천안 "현재 모델 그대로"였으나 버프 반영으로 논점 소멸).

## 변경 사항

### 1. C44 버프 반영 — `adc_sim/items.py` `HextechScopeC44.get_damage_modifier`
- `ratio = min(1.0, current_range / 600.0)` → `min(1.0, current_range / 500.0)`.
- 주석 갱신: "버프: 500거리부터 최대 10% [26.13, 사용자 툴팁 확인]".
- `is_buff_active`(+100 사거리 토글, 기본 False) 및 스탯(AD55/크리25%/2800G)은 불변.
- 파급: 사거리 500 이상 전 모델 ADC가 10% 증폭으로 수렴
  (Jinx 8.75%→10%, Corki/Vayne 9.17%→10%, KaiSa 8.75%→10%, Yunara 9.58%→10%; Ashe는 기존에도 10%).
  기존 c44 포함 빌드(Ashe/Jinx top1 등)의 점수 상승은 **의도된 패치 반영**.
- 회귀 스냅샷(`tests/_baseline_dps.json`) 5챔프 대표 빌드에는 c44 미포함 → 무영향 예상, 실행으로 확인.

### 2. C44를 코그모 후보 풀 1~4코어 추가 — `adc_sim/simulations/cogmaw.py`
- 현재 core1~4 후보 리스트가 `get_cogmaw_4core_top1_build`(84~87행)와 `__main__` 경로 빌더
  (362~365행)에 **중복 하드코딩** — 이번 같은 풀 변경 시 한쪽 누락 위험.
  → 모듈 상수 `COGMAW_CORE_CANDIDATES`(dict: tier→list)로 추출, 두 곳 모두 이 상수 사용
  (동작 불변 리팩터 + 이번 변경의 직접 리스크 제거).
- `c44`를 1~4코어 리스트 전부에 추가. c44는 관통 아이템이 아니므로 pen 배타 규칙 무관.
- 경로 수 약 +29% (15·16·15·15 → 16·17·16·16 조합) → 코그모 시뮬 런타임 증가 수용.
- power_compare는 `get_cogmaw_4core_top1_build`를 통해 자동으로 새 풀 반영.

### 3. 패키지 A/B 비교표 — `_run_cogmaw_ranking` 출력 끝에 섹션 추가
- 랭킹 계산·표는 불변. **rel_dpg_score 랭킹 상위 10개 빌드를 랭킹 순서 그대로** 대상으로 하고,
  컨트롤 빌드가 상위 10에 없으면 참고용으로 마지막에 1행 추가(메인 표의 extra_controls 관례 미러).
  각 대상 빌드에 대해 pre-dedup `rows`에서 같은 빌드 집합의 A행/B행을 찾아 **동일 컨트롤
  baseline**으로 각각 rel_dpg_score를 계산해 나란히 출력:
  `빌드(4아이템) | A RelDPG | B RelDPG | Δ(B−A) | 우세(A/B)`.
- 재시뮬 없음(기존 rows 재사용). 행 구성은 순수 헬퍼
  `_build_pkg_compare_rows(rows, top_paths, baseline_dpg_4, core_weights)` → list[dict]로 분리
  (print와 분리해 유닛 테스트 가능).
- LT·PtA 두 룬 실행마다 각각 출력(함수 내부라 자동).
- 주의: dedup에서 진 패키지 행도 비교에 필요하므로 rows(전 행)는 dedup 후에도 참조 유지.

## 테스트

- `tests/test_c44_range.py`(신규): C44 modifier — range 500→0.10, 250→0.05, 600→0.10(클램프),
  `is_buff_active` 동작 보존.
- `tests/test_cogmaw_pkg_compare.py`(신규): `_build_pkg_compare_rows` — 합성 rows로 A/B 짝 매칭,
  점수·Δ·우세 판정 검증; `COGMAW_CORE_CANDIDATES` 1~4 전부에 `c44` 포함 확인.
- 기존 `test_cogmaw_ranking.py`(형태 검증)·전체 스위트 통과 확인.
- 수동 검증: `MPLBACKEND=Agg`로 cogmaw 시뮬 실행 → 비교표 출력·c44 빌드 등장 확인.

## 스코프 밖 (명시적 제외)

- 코그모 W 사거리 증가(+130~250)의 엔진 모델링 — C44 버프로 불필요해짐; 다른 사거리 의존
  효과가 생기면 재론.
- CSV/JSON export 스키마에 A/B 비교 반영 — 표 출력만.
- 타 챔피언 시뮬에 동일 비교표 확산 — 코그모 한정(요청 범위).

## 리스크 / 노트

- C44 버프 수치의 출처는 사용자 툴팁 확인 단일 소스 — 구현 시 CDragon으로 교차 확인 시도
  (실패해도 사용자 확인을 우선, 주석에 출처 명기). [데이터 교차검증 워크플로 준수]
- 런타임 +29%는 "느리다" 주석이 이미 있는 시뮬에 추가 부담 — 수용하되 체감 과도 시 후속 논의.
