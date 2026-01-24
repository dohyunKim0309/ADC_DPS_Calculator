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
    total_damage_dealt = 0.0 # 누적 대미지 (오버킬 포함)
    
    # 시뮬레이션 시작 전 초기 상태 기록
    history.append((0.0, target.current_hp))

    if verbose:
        print(f"--- Simulation Start: {champion.name} vs Dummy ---")
        print(f"Stats - AD: {champion.total_ad}, AS: {champion.current_attack_speed}")

    while target.current_hp > 0:
        # 0. 챔피언 상태 업데이트 (스킬 쿨타임 등)
        if hasattr(champion, 'update'):
            s_phys, s_magic = champion.update(current_time, target)
            if s_phys > 0 or s_magic > 0:
                actual_s_phys, actual_s_magic = calculate_mitigation(s_phys, s_magic, target, champion)
                skill_dmg = actual_s_phys + actual_s_magic
                target.current_hp -= skill_dmg
                total_damage_dealt += skill_dmg
                if verbose:
                    print(f"[{current_time:.3f}s] Skill Dmg: {skill_dmg:.1f} -> HP: {max(0, target.current_hp):.1f}")
                
                if target.current_hp <= 0:
                    history.append((round(current_time, 2), 0))
                    break

        # 1. 대미지 성분 계산
        p_base, m_base, p_onhit, m_onhit = champion.get_one_hit_damage(target, current_time)

        # 2. 방어력/마저 적용
        raw_phys = p_base + p_onhit
        raw_magic = m_base + m_onhit

        actual_phys, actual_magic = calculate_mitigation(
            raw_phys, raw_magic, target, champion
        )
        total_damage = actual_phys + actual_magic

        # 3. 체력 차감 및 누적 딜 계산
        target.current_hp -= total_damage
        total_damage_dealt += total_damage # 오버킬 대미지도 그대로 누적
        attack_count += 1

        if verbose:
            rune_stacks = champion.rune.stacks if champion.rune else 0
            rune_bonus_as = champion.rune.get_bonus_as() if champion.rune else 0.0
            
            print(
                f"[{current_time:.3f}s] Attack #{attack_count}: "
                f"AS {champion.current_attack_speed:.2f} (Rune +{rune_bonus_as*100:.1f}%, Stacks {rune_stacks}) | "
                f"Dmg {total_damage:.1f} (Phys:{actual_phys:.1f}, Mag:{actual_magic:.1f}) -> "
                f"HP: {max(0, target.current_hp):.1f}"
            )

        # 4. 기록
        recorded_hp = max(0, target.current_hp)
        history.append((round(current_time, 2), recorded_hp))
        
        # 죽었으면 종료
        if target.current_hp <= 0:
            break
            
        # 5. 다음 공격 시간 계산
        attack_interval = champion.get_attack_interval()
        current_time += attack_interval

    # 결과 요약
    kill_time = current_time 
    
    # DPS 계산: (오버킬 포함 총 대미지) / (마지막 공격 시점)
    if kill_time > 0:
        dps = total_damage_dealt / kill_time
    else:
        # 0초 킬 (한 방)
        dps = total_damage_dealt
        
    if verbose:
        print(f"--- Killed in {kill_time:.3f}s | DPS: {dps:.2f} ---")

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
