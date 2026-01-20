import matplotlib.pyplot as plt
import json
import os
from datetime import datetime
from champion import Ashe, Champion, Target
from items import (
    KrakenSlayer, InfinityEdge, BerserkerGreaves, BladeOfRuinedKing,
    TheCollector, YunTalWildarrows, PhantomDancer, HextechScopeC44, Stormrazor,
    GuinsoosRageblade, Terminus, MortalReminder, Bloodthirster, LordDominiksRegards, SerpentsFang, Item,
    Pickaxe, BFSword, ScoutingsSlingshot, LongSword, RecurveBow, Noonquiver, VampiricScepter, HearthboundAxe, Dagger, CloakofAgility
)
from settings import SIMULATION_SETTINGS
from runes import LethalTempo


# 4. 시뮬레이션 엔진
def calculate_mitigation(raw_phys, raw_magic, target: Target, champion: Champion):
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


def run_simulation(champion: Champion, target: Target, verbose=True):
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


# 아이템 세트 생성 함수 (매번 새로운 객체 반환)
def get_item_set(set_name):
    # 1. YunTal (0%)
    if set_name == "Set1":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.0)]
    # 2. Kraken
    elif set_name == "Set2":
        return [BerserkerGreaves(), KrakenSlayer()]
    # 3. Terminus
    elif set_name == "Set3":
        return [BerserkerGreaves(), Terminus()]
    # 4. Guinsoo
    elif set_name == "Set4":
        return [BerserkerGreaves(), GuinsoosRageblade()]
    # 5. IE
    elif set_name == "Set5":
        return [BerserkerGreaves(), InfinityEdge()]
    # 6. Collector
    elif set_name == "Set6":
        return [BerserkerGreaves(), TheCollector()]
    # 7. BotRK
    elif set_name == "Set7":
        return [BerserkerGreaves(), BladeOfRuinedKing()]
    # 8. C44
    elif set_name == "Set8":
        return [BerserkerGreaves(), HextechScopeC44()]
    # 9. Stormrazor
    elif set_name == "Set9":
        return [BerserkerGreaves(), Stormrazor()]
    # 10. YunTal (5%)
    elif set_name == "Set10":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.05)]
    # 11. YunTal (10%)
    elif set_name == "Set11":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.10)]
    # 12. YunTal (15%)
    elif set_name == "Set12":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.15)]
    # 13. YunTal (20%)
    elif set_name == "Set13":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.20)]
    # 14. YunTal (25%)
    elif set_name == "Set14":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.25)]
    # 15. BotRK (AS+18%)
    elif set_name == "Set15":
        bot = BladeOfRuinedKing()
        bot.stats['as'] += 0.18
        bot.name = "BotRK (AS+18%)"
        return [BerserkerGreaves(), bot]
    return []


