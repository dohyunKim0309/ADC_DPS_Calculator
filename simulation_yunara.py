import matplotlib.pyplot as plt
from champion import Yunara, Target
from items import (
    KrakenSlayer, InfinityEdge, BerserkerGreaves, BladeOfRuinedKing,
    TheCollector, YunTalWildarrows, PhantomDancer, HextechScopeC44, Stormrazor,
    GuinsoosRageblade, Terminus, MortalReminder, Bloodthirster, LordDominiksRegards, SerpentsFang, Item,
    Pickaxe, BFSword, ScoutingsSlingshot, LongSword, RecurveBow, Noonquiver, VampiricScepter, HearthboundAxe, Dagger, CloakofAgility,
    NashorsTooth, RabadonsDeathcap, Shadowflame, HextechGunblade
)
from settings import SIMULATION_SETTINGS
from runes import LethalTempo
from engine import run_simulation, save_results


# 1코어 아이템 세트 생성 함수
def get_item_set_1core(set_name):
    # 1. Kraken
    if set_name == "Set1":
        return [BerserkerGreaves(), KrakenSlayer()]
    # 2. Guinsoo
    elif set_name == "Set2":
        return [BerserkerGreaves(), GuinsoosRageblade()]
    # 3. BotRK
    elif set_name == "Set3":
        return [BerserkerGreaves(), BladeOfRuinedKing()]
    # 4. YunTal (25%)
    elif set_name == "Set4":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.25)]
    # 5. YunTal (0%)
    elif set_name == "Set5":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.0)]
    return []

# 2코어 아이템 세트 생성 함수
def get_item_set_2core(set_name):
    # 1. Krk+Gui
    if set_name == "Set1":
        return [BerserkerGreaves(), KrakenSlayer(), GuinsoosRageblade()]
    # 2. Krk+Yun(25%)
    elif set_name == "Set2":
        return [BerserkerGreaves(), KrakenSlayer(), YunTalWildarrows(crit=0.25)]
    # 3. Krk+PD
    elif set_name == "Set3":
        return [BerserkerGreaves(), KrakenSlayer(), PhantomDancer()]
    # 4. Gui+Yun(25%)
    elif set_name == "Set4":
        return [BerserkerGreaves(), GuinsoosRageblade(), YunTalWildarrows(crit=0.25)]
    # 5. Gui+PD
    elif set_name == "Set5":
        return [BerserkerGreaves(), GuinsoosRageblade(), PhantomDancer()]
    # 6. Gui+Stm
    elif set_name == "Set6":
        return [BerserkerGreaves(), GuinsoosRageblade(), Stormrazor()]
    # 7. Krk+Stm
    elif set_name == "Set7":
        return [BerserkerGreaves(), KrakenSlayer(), Stormrazor()]
    # 8. Yun(25%)+Stm
    elif set_name == "Set8":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.25), Stormrazor()]
    return []

# 3코어 아이템 세트 생성 함수
def get_item_set_3core(set_name):
    # 1. Krk+PD+IE
    if set_name == "Set1":
        return [BerserkerGreaves(), KrakenSlayer(), PhantomDancer(), InfinityEdge()]
    # 2. Krk+PD+LDR
    elif set_name == "Set2":
        return [BerserkerGreaves(), KrakenSlayer(), PhantomDancer(), LordDominiksRegards()]
    # 3. Krk+PD+C44
    elif set_name == "Set3":
        return [BerserkerGreaves(), KrakenSlayer(), PhantomDancer(), HextechScopeC44()]
    # 4. Krk+Yun+LDR
    elif set_name == "Set4":
        return [BerserkerGreaves(), KrakenSlayer(), YunTalWildarrows(crit=0.25), LordDominiksRegards()]
    # 5. Krk+Yun+IE
    elif set_name == "Set5":
        return [BerserkerGreaves(), KrakenSlayer(), YunTalWildarrows(crit=0.25), InfinityEdge()]
    # 6. Krk+Yun+C44
    elif set_name == "Set6":
        return [BerserkerGreaves(), KrakenSlayer(), YunTalWildarrows(crit=0.25), HextechScopeC44()]
    # 7. Yun+Gui+C44
    elif set_name == "Set7":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.25), GuinsoosRageblade(), HextechScopeC44()]
    # 8. Yun+Gui+IE
    elif set_name == "Set8":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.25), GuinsoosRageblade(), InfinityEdge()]
    # 9. Yun+Gui+LDR
    elif set_name == "Set9":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.25), GuinsoosRageblade(), LordDominiksRegards()]
    # 10. Yun+Stm+C44
    elif set_name == "Set10":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.25), Stormrazor(), HextechScopeC44()]
    # 11. Yun+Stm+IE
    elif set_name == "Set11":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.25), Stormrazor(), InfinityEdge()]
    # 12. Yun+Stm+LDR
    elif set_name == "Set12":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.25), Stormrazor(), LordDominiksRegards()]
    # 13. Yun+PD+IE
    elif set_name == "Set13":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.25), PhantomDancer(), InfinityEdge()]
    # 14. Yun+PD+LDR
    elif set_name == "Set14":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.25), PhantomDancer(), LordDominiksRegards()]
    # 15. Yun+PD+C44
    elif set_name == "Set15":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.25), PhantomDancer(), HextechScopeC44()]
    # 16. Gui+Nash+Rabadon
    elif set_name == "Set16":
        return [BerserkerGreaves(), GuinsoosRageblade(), NashorsTooth(), RabadonsDeathcap()]
    # 17. Gui+Nash+Shadowflame
    elif set_name == "Set17":
        return [BerserkerGreaves(), GuinsoosRageblade(), NashorsTooth(), Shadowflame()]
    # 18. Gui+Terminus+Shadowflame
    elif set_name == "Set18":
        return [BerserkerGreaves(), GuinsoosRageblade(), Terminus(), Shadowflame()]
    return []

