import matplotlib.pyplot as plt
from champion import Ashe, Target
from items import (
    KrakenSlayer, InfinityEdge, BerserkerGreaves, BladeOfRuinedKing,
    TheCollector, YunTalWildarrows, PhantomDancer, HextechScopeC44, Stormrazor,
    GuinsoosRageblade, Terminus, MortalReminder, Bloodthirster, LordDominiksRegards, SerpentsFang, Item,
    Pickaxe, BFSword, ScoutingsSlingshot, LongSword, RecurveBow, Noonquiver, VampiricScepter, HearthboundAxe, Dagger, CloakofAgility
)
from settings import SIMULATION_SETTINGS
from runes import LethalTempo
from engine import run_simulation, save_results


# 아이템 세트 생성 함수 (매번 새로운 객체 반환)
def get_item_set(set_name):
    # 1. Col+Yun+IE
    if set_name == "Set1":
        return [TheCollector(), YunTalWildarrows(crit=0.25), InfinityEdge(), BerserkerGreaves()]
    # 2. Col+Yun+LDR
    elif set_name == "Set2":
        return [TheCollector(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), BerserkerGreaves()]
    # 3. Krk+PD+IE
    elif set_name == "Set3":
        return [KrakenSlayer(), PhantomDancer(), InfinityEdge(), BerserkerGreaves()]
    # 4. Krk+PD+LDR
    elif set_name == "Set4":
        return [KrakenSlayer(), PhantomDancer(), LordDominiksRegards(), BerserkerGreaves()]
    # 5. Krk+Bot+Gui
    elif set_name == "Set5":
        return [KrakenSlayer(), BladeOfRuinedKing(), GuinsoosRageblade(), BerserkerGreaves()]
    # 6. Krk+Bot+LDR
    elif set_name == "Set6":
        return [KrakenSlayer(), BladeOfRuinedKing(), LordDominiksRegards(), BerserkerGreaves()]
    # 7. Yun+Krk+LDR
    elif set_name == "Set7":
        return [YunTalWildarrows(crit=0.25), KrakenSlayer(), LordDominiksRegards(), BerserkerGreaves()]
    # 8. Krk+BT(AS18)+LDR
    elif set_name == "Set8":
        bt = Bloodthirster()
        bt.stats['as'] = 0.18
        bt.name = "Bloodthirster (AS+18%)"
        return [KrakenSlayer(), bt, LordDominiksRegards(), BerserkerGreaves()]
    return []


# --- 메인 실행부 ---
if __name__ == "__main__":
    # 공통 설정 (3코어 타이밍)
    dummy_hp = 2500
    dummy_armor = 100
    dummy_mr = 50
    
    # 비교할 8가지 3코어 빌드 정의
    item_sets = [
        ("1. Col+Yun+IE", "Set1"),
        ("2. Col+Yun+LDR", "Set2"),
        ("3. Krk+PD+IE", "Set3"),
        ("4. Krk+PD+LDR", "Set4"),
        ("5. Krk+Bot+Gui", "Set5"),
        ("6. Krk+Bot+LDR", "Set6"),
        ("7. Yun+Krk+LDR", "Set7"),
        ("8. Krk+BT(AS18)+LDR", "Set8"),
    ]
    
    results = []
    
    # 1. 모든 시뮬레이션 실행 (모두 치명적 속도 적용)
    for label, set_name in item_sets:
        target = Target(hp=dummy_hp, armor=dummy_armor, magic_resist=dummy_mr, bonus_hp=dummy_hp-1000)
        ashe = Ashe(level=13, q_level=5) # 3코어 타이밍 레벨 13, Q 선마 가정 (또는 Q 5렙)
        
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
    champion_info = {"name": "Ashe", "level": 13, "rune": "Lethal Tempo"}
    target_info = {"hp": dummy_hp, "armor": dummy_armor, "mr": dummy_mr}
    save_results(champion_info, target_info, results)

    # 3. DPS 기준 내림차순 정렬
    results.sort(key=lambda x: x['dps'], reverse=True)

    # 4. 그래프 그리기
    plt.figure(figsize=(14, 9))
    
    # 색상 팔레트 (8개 이상)
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f']
    
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
        
        # Kill time 점 찍기
        plt.scatter([kill_time], [0], color=color, s=50, zorder=10, edgecolors='white')
        
        # 텍스트 (시간) - 겹치지 않게 y축 위치 조정
        text_y = 100 + (i * 150)
        plt.text(kill_time, text_y, f"{kill_time:.2f}s", 
                 color=color, fontweight='bold', ha='center', va='bottom', fontsize=9)

    plt.title(f'Ashe DPS Comparison (3-Core, Target: HP {dummy_hp}, AR {dummy_armor}) - {graph_style.capitalize()} Graph')
    plt.xlabel('Time (s)')
    plt.ylabel('Target HP')
    plt.axhline(y=0, color='black', linestyle='--')
    plt.grid(True, alpha=0.3)
    # 범례가 너무 많으므로 그래프 밖으로 뺌
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
    plt.tight_layout()
    plt.show()
