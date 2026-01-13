from champion import Ashe, Champion, Target


# 4. 시뮬레이션 엔진
def calculate_mitigation(phys_damage, magic_damage, ar, mr):
    """방어력/마법저항력 계산 공식: 100 / (100 + 저항력)"""
    ar_modifier = 100.0 / (100.0 + ar)
    mr_modifier = 100.0 / (100.0 + mr)
    return phys_damage * ar_modifier, magic_damage * mr_modifier


def run_simulation(champion: Champion, target: Target, verbose=True):
    current_time = 0.0
    history = []  # (시간, 남은체력) 기록
    attack_count = 0

    # 시뮬레이션 시작 전 초기 상태 기록
    history.append((0.0, target.current_hp))

    print(f"--- Simulation Start: {champion.name} vs Dummy ---")
    print(f"Stats - AD: {champion.total_ad}, AS: {champion.current_attack_speed}")

    while target.current_hp > 0:
        # 1. 대미지 성분 계산 (챔피언 클래스 내부 로직)
        p_base, m_base, p_onhit, m_onhit = champion.get_one_hit_damage(target)

        # 2. 방어력/마저 적용 (시뮬레이션 로직)
        # 물리 피해 합산 (기본 + 온힛)
        raw_phys = p_base + p_onhit

        # 마법 피해 합산 (기본 + 온힛)
        raw_magic = m_base + m_onhit

        actual_phys, actual_magic = calculate_mitigation(
            raw_phys, raw_magic, target.armor, target.magic_resist
        )
        total_damage = actual_phys + actual_magic

        # 3. 체력 차감
        target.current_hp -= total_damage
        attack_count += 1

        if verbose:
            print(
                f"[{current_time:.2f}s] Attack #{attack_count}: Dmg {total_damage:.1f} "
                f"(Phys:{actual_phys:.1f}, Mag:{actual_magic:.1f}) -> "
                f"HP: {max(0, target.current_hp):.1f}"
            )

        # 4. 시간 경과 기록 (체력이 0이 되어도 이번 공격은 들어간 것으로 처리하고 시간 흐름)
        # 다음 공격까지의 딜레이 계산
        attack_interval = champion.get_attack_interval()
        current_time += attack_interval

        # 기록 (0 이하일 경우 0으로 기록)
        recorded_hp = max(0, target.current_hp)
        history.append((round(current_time, 2), recorded_hp))

    # 결과 요약
    dps = target.max_hp / current_time if current_time > 0 else 0
    print(f"--- Killed in {current_time:.2f}s | DPS: {dps:.2f} ---")

    return history, dps


# --- 메인 실행부 예시 ---
if __name__ == "__main__":
    # 1. 적 설정 (체력 2000, 방어 200, 마저 100)
    dummy = Target(hp=2000, armor=200, magic_resist=100)

    # 2. 챔피언 설정 (애쉬, 18레벨 가정)
    my_ashe = Ashe(level=18)

    # 아이템 장착 시뮬레이션 (예: 공격력 100, 공속 50% 추가)
    my_ashe.bonus_ad = 100
    my_ashe.bonus_as_percent = 0.5  # 50%

    # 3. 시뮬레이션 실행
    history_data, final_dps = run_simulation(my_ashe, dummy)

    # (선택 사항) 그래프 그리기
    # times, hps = zip(*history_data)
    # plt.plot(times, hps)
    # plt.show()