# 4코어 아이템 세트 생성 함수
def get_item_set_4core(set_name):
    # 1. Krk+Yun+LDR+IE
    if set_name == "Set1":
        return [BerserkerGreaves(), KrakenSlayer(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), InfinityEdge()]
    # 2. Krk+Yun+LDR+Bot
    elif set_name == "Set2":
        return [BerserkerGreaves(), KrakenSlayer(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), BladeOfRuinedKing()]
    # 3. Krk+Yun+LDR+C44
    elif set_name == "Set3":
        return [BerserkerGreaves(), KrakenSlayer(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), HextechScopeC44()]
    # 4. Krk+Yun+LDR+Gui
    elif set_name == "Set4":
        return [BerserkerGreaves(), KrakenSlayer(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), GuinsoosRageblade()]
    # 5. Yun+PD+IE+LDR
    elif set_name == "Set5":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.25), PhantomDancer(), InfinityEdge(), LordDominiksRegards()]
    # 6. Krk+Yun+LDR+Shadow
    elif set_name == "Set6":
        return [BerserkerGreaves(), KrakenSlayer(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), Shadowflame()]
    # 7. Krk+Yun+LDR+Nash
    elif set_name == "Set7":
        return [BerserkerGreaves(), KrakenSlayer(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), NashorsTooth()]
    # 8. Krk+Yun+LDR+Rabadon
    elif set_name == "Set8":
        return [BerserkerGreaves(), KrakenSlayer(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), RabadonsDeathcap()]
    return []

# 5코어 아이템 세트 생성 함수
def get_item_set_5core(set_name):
    # 1. Krk+Yun+LDR+Gui+Rabadon
    if set_name == "Set1":
        return [BerserkerGreaves(), KrakenSlayer(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), GuinsoosRageblade(), RabadonsDeathcap()]
    # 2. Krk+Yun+LDR+Gui+Shadow
    elif set_name == "Set2":
        return [BerserkerGreaves(), KrakenSlayer(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), GuinsoosRageblade(), Shadowflame()]
    # 3. Krk+Yun+LDR+Gui+BT
    elif set_name == "Set3":
        return [BerserkerGreaves(), KrakenSlayer(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), GuinsoosRageblade(), Bloodthirster()]
    # 4. Krk+Yun+LDR+Gui+IE
    elif set_name == "Set4":
        return [BerserkerGreaves(), KrakenSlayer(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), GuinsoosRageblade(), InfinityEdge()]
    # 5. Krk+Yun+LDR+Gui+Nash
    elif set_name == "Set5":
        return [BerserkerGreaves(), KrakenSlayer(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), GuinsoosRageblade(), NashorsTooth()]
    # 6. Krk+Yun+LDR+Gui+C44
    elif set_name == "Set6":
        return [BerserkerGreaves(), KrakenSlayer(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), GuinsoosRageblade(), HextechScopeC44()]
    # 7. Krk+Yun+LDR+Gui+Bot
    elif set_name == "Set7":
        return [BerserkerGreaves(), KrakenSlayer(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), GuinsoosRageblade(), BladeOfRuinedKing()]
    # 8. Krk+Yun+LDR+IE+Shadow
    elif set_name == "Set8":
        return [BerserkerGreaves(), KrakenSlayer(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), InfinityEdge(), Shadowflame()]
    # 9. Krk+Yun+LDR+IE+C44
    elif set_name == "Set9":
        return [BerserkerGreaves(), KrakenSlayer(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), InfinityEdge(), HextechScopeC44()]
    # 10. Krk+Yun+LDR+IE+BT
    elif set_name == "Set10":
        return [BerserkerGreaves(), KrakenSlayer(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), InfinityEdge(), Bloodthirster()]
    return []

