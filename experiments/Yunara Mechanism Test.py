def check_yunara_damage(ad, ap):
    # 공통: 물리 대미지 (무한의 대검 치명타)
    phys = 2.15 * ad

    # 공통: 마법 대미지 베이스 (Q 5렙, 체력 40% 이하)
    # 수식: (0.1 + 0.001*AP) * 2.15*AD + 50 + 0.4*AP
    base_magic = (0.1 + 0.001 * ap) * 2.15 * ad + 50 + 0.4 * ap

    # 가설 1: 그림자불꽃 28% 증폭만 적용
    h1_total = base_magic * 1.28

    # 가설 2: 그림자불꽃 증폭 + 패시브 계수 재귀 적용
    h2_total = base_magic * 1.28 * (1.1 + 0.001 * ap)

    print(f"--- [AD: {ad}, AP: {ap}] 예측 결과 ---")
    print(f"가설 1 (일반 적용): {h1_total:.1f}")
    print(f"가설 2 (재귀 적용): {h2_total:.1f}")


# 아래에 연습모드 상태창의 AD, AP를 입력해서 실행하세요.
check_yunara_damage(ad=274, ap=327)  # 788 실제
check_yunara_damage(ad=308, ap=324)  # 838
check_yunara_damage(ad=278, ap=389)  # 947
