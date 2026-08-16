"""레벨 성장 곡선 — 전 프로젝트 단일 출처(2026-08-11 중앙화).

실 LoL 공식(라이엇):

    스탯(n) = base + bonus + g × (n − 1) × (0.7025 + 0.0175 × (n − 1))

  · g = 성장 스탯, n = 현재 레벨.
  · 체력 / 방어력 / 마법저항 / 공격력 / 체력재생 / 마나 / 마나재생 **7종**이 이 곡선을 쓰고,
    **공격속도 성장**도 같은 곡선을 쓴다(다만 결과가 '추가 공속 %'라
    최종적으로 `base_as + as_ratio × bonus_as%` 로 합쳐진다).
  · n = 18 에서 계수가 정확히 1.0 → `g × 17`. 즉 만렙에서만 선형 근사와 일치한다.
  · 중간 레벨은 선형보다 낮다. 레벨 9 → 선형 대비 84.25%, 레벨 11 → 87.75%, 레벨 15 → 94.25%.

출처: LoL Wiki "Champion statistic", "Attack speed" (2026-08-11 확인).

이 프로젝트의 **모든 레벨 성장 계산은 반드시 이 모듈을 거친다.**
수식이 바뀌면 여기 한 곳만 고치면 된다 — 호출부를 개별 수정하지 말 것.

의존성 없음(순수 함수 모듈). `item_base.py` 와 같은 위치의 리프 모듈이라
코어 모듈(`champion` / `core_items` / `engine`)에서 자유롭게 import 해도
순환 참조가 생기지 않는다.

이 모듈이 담당하지 **않는** 선형 보간:
  · `core_items._level_scaled` — 아이템 방어막 등 8~18레벨 선형(라이엇 아이템 관례)
  · `runes.py` 의 1~18레벨 선형 보간 — 룬 스케일링(성장 스탯이 아님)
  · `KaiSa._lerp_by_level` — 스킬 계수 1↔18 보간(성장 스탯이 아님)
"""

# 라이엇 성장 계수. 두 값의 유일한 정의 위치.
GROWTH_BASE_COEFF = 0.7025
GROWTH_STEP_COEFF = 0.0175


def level_growth_factor(level):
    """레벨 `level` 에서 '성장치 몇 개분'을 얻는지 반환한다.

    level=1 → 0.0, level=18 → 17.0 (정확히). 1 미만은 0으로 클램프.
    """
    n = level - 1
    if n <= 0:
        return 0.0
    return n * (GROWTH_BASE_COEFF + GROWTH_STEP_COEFF * n)


def growth_at_level(growth, level):
    """성장 스탯 `growth` 가 레벨 `level` 에서 만들어내는 **증가분**을 반환한다."""
    return growth * level_growth_factor(level)


def stat_at_level(base, growth, level):
    """기본값 + 레벨 성장분. 가장 흔한 형태의 축약."""
    return base + growth_at_level(growth, level)