# 6코어 아이템 세트 생성 함수
def get_item_set_6core(set_name):
    # 1. Krk+Yun+LDR+Gui+IE+C44
    if set_name == "Set1":
        return [KrakenSlayer(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), GuinsoosRageblade(), InfinityEdge(), HextechScopeC44(), BerserkerGreaves()]
    # 2. Yun+LDR+IE+Nash+Shadow+Deathcap
    elif set_name == "Set2":
        return [YunTalWildarrows(crit=0.25), LordDominiksRegards(), InfinityEdge(), NashorsTooth(), Shadowflame(), RabadonsDeathcap(), BerserkerGreaves()]
    # 3. Krk+Yun+LDR+IE+C44+Bot
    elif set_name == "Set3":
        return [KrakenSlayer(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), InfinityEdge(), HextechScopeC44(), BladeOfRuinedKing(), BerserkerGreaves()]
    # 4. Krk+Yun+LDR+IE+C44+Shadow
    elif set_name == "Set4":
        return [KrakenSlayer(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), InfinityEdge(), HextechScopeC44(), Shadowflame(), BerserkerGreaves()]
    # 5. Krk+Yun+LDR+Gunblade+IE+C44
    elif set_name == "Set5":
        return [KrakenSlayer(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), HextechGunblade(), InfinityEdge(), HextechScopeC44(), BerserkerGreaves()]
    return []


# --- 메인 실행부 ---
if __name__ == "__main__":
    # === 1코어 시뮬레이션 (비활성화) ===
    if False:
        print("\n=== 1-Core Simulation ===")
        # ... (생략) ...

    # === 2코어 시뮬레이션 (비활성화) ===
    if False:
        print("\n=== 2-Core Simulation ===")
        # ... (생략) ...

    # === 3코어 시뮬레이션 (비활성화) ===
    if False:
        print("\n=== 3-Core Simulation ===")
        # ... (생략) ...

    # === 4코어 시뮬레이션 (비활성화) ===
    if False:
        print("\n=== 4-Core Simulation ===")
        # ... (생략) ...

    # === 5코어 시뮬레이션 (비활성화) ===
    if False:
        print("\n=== 5-Core Simulation ===")
        # ... (생략) ...

    # === 6코어 시뮬레이션 ===
    print("\n=== 6-Core Simulation ===")
    dummy_hp_6 = 4000
    dummy_armor_6 = 250
    dummy_mr_6 = 100
    
    item_sets_6core = [
        ("1. Krk+Yun+LDR+Gui+IE+C44", "Set1"),
        ("2. Yun+LDR+IE+Nash+Shadow+Deathcap", "Set2"),
        ("3. Krk+Yun+LDR+IE+C44+Bot", "Set3"),
        ("4. Krk+Yun+LDR+IE+C44+Shadow", "Set4"),
        ("5. Krk+Yun+LDR+Gun+IE+C44", "Set5"),
    ]
    
    results_6 = []
    
    for label, set_name in item_sets_6core:
        target = Target(hp=dummy_hp_6, armor=dummy_armor_6, magic_resist=dummy_mr_6, bonus_hp=dummy_hp_6-1000)
        yunara = Yunara(level=18, q_level=5) 
        yunara.set_rune(LethalTempo())
        
        items = get_item_set_6core(set_name)
        item_names = []
        total_cost = 0
        core_cost = 0
        
        for item in items:
            item_names.append(item.name)
            total_cost += item.cost
            # 6코어는 신발 포함 7개 아이템이므로 신발 제외 가격 계산
            if item.name != "Berserker Greaves":
                core_cost += item.cost
            yunara.add_item(item)
            if isinstance(item, HextechScopeC44):
                item.activate_vision_focus(yunara)
                
        history, dps, kill_time = run_simulation(yunara, target, verbose=False)
        efficiency = dps / total_cost if total_cost > 0 else 0
        
        results_6.append({
            'label': label, 'history': history, 'dps': dps, 'kill_time': kill_time,
            'item_names': item_names, 'total_cost': total_cost, 'core_cost': core_cost, 'efficiency': efficiency
        })
        print(f"{label} -> DPS: {dps:.2f}, Cost: {total_cost} (Core: {core_cost}), DPG: {efficiency:.4f}")

    # 6코어 그래프
    results_6.sort(key=lambda x: x['dps'], reverse=True)
    plt.figure(figsize=(14, 9))
    colors_6 = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    graph_style = SIMULATION_SETTINGS.get('graph_style', 'linear')
    drawstyle = 'steps-post' if graph_style == 'step' else 'default'
    
    for i, res in enumerate(results_6):
        times, hps = zip(*res['history'])
        kill_time = res['kill_time']
        dps_val = res['dps']
        eff_val = res['efficiency'] * 1000
        core_cost = res['core_cost']
        label = res['label']
        color = colors_6[i % len(colors_6)]
        legend_label = f"#{i+1} {label}\n   DPS: {dps_val:.0f} | DPG: {eff_val:.2f} | Cost: {core_cost}"
        plt.plot(times, hps, color=color, linewidth=2, label=legend_label, drawstyle=drawstyle)
        
    plt.title(f'Yunara DPS Comparison (6-Core, Target: {dummy_hp_6}/{dummy_armor_6}/{dummy_mr_6})')
    plt.xlabel('Time (s)')
    plt.ylabel('Target HP')
    plt.axhline(y=0, color='black', linestyle='--')
    plt.grid(True, alpha=0.3)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
    plt.tight_layout()
    plt.show()
