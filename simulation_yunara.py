import matplotlib.pyplot as plt
from champion import Yunara, Target
from items import (
    KrakenSlayer, InfinityEdge, BerserkerGreaves, BladeOfRuinedKing,
    TheCollector, YunTalWildarrows, PhantomDancer, HextechScopeC44, Stormrazor,
    GuinsoosRageblade, Terminus, MortalReminder, Bloodthirster, LordDominiksRegards, SerpentsFang, Item,
    Pickaxe, BFSword, ScoutingsSlingshot, LongSword, RecurveBow, Noonquiver, VampiricScepter, HearthboundAxe, Dagger, CloakofAgility,
    NashorsTooth, RabadonsDeathcap, Shadowflame, HextechGunblade, RunaansHurricane
)
from settings import SIMULATION_SETTINGS
from runes import LethalTempo, PressTheAttack, CutDown, CoupDeGrace
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

# 3코어 아이템 세트 생성 함수 (기존)
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

# 3코어 아이템 세트 생성 함수 (루난 버전, 신발 X)
def get_item_set_3core_runaan(set_name):
    # 1. Yun + Gui + Runaan
    if set_name == "Set1":
        return [YunTalWildarrows(crit=0.25), GuinsoosRageblade(), RunaansHurricane()]
    # 2. Yun + BotRK(AS+18%) + Runaan
    elif set_name == "Set2":
        bot = BladeOfRuinedKing()
        bot.stats['as'] += 0.18
        bot.name = "Blade of Ruined King (AS+18%)"
        return [YunTalWildarrows(crit=0.25), bot, RunaansHurricane()]
    # 4. Yun + IE + Runaan
    elif set_name == "Set4":
        return [YunTalWildarrows(crit=0.25), InfinityEdge(), RunaansHurricane()]
    # 5. Yun + Krk + Runaan
    elif set_name == "Set5":
        return [YunTalWildarrows(crit=0.25), KrakenSlayer(), RunaansHurricane()]
    # 6. Yun + Terminus + Runaan
    elif set_name == "Set6":
        return [YunTalWildarrows(crit=0.25), Terminus(), RunaansHurricane()]
    # 7. Gui + Terminus + Runaan
    elif set_name == "Set7":
        return [GuinsoosRageblade(), Terminus(), RunaansHurricane()]
    # 9. BotRK(AS+18%) + Gui + Runaan
    elif set_name == "Set9":
        bot = BladeOfRuinedKing()
        bot.stats['as'] += 0.18
        bot.name = "Blade of Ruined King (AS+18%)"
        return [bot, GuinsoosRageblade(), RunaansHurricane()]
    # 13. Yun + Run + LDR
    elif set_name == "Set13":
        return [YunTalWildarrows(crit=0.25), RunaansHurricane(), LordDominiksRegards()]
    # 15. Yun + Krk + LDR (신발 X)
    elif set_name == "Set15":
        return [YunTalWildarrows(crit=0.25), KrakenSlayer(), LordDominiksRegards()]
    # 16. Yun + Gui + LDR (신발 X)
    elif set_name == "Set16":
        return [YunTalWildarrows(crit=0.25), GuinsoosRageblade(), LordDominiksRegards()]
    # 17. Yun + Krk + IE (신발 X)
    elif set_name == "Set17":
        return [YunTalWildarrows(crit=0.25), KrakenSlayer(), InfinityEdge()]
    # 18. Yun + Gui + IE (신발 X)
    elif set_name == "Set18":
        return [YunTalWildarrows(crit=0.25), GuinsoosRageblade(), InfinityEdge()]
    # 19. Yun + LDR + IE (신발 X)
    elif set_name == "Set19":
        return [YunTalWildarrows(crit=0.25), LordDominiksRegards(), InfinityEdge()]
    # 20. Yun + Bot(AS18) + LDR (신발 X)
    elif set_name == "Set20":
        bot = BladeOfRuinedKing()
        bot.stats['as'] += 0.18
        bot.name = "Blade of Ruined King (AS+18%)"
        return [YunTalWildarrows(crit=0.25), bot, LordDominiksRegards()]
    return []

# 4코어 아이템 세트 생성 함수 (루난 버전, 신발 X)
def get_item_set_4core_runaan(set_name):
    # 1. Yun + Bot(AS18) + LDR + IE
    if set_name == "Set1":
        bot = BladeOfRuinedKing()
        bot.stats['as'] += 0.18
        bot.name = "Blade of Ruined King (AS+18%)"
        return [YunTalWildarrows(crit=0.25), bot, LordDominiksRegards(), InfinityEdge()]
    # 2. Yun + Bot(AS18) + LDR + Run
    elif set_name == "Set2":
        bot = BladeOfRuinedKing()
        bot.stats['as'] += 0.18
        bot.name = "Blade of Ruined King (AS+18%)"
        return [YunTalWildarrows(crit=0.25), bot, LordDominiksRegards(), RunaansHurricane()]
    # 3. Yun + Krk + LDR + IE
    elif set_name == "Set3":
        return [YunTalWildarrows(crit=0.25), KrakenSlayer(), LordDominiksRegards(), InfinityEdge()]
    # 4. Yun + Krk + LDR + Run
    elif set_name == "Set4":
        return [YunTalWildarrows(crit=0.25), KrakenSlayer(), LordDominiksRegards(), RunaansHurricane()]
    # 5. Yun + Run + LDR + IE
    elif set_name == "Set5":
        return [YunTalWildarrows(crit=0.25), RunaansHurricane(), LordDominiksRegards(), InfinityEdge()]
    # 6. Krk + PD + IE + LDR (윤탈 X)
    elif set_name == "Set6":
        return [KrakenSlayer(), PhantomDancer(), InfinityEdge(), LordDominiksRegards()]
    # 7. Yun + Gui + Run + LDR
    elif set_name == "Set7":
        return [YunTalWildarrows(crit=0.25), GuinsoosRageblade(), RunaansHurricane(), LordDominiksRegards()]
    return []

