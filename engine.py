import json
import os
from datetime import datetime

# 시뮬레이션 엔진
def calculate_mitigation(raw_phys, raw_magic, target, champion):
    """
    방어력/마법저항력 및 관통력을 적용하여 실제 피해량을 계산
    공식: Effective Stat = Stat * (1 - %Pen) - Flat Pen
    대미지 감소율: 100 / (100 + Effective Stat)
    """
    # 1. 물리 관통력 적용 (% 방관 -> 고정 방관)
    # champion 객체에서 관통력 정보를 가져옵니다.
    eff_armor = target.armor * (1 - champion.armor_pen_percent) - champion.lethality
    eff_armor = max(0, eff_armor)  # 관통력으로 방어력이 음수가 되지는 않음

    # 2. 마법 관통력 적용 (% 마관 -> 고정 마관)
    # Champion 클래스에 magic_pen_flat이 없으면 0으로 처리
    magic_pen_flat = getattr(champion, 'magic_pen_flat', 0)
    eff_mr = target.magic_resist * (1 - champion.magic_pen_percent) - magic_pen_flat
    eff_mr = max(0, eff_mr)

    actual_phys = raw_phys * (100.0 / (100.0 + eff_armor))
    actual_magic = raw_magic * (100.0 / (100.0 + eff_mr))

    return actual_phys, actual_magic


def run_simulation(champion, target, verbose=True):
    current_time = 0.0
    history = []  # (시간, 남은체력) 기록
    attack_count = 0
    total_damage_dealt = 0.0 # 누적 대미지
    
    # DPS 계산을 위한 변수 (직전 공격 시점 데이터)
    prev_damage_dealt = 0.0
    prev_attack_time = 0.0

    # 시뮬레이션 시작 전 초기 상태 기록
    history.append((0.0, target.current_hp))

    if verbose:
        print(f"--- Simulation Start: {champion.name} vs Dummy ---")
        print(f"Stats - AD: {champion.total_ad}, AS: {champion.current_attack_speed}")

    while target.current_hp > 0:
        # 0. 공격 간격 계산 및 시간 경과 (선딜레이 반영)
        # 첫 공격도 공격 속도에 따른 딜레이 후 적중한다고 가정 (그래프의 자연스러움을 위해)
        attack_interval = champion.get_attack_interval()
        current_time += attack_interval

        # 현재 상태를 직전 상태로 저장 (이번 공격 대미지 적용 전)
        if attack_count > 0:
            prev_damage_dealt = total_damage_dealt
            prev_attack_time = current_time - attack_interval # 직전 공격 시간

        # 1. 대미지 성분 계산 (챔피언 클래스 내부 로직)
        p_base, m_base, p_onhit, m_onhit = champion.get_one_hit_damage(target, current_time)

        # 2. 방어력/마저 적용 (시뮬레이션 로직)
        # 물리 피해 합산 (기본 + 온힛)
        raw_phys = p_base + p_onhit

        # 마법 피해 합산 (기본 + 온힛)
        raw_magic = m_base + m_onhit

        # 방어력/마저 및 관통력 적용
        actual_phys, actual_magic = calculate_mitigation(
            raw_phys, raw_magic, target, champion
        )
        total_damage = actual_phys + actual_magic

        # 3. 체력 차감
        target.current_hp -= total_damage
        total_damage_dealt += total_damage # 누적 대미지 기록
        attack_count += 1

        if verbose:
            # 룬 스택 정보 가져오기
            rune_stacks = champion.rune.stacks if champion.rune else 0
            rune_bonus_as = champion.rune.get_bonus_as() if champion.rune else 0.0
            
            print(
                f"[{current_time:.3f}s] Attack #{attack_count}: "
                f"AS {champion.current_attack_speed:.2f} (Rune +{rune_bonus_as*100:.1f}%, Stacks {rune_stacks}) | "
                f"Dmg {total_damage:.1f} (Phys:{actual_phys:.1f}, Mag:{actual_magic:.1f}) -> "
                f"HP: {max(0, target.current_hp):.1f}"
            )

        # 4. 기록 (0 이하일 경우 0으로 기록)
        recorded_hp = max(0, target.current_hp)
        history.append((round(current_time, 2), recorded_hp))
        
        # 만약 이번 공격으로 죽었다면 루프 종료
        if target.current_hp <= 0:
            break

    # 결과 요약
    kill_time = current_time # 루프가 break된 시점의 시간이 킬 타임
    
    # DPS 계산: (N-1번째 타격까지의 누적 대미지) / (N-1번째 타격 시간)
    if attack_count > 1:
        dps_damage = prev_damage_dealt
        dps_time = prev_attack_time
    else:
        dps_damage = total_damage_dealt
        dps_time = kill_time
        
    dps = dps_damage / dps_time if dps_time > 0 else 0
    
    if verbose:
        print(f"--- Killed in {kill_time:.3f}s | DPS (N-1): {dps:.2f} ---")

    return history, dps, kill_time


def save_results(champion_info, target_info, results):
    """
    시뮬레이션 결과를 JSON 파일로 저장합니다.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sim_result_{timestamp}.json"
    
    data = {
        "meta": {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "champion": champion_info,
            "target": target_info
        },
        "results": []
    }
    
    for res in results:
        entry = {
            "label": res['label'],
            "dps": res['dps'],
            "efficiency": res['efficiency'],
            "total_cost": res['total_cost'],
            "core_cost": res['core_cost'],
            "kill_time": res['kill_time'],
            "item_names": res['item_names'],
            "history": res['history']
        }
        data["results"].append(entry)
        
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\n[System] Results successfully saved to: {os.path.abspath(filename)}")
    except Exception as e:
        print(f"\n[Error] Failed to save results: {e}")