# --- 메인 실행부 ---
if __name__ == "__main__":
    # 공통 설정 (1코어 타이밍)
    dummy_hp = 1700
    dummy_armor = 60
    dummy_mr = 40 # 마저도 적당히 설정 (기본값 50에서 조금 낮춤)
    
    # 비교할 15가지 1코어 빌드 정의
    item_sets = [
        ("1. YunTal(0%)", "Set1"),
        ("2. Kraken", "Set2"),
        ("3. Terminus", "Set3"),
        ("4. Guinsoo", "Set4"),
        ("5. Infinity Edge", "Set5"),
        ("6. Collector", "Set6"),
        ("7. BotRK", "Set7"),
        ("8. C44", "Set8"),
        ("9. Stormrazor", "Set9"),
        ("10. YunTal(5%)", "Set10"),
        ("11. YunTal(10%)", "Set11"),
        ("12. YunTal(15%)", "Set12"),
        ("13. YunTal(20%)", "Set13"),
        ("14. YunTal(25%)", "Set14"),
        ("15. BotRK(AS+18%)", "Set15"),
    ]
    
    results = []
    
    # 1. 모든 시뮬레이션 실행 (모두 치명적 속도 적용)
    for label, set_name in item_sets:
        target = Target(hp=dummy_hp, armor=dummy_armor, magic_resist=dummy_mr, bonus_hp=0) # 1코어라 추가 체력 거의 없음 가정
        ashe = Ashe(level=9, q_level=2) # 1코어 타이밍 레벨 조정 (예: 9레벨)
        
        # 룬 설정 (항상 적용)
        ashe.set_rune(LethalTempo())
        
        # 아이템 생성 및 장착
        items = get_item_set(set_name)
        item_names = []
        total_cost = 0
        core_cost = 0 # 신발 제외 가격
        
        for item in items:
            item_names.append(item.name)
            total_cost += item.cost
            # 신발 제외 가격 계산 (Berserker Greaves = 1100)
            if item.name != "Berserker Greaves":
                core_cost += item.cost
                
            ashe.add_item(item)
            if isinstance(item, HextechScopeC44):
                item.activate_vision_focus(ashe)
                
        history, dps, kill_time = run_simulation(ashe, target, verbose=False)
        
        # 가성비 계산 (DPS / Gold)
        efficiency = dps / total_cost if total_cost > 0 else 0
        
        results.append({
            'label': label, 
            'history': history, 
            'dps': dps,
            'kill_time': kill_time,
            'item_names': item_names,
            'total_cost': total_cost,
            'core_cost': core_cost,
            'efficiency': efficiency
        })
        print(f"{label} -> DPS: {dps:.2f}, Cost: {total_cost} (Core: {core_cost}), DPG: {efficiency:.4f}")

    # 2. 결과 저장 (JSON)
    champion_info = {"name": "Ashe", "level": 9, "rune": "Lethal Tempo"}
    target_info = {"hp": dummy_hp, "armor": dummy_armor, "mr": dummy_mr}
    save_results(champion_info, target_info, results)

    # 3. DPS 기준 내림차순 정렬
    results.sort(key=lambda x: x['dps'], reverse=True)

    # 4. 그래프 그리기
    plt.figure(figsize=(14, 9))
    
    # 색상 팔레트 (15개 이상)
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
              '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf', 
              '#1a55FF', '#FF1493', '#000000', '#800000', '#008080']
    
    # 그래프 스타일 설정 가져오기
    graph_style = SIMULATION_SETTINGS.get('graph_style', 'linear')
    drawstyle = 'steps-post' if graph_style == 'step' else 'default'
    
    for i, res in enumerate(results):
        times, hps = zip(*res['history'])
        kill_time = res['kill_time']
        dps_val = res['dps']
        eff_val = res['efficiency'] * 1000
        core_cost = res['core_cost']
        label = res['label']
        
        # 색상 순환
        color = colors[i % len(colors)]
        
        # 순위
        rank = i + 1
        
        # 범례 라벨 (DPS, DPG, Core Cost 포함)
        legend_label = f"#{rank} {label}\n   DPS: {dps_val:.0f} | DPG: {eff_val:.2f} | Cost: {core_cost}"
        
        # 선 그리기
        plt.plot(times, hps, color=color, linewidth=2, label=legend_label, drawstyle=drawstyle)
        
        # Kill time 점 찍기 및 텍스트 제거 (요청사항 반영)
        # plt.scatter([kill_time], [0], color=color, s=50, zorder=10, edgecolors='white')
        # text_y = 100 + (i * 150)
        # plt.text(kill_time, text_y, f"{kill_time:.2f}s", 
        #          color=color, fontweight='bold', ha='center', va='bottom', fontsize=9)

    plt.title(f'Ashe DPS Comparison (1-Core Timing, Target: HP {dummy_hp}, AR {dummy_armor}) - {graph_style.capitalize()} Graph')
    plt.xlabel('Time (s)')
    plt.ylabel('Target HP')
    plt.axhline(y=0, color='black', linestyle='--')
    plt.grid(True, alpha=0.3)
    # 범례가 너무 많으므로 그래프 밖으로 뺌
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
    plt.tight_layout()
    plt.show()