# 5코어 아이템 세트 생성 함수 (루난 버전, 신발 X)
def get_item_set_5core_runaan(set_name):
    # 0. (대조군) Yun+Krk+IE+LDR+Gui (신발 포함)
    if set_name == "Set0":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.25), KrakenSlayer(), InfinityEdge(), LordDominiksRegards(), GuinsoosRageblade()]
    # 1. Yun+Gui+Run+Trm+IE
    elif set_name == "Set1":
        return [YunTalWildarrows(crit=0.25), GuinsoosRageblade(), RunaansHurricane(), Terminus(), InfinityEdge()]
    # 2. Yun+Gui+Run+Trm+C44
    elif set_name == "Set2":
        return [YunTalWildarrows(crit=0.25), GuinsoosRageblade(), RunaansHurricane(), Terminus(), HextechScopeC44()]
    # 3. Yun+Gui+Run+Trm+Shadow
    elif set_name == "Set3":
        return [YunTalWildarrows(crit=0.25), GuinsoosRageblade(), RunaansHurricane(), Terminus(), Shadowflame()]
    # 4. Yun+Gui+Run+Trm+Nash
    elif set_name == "Set4":
        return [YunTalWildarrows(crit=0.25), GuinsoosRageblade(), RunaansHurricane(), Terminus(), NashorsTooth()]
    # 5. Yun+Gui+Run+Trm+Deathcap
    elif set_name == "Set5":
        return [YunTalWildarrows(crit=0.25), GuinsoosRageblade(), RunaansHurricane(), Terminus(), RabadonsDeathcap()]
    # 6. Yun+Gui+Run+Trm+BT
    elif set_name == "Set6":
        return [YunTalWildarrows(crit=0.25), GuinsoosRageblade(), RunaansHurricane(), Terminus(), Bloodthirster()]
    # 7. Yun+Gui+Run+LDR+IE
    elif set_name == "Set7":
        return [YunTalWildarrows(crit=0.25), GuinsoosRageblade(), RunaansHurricane(), LordDominiksRegards(), InfinityEdge()]
    # 8. Yun+Gui+Run+LDR+C44
    elif set_name == "Set8":
        return [YunTalWildarrows(crit=0.25), GuinsoosRageblade(), RunaansHurricane(), LordDominiksRegards(), HextechScopeC44()]
    # 9. Yun+Gui+Run+LDR+BT
    elif set_name == "Set9":
        return [YunTalWildarrows(crit=0.25), GuinsoosRageblade(), RunaansHurricane(), LordDominiksRegards(), Bloodthirster()]
    # 10. Yun+Gui+Run+LDR+Deathcap
    elif set_name == "Set10":
        return [YunTalWildarrows(crit=0.25), GuinsoosRageblade(), RunaansHurricane(), LordDominiksRegards(), RabadonsDeathcap()]
    return []

# 4코어 아이템 세트 생성 함수 (기존)
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
    # 9. Yun+LDR+Gui+Bot
    elif set_name == "Set9":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), GuinsoosRageblade(), BladeOfRuinedKing()]
    # 10. Yun+LDR+Gui+IE
    elif set_name == "Set10":
        return [BerserkerGreaves(), YunTalWildarrows(crit=0.25), LordDominiksRegards(), GuinsoosRageblade(), InfinityEdge()]
    return []

# 5코어 아이템 세트 생성 함수 (기존)
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

