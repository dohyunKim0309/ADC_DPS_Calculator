"""코그모 후보 풀 상수 + 패키지 A/B 비교 헬퍼 테스트."""


def test_cogmaw_pool_contains_c44_all_tiers():
    from adc_sim.simulations.cogmaw import COGMAW_CORE_CANDIDATES
    for tier in (1, 2, 3, 4):
        assert "c44" in COGMAW_CORE_CANDIDATES[tier], f"c44 missing in tier {tier}"
