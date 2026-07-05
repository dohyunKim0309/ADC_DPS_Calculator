# 관통 배타 전역화 + 점수 모드 설정 + 통일 랭킹 러너(Phase 1) — 설계

날짜: 2026-07-06 · 상태: 사용자 승인(핵심 결정 2건 명시 확정, Phase 1 스코프는 권장안 채택) · 브랜치 feat/ranking-core

## 사용자 확정 결정

1. **void+terminus 배타는 게임 자체 규칙** → 전 시뮬 전역 적용. (근거: CLAUDE.md 전역 pen 규칙 —
   방관 {ldr, mortal, terminus} ≤1 **그리고** 마관 {void, terminus} ≤1; terminus 양쪽 겸비.)
2. **점수 방식(할인율 vs 전체 가중합)을 선택 가능하게** — 구현 형태는 "통일 러너 + 인자",
   **기본 모드 = discounted γ=0.9** (weighted 4:4:3:3에서 전환).

## 현황 (2026-07-06 조사)

- pen 배타: **유나라만 정답**(ARMOR/MAGIC 두 세트 체크). 나머지 11개 사이트(ashe×2, kaisa×2,
  corki×2, cogmaw×2, vayne, ezreal, cogmaw_sequential, sim_settings/case_ranking)는 방관만 체크,
  상수 로컬 중복. void가 풀에 실존하는 곳은 cogmaw(+sequential)·yunara뿐 → 실질 랭킹 변화는
  **코그모에서 void+terminus 조합 제거**.
- 가중치: `settings.CORE_WEIGHTS_RAW=[4,4,3,3]` 하나를 소비처 ~30곳이 import (029684f 중앙화).
- 랭킹 루프: 코그모/베인/징크스 3벌은 사실상 미러(rows→sorted-combo dedup→컨트롤 canonical
  고정→가중 rel-DPG→표). 카이사(윤탈 위치 민감 dedup·5코어 변형)/애쉬(보조랭킹·케이스5)/
  코르키(신발·룬 축)/유나라(멀티타깃)/이즈리얼은 고유 변형 보유.

## 설계

### 1. pen 배타 전역화 — `adc_sim/data/items_data.py`
```python
ARMOR_PEN_EXCLUSIVE = frozenset({"ldr", "mortal", "terminus"})
MAGIC_PEN_EXCLUSIVE = frozenset({"void", "terminus"})

def pen_rule_ok(keys) -> bool:
    """빌드 내 방관 ≤1 AND 마관 ≤1 (게임 규칙, 챔피언 무관)."""
```
- 11개 사이트 전부 로컬 상수/체크 제거 → `pen_rule_ok` 사용. 유나라도 공유 상수로 전환(동작 동일).
- `cogmaw_sequential.legal_next_items`는 증분형이므로 "owned+후보"에 `pen_rule_ok` 적용.
- case_ranking/sim_settings의 `PEN_EXCLUSIVE_KEYS`(hc/mortal 강제 로직이 참조)는 **armor 세트
  alias로 유지하되 items_data에서 import** — 케이스 축 의미(펜 슬롯 mortal 강제) 불변.
- 파급: 코그모 계열 랭킹에서 void+terminus 빌드 소멸(의도). 타 챔프 불변(풀에 void 없음).

### 2. 점수 모드 — `adc_sim/settings.py`
```python
RANKING_SCORING = {
    "mode": "discounted",        # "weighted" | "discounted"  ← 기본 discounted (사용자 확정)
    "fixed_raw": [4.0, 4.0, 3.0, 3.0],   # weighted 모드 가중
    "gamma": 0.9,                          # discounted 모드: 가중 = [γ^1..γ^n]
}
CORE_WEIGHTS_RAW = _derive_core_weights(RANKING_SCORING)   # 파생 — 소비처 ~30곳 무변경
CORE_WEIGHTS_LABEL = ...                                    # 모드 표시 포함(예: "disc γ=0.9")
```
- 수학적 근거: 할인 점수 Σγ^k·P_k 는 가중 벡터 [γ¹..γ⁴]의 가중합과 동치 → 기존 rel-DPG
  파이프라인 그대로 재사용. ashe 1~3코어 보조랭킹의 `[:3]` 슬라이스도 자연 호환.
- 회귀: DPS baseline(`_baseline_dps.json`)은 점수 무관이라 무영향. 랭킹 점수·순위는 전 챔피언
  변경(의도 — 기본 모드 전환).

### 3. 통일 랭킹 러너 Phase 1 — 신규 `adc_sim/simulations/ranking_core.py`
```python
def rank_builds(cfg, weights_raw=None) -> dict
# cfg: simulate_fn(path, tier, **pkg_kw)→(dps,gold) / all_paths / packages(ADC_PACKAGES)
#      / control_path / pinned_paths([(태그, 경로)] — 코그모 CTRL2) / n_cores(=4)
# 반환: ranked rows(각 row: path/pkg/x/y/dpg/weighted_dpg/rel_dpg_score/is_control/pinned_tag)
```
- 파이프라인: 경로×패키지 시뮬(rows) → sorted-combo dedup(best-order) → 컨트롤·pinned canonical
  고정 → weights_raw(기본 settings 파생값) 채점 → 컨트롤 baseline rel 점수 → 정렬.
- **이관 대상(Phase 1): vayne 단독** (사용자 확정 2026-07-06: "1챔프 먼저 — 베인부터. 이후
  확인하고 나머지 이관 시도"). 베인이 가장 깨끗한 미러(단일 키스톤 LT, CTRL2/AB표 없음).
  vayne.py는 rank_builds 호출 + 자기 출력만 유지, 외부 인터페이스
  (`simulate_vayne_core_path`/`get_vayne_powercompare_builds`/`build_vayne_core_report_meta` —
  power_compare가 import) 불변.
- **동작 보존 검증(핵심 안전장치)**: weighted 모드로 고정한 전후 랭킹 표 diff 0
  확인(스냅샷 비교 테스트 또는 수동 diff 기록) → 검증 후 기본 discounted 전환 커밋.
- Phase 1.5(사용자 확인 후 이 브랜치 또는 후속): cogmaw / jinx 이관.
  Phase 2(후속 브랜치): kaisa/ashe/corki/yunara/ezreal — 변형별 어댑터 설계 후 순차.

## 테스트

- `pen_rule_ok` 유닛(방관 2개·마관 2개·terminus+void·terminus+ldr 불법, ldr+void 합법 등) +
  코그모 경로 생성물에 void+terminus 부재 검증 + 기존 유나라 테스트 통과.
- 가중 파생 유닛: weighted→[4,4,3,3], discounted→[0.9,0.81,0.729,0.6561], 라벨.
- 러너: 합성 simulate_fn으로 dedup/컨트롤 고정/rel 점수 수계산 일치; cogmaw/vayne/jinx 이관
  전후 동일성(weighted 고정) 검증 테스트 또는 기록.
- 전체 스위트 통과(94+신규). 기존 랭킹 형태 테스트(test_cogmaw_ranking 등) 유지.

## 스코프 밖

- Phase 2 챔피언 이관, case_ranking 엔진의 러너 통합(별도 모델), CSV export 통일,
  cogmaw_sequential의 DP와 러너 통합(각자 역할 유지).

## 리스크

- 기본 discounted 전환으로 기존에 보고된 수치들과 비교 단절 — 필요 시 mode를 weighted로 되돌려
  재현 가능(설정 1줄).
- 러너 이관 중 미세 동작 차이(정렬 tie-break, 출력 포맷) — 전후 diff 검증으로 방어.