# 6코어 아이템 세트 생성 함수 (기존)
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

    # === 3코어 시뮬레이션 (루난 버전, 신발 X) (비활성화) ===
    if False:
        print("\n=== 3-Core Simulation (Runaan, No Boots) ===")
        # ... (생략) ...

    # === 4코어 시뮬레이션 (루난 버전, 신발 X) ===
    print("\n=== 4-Core Simulation (Runaan, No Boots) ===")
    dummy_hp_4 = 3000
    dummy_armor_4 = 180
    dummy_mr_4 = 90
    
    item_sets_4core_runaan = [
        ("1. Yun+Bot(AS18)+LDR+IE", "Set1"),
        ("2. Yun+Bot(AS18)+LDR+Run", "Set2"),
        ("3. Yun+Krk+LDR+IE", "Set3"),
        ("4. Yun+Krk+LDR+Run", "Set4"),
        ("5. Yun+Run+LDR+IE", "Set5"),
        ("6. Krk+PD+IE+LDR", "Set6"),
        ("7. Yun+Gui+Run+LDR", "Set7"),
    ]
    
    results_4_runaan = []
    
    # 룬 조합 정의
    rune_combinations = [
        ("LT+Cut", LethalTempo(), CutDown()),
        ("PTA+Coup", PressTheAttack(), CoupDeGrace())
    ]
    
    # 적 수 시나리오 (1, 2, 3명)
    target_counts = [1, 2, 3]
    
    for label, set_name in item_sets_4core_runaan:
        for rune_label, main_rune, sub_rune in rune_combinations:
            # 아이템 세트 미리 가져와서 루난 여부 확인
            temp_items = get_item_set_4core_runaan(set_name)
            has_runaan = any(item.name == "Runaan's Hurricane" for item in temp_items)
            
            # 루난이 없으면 1타겟만 시뮬레이션
            current_target_counts = [1] if not has_runaan else target_counts
            
            for t_count in current_target_counts:
                target = Target(hp=dummy_hp_4, armor=dummy_armor_4, magic_resist=dummy_mr_4, bonus_hp=dummy_hp_4-1000)
                yunara = Yunara(level=16, q_level=5) 
                
                # 룬 및 타겟 수 설정
                yunara.set_rune(main_rune)
                yunara.set_sub_rune(sub_rune)
                yunara.set_target_count(t_count)
                
                items = get_item_set_4core_runaan(set_name)
                item_names = []
                total_cost = 0
                core_cost = 0
                
                for item in items:
                    item_names.append(item.name)
                    total_cost += item.cost
                    # 신발 X 빌드이므로 모든 아이템이 Core Cost
                    core_cost += item.cost
                    yunara.add_item(item)
                    if isinstance(item, HextechScopeC44):
                        item.activate_vision_focus(yunara)
                        
                history, dps, kill_time = run_simulation(yunara, target, verbose=False)
                efficiency = dps / total_cost if total_cost > 0 else 0
                
                # 라벨에 타겟 수 표시
                full_label = f"{label} ({t_count} Targets)"
                
                results_4_runaan.append({
                    'label': full_label, 'history': history, 'dps': dps, 'kill_time': kill_time,
                    'item_names': item_names, 'total_cost': total_cost, 'core_cost': core_cost, 'efficiency': efficiency
                })
                print(f"{full_label} -> DPS: {dps:.2f}, Cost: {total_cost} (Core: {core_cost}), DPG: {efficiency:.4f}")

    # 4코어 루난 그래프
    results_4_runaan.sort(key=lambda x: x['dps'], reverse=True)
    plt.figure(figsize=(16, 10))
    # 색상 팔레트 확장 (21개 이상 필요)
    colors_4_runaan = [
        '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
        '#1a55FF', '#FF1493', '#000000', '#800000', '#008080', '#FFD700', '#00FF00', '#0000FF', '#FF4500', '#DA70D6',
        '#4B0082'
    ]
    graph_style = SIMULATION_SETTINGS.get('graph_style', 'linear')
    drawstyle = 'steps-post' if graph_style == 'step' else 'default'
    
    for i, res in enumerate(results_4_runaan):
        times, hps = zip(*res['history'])
        kill_time = res['kill_time']
        dps_val = res['dps']
        eff_val = res['efficiency'] * 1000
        core_cost = res['core_cost']
        label = res['label']
        color = colors_4_runaan[i % len(colors_4_runaan)]
        legend_label = f"#{i+1} {label}\n   DPS: {dps_val:.0f} | DPG: {eff_val:.2f} | Cost: {core_cost}"
        plt.plot(times, hps, color=color, linewidth=1.5, label=legend_label, drawstyle=drawstyle)
        
    plt.title(f'Yunara DPS Comparison (4-Core Runaan, No Boots, LT+Cut, Target: {dummy_hp_4}/{dummy_armor_4}/{dummy_mr_4})')
    plt.xlabel('Time (s)')
    plt.ylabel('Target HP')
    plt.axhline(y=0, color='black', linestyle='--')
    plt.grid(True, alpha=0.3)
    plt.legend(bbox_to_anchor=(0.5, -0.1), loc='upper center', fontsize=8, ncol=4)
    plt.tight_layout()
    plt.show()

    # === 5코어 시뮬레이션 (루난 버전, 신발 X) (비활성화) ===
    if False:
        print("\n=== 5-Core Simulation (Runaan, No Boots) ===")
        # ... (생략) ...

    # === 4코어 시뮬레이션 (기존) (비활성화) ===
    if False:
        print("\n=== 4-Core Simulation ===")
        # ... (생략) ...

    # === 5코어 시뮬레이션 (기존) (비활성화) ===
    if False:
        print("\n=== 5-Core Simulation ===")
        # ... (생략) ...

    # === 6코어 시뮬레이션 (비활성화) ===
    if False:
        print("\n=== 6-Core Simulation ===")
        # ... (생략) ...
