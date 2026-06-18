# items.py

class Item:
    def __init__(self, name, ad=0, ap=0, as_percent=0.0, crit=0.0, add_crit_damage=0.0, armor_pen_percent=0.0,
                 lethality=0, lifesteal=0.0, hp=0, ms=0, ar=0, mr=0, cdr=0, omnivamp=0.0, tenacity=0.0, magic_pen_flat=0):
        self.name = name
        self.cost = 0
        self.stats = {
            'ad': ad, 'ap': ap, 'as': as_percent, 'crit': crit,
            'add_crit_damage': add_crit_damage,
            'armor_pen_percent': armor_pen_percent, 'lethality': lethality,
            'magic_pen_flat': magic_pen_flat,
            'cdr': cdr, # 스킬 가속
            'mana': 0,  # 기본값
        }
        # 구인수 확인용 태그
        self.is_guinsoo = False


    def get_damage_modifier(self, target, champion):
        """
        최종 대미지를 %단위로 증폭시킬 때 사용
        반환값: 0.15 (15% 증폭) / 0.0 (증폭 없음)
        """
        return 0.0

    def on_hit(self, target, champion):
        """
        평타 적중 시 호출. (구인수 발동 시 1회 공격에 2번 호출됨)
        내부 스택을 여기서 관리함.
        """
        return 0, 0, 0, 0 # (Phys, Magic, True_Base, True_Onhit)

    def get_onhit_proc_count(self, champion):
        """
        한 번의 기본 공격에서 온힛 계산을 몇 회 수행할지 반환.
        기본값은 1회.
        """
        return 1
    
    def on_spell_cast(self, champion, time):
        """스킬 사용 시 호출 (주문검 활성화 등)"""
        pass
        
    def on_ult_cast(self, champion, time):
        """궁극기 사용 시 호출"""
        pass

    def on_skill_hit(self, target, champion, time):
        """
        스킬이 챔피언에게 적중했을 때 호출.
        반환: (Phys, Magic, True)
        """
        return 0, 0, 0

    def get_bonus_ad(self, champion):
        """동적 추가 공격력(예: 경탄)"""
        return 0.0

    def get_bonus_mana(self, champion):
        """동적 추가 마나(예: 마나순환 스택/변신 보정)"""
        return 0.0

# ==========================================
# 1. 시작 아이템 및 신발
# ==========================================
class Doranblade(Item):
    def __init__(self):
        # 스펙: AD 10, 체력 80, 피흡 2.5%
        super().__init__('Doran Blade', ad=10, hp=80, omnivamp=0.025)
        self.cost = 450

class DdongShin(Item):
    def __init__(self): 
        super().__init__('ddongshin', ms=25)
        self.cost = 300

class BerserkerGreaves(Item):
    def __init__(self):
        super().__init__('Berserker Greaves', as_percent=0.25, ms=45)
        self.cost = 1100

class IoniaGreaves(Item):
    def __init__(self):
        super().__init__('Ionia Greaves', cdr=10, ms=45)
        self.cost = 900

class BootsofSwiftness(Item):
    def __init__(self):
        super().__init__('Boots of Swiftness', ms=55)
        self.cost = 1000

class Plated_Steelcaps(Item):
    def __init__(self):
        super().__init__('Plated Steelcaps', ms=45, ar=25)
        self.cost = 1200
        # 기본 공격 피해량 10% 감소

class Mercury_Treads(Item):
    def __init__(self):
        super().__init__('Mercury Treads', ms=45, mr=20, tenacity=0.3)
        self.cost = 1250

# ==========================================
# 2. 하위템
# ==========================================
class Pickaxe(Item):
    def __init__(self):
        super().__init__("Pickaxe", ad=25)
        self.cost = 875

class BFSword(Item):
    def __init__(self):
        super().__init__("B.F. Sword", ad=40)
        self.cost = 1300

class ScoutingsSlingshot(Item):
    def __init__(self):
        super().__init__("Scouting's Slingshot", as_percent=0.20)
        self.cost = 600

class LongSword(Item):
    def __init__(self):
        super().__init__("Long Sword", ad=10)
        self.cost = 350

class RecurveBow(Item):
    def __init__(self):
        super().__init__("Recurve Bow", as_percent=0.15)
        self.cost = 700
    
    def on_hit(self, target, champion):
        return 15, 0, 0, 0 # 적중 시 물리 피해 15

class Noonquiver(Item):
    def __init__(self):
        super().__init__("Noonquiver", ad=15, crit=0.20)
        self.cost = 1300

class VampiricScepter(Item):
    def __init__(self):
        super().__init__("Vampiric Scepter", ad=15, lifesteal=0.07)
        self.cost = 900

class HearthboundAxe(Item):
    def __init__(self):
        super().__init__("Hearthbound Axe", ad=20, as_percent=0.20)
        self.cost = 1200

class Dagger(Item):
    def __init__(self):
        super().__init__("Dagger", as_percent=0.10)
        self.cost = 250

class CloakofAgility(Item):
    def __init__(self):
        super().__init__("Cloak of Agility", crit=0.15)
        self.cost = 600


# ==========================================
# 3. 코어 아이템 1 - 공격 속도 및 유틸리티 (공통 가격 2650)
# ==========================================
class PhantomDancer(Item):
    def __init__(self):
        super().__init__("Phantom Dancer", as_percent=0.65, crit=0.25)
        self.cost = 2650
        # 이동속도, 유체화는 DPS 수치에 직접 영향 X


class RunaansHurricane(Item):
    def __init__(self):
        super().__init__("Runaan's Hurricane", as_percent=0.40, crit=0.25)
        self.cost = 2650

    def on_hit(self, target, champion):
        # 단일 대상 DPS 측정 시에는 추가 대미지 없음.
        # 다수 타겟 시뮬레이션이라면 로직 추가 필요.
        # * 루난 자체에는 온힛 대미지가 없고 탄환에만 있음.
        # 여기서는 0, 0 반환이 맞음.
        return 0, 0, 0, 0


class RapidFirecannon(Item):
    def __init__(self):
        super().__init__("Rapid Firecannon", as_percent=0.35, crit=0.25)
        self.cost = 2650

    def on_hit(self, target, champion):
        # 충전 상태 구현 필요.
        # 단순화를 위해: 공격 속도 기반으로 대략 5초에 한번 40 마법 피해를 준다고 가정하거나
        # 시뮬레이터가 '이동'을 안 한다면 충전이 매우 느림.
        # 일단 0으로 둠.
        return 0, 0, 0, 0


class NavoriFlickerblade(Item):
    def __init__(self):
        super().__init__("Navori Flickerblade", as_percent=0.40, crit=0.25)
        self.cost = 2650

    def on_hit(self, target, champion):
        # 쿨타임 감소 -> 스킬 사용 빈도 증가 -> DPS 증가
        # 평타 시뮬레이션에서는 구현이 어렵지만,
        # 루시안/이즈리얼 같은 경우 스킬 쿨타임 변수에 영향을 줌
        return 0, 0, 0, 0


# ==========================================
# 4. 코어 아이템 2 - dps/치명타 아이템
# ==========================================
class StatikkShiv(Item):
    def __init__(self):
        super().__init__("Statikk Shiv", ad=45, ap=45, as_percent=0.30)
        self.cooldown_timer = 0
        self.cost = 3000

    def on_hit(self, target, champion):
        # 8초 내 첫 3회 공격 시 60 마법 피해.
        # 시뮬레이션 상 8초에 한 번 세트가 돈다고 가정?
        # 복잡하므로 단순하게 '첫 타격'에만 60 데미지 주고
        # 이후 쿨타임 로직은 시뮬레이터 엔진 레벨에서 다루는 게 좋음.
        return 0, 0, 0, 0


class Stormrazor(Item):
    def __init__(self):
        # 스펙: AD 50, AS 20%, 치명타 25%
        super().__init__("Stormrazor", ad=50, as_percent=0.20, crit=0.25)
        self.cost = 3200


class BladeOfRuinedKing(Item):
    def __init__(self):
        super().__init__("Blade of the Ruined King", ad=40, as_percent=0.25, lifesteal=0.1)
        self.cost = 3200

    def on_hit(self, target, champion):
        # 원거리 챔피언은 적 챔피언의 현재 체력의 6퍼센트에 해당하는 온힛 물리 피해
        return target.current_hp * 0.06, 0, 0, 0


class KrakenSlayer(Item):
    def __init__(self):
        # 스펙: AD 45, AS 40% (25.14 패치 기준)
        super().__init__("Kraken Slayer", ad=45, as_percent=0.40)
        self.stack = 0
        self.cost = 3000

    def on_hit(self, target, champion):
        total_damage = 0.0 # 초기화

        # 1. 스택 쌓기
        stack_increment = 1
        if (
            champion.name == "Yunara"
            and getattr(champion, "q_active", False)
            and champion.target_count >= 2
            and any(item.name == "Runaan's Hurricane" for item in champion.inventory)
        ):
            extra_targets = min(2, champion.target_count - 1)
            stack_increment += extra_targets

        self.stack += stack_increment

        # 2. 3타 발동 조건 확인
        if self.stack >= 3:
            self.stack = 0  # 스택 초기화

            # --- [A] 기본 피해량 계산 (8~18레벨 선형 보간) ---
            lvl = champion.level
            min_dmg = 120
            max_dmg = 160

            if lvl < 8:
                base_dmg = min_dmg
            elif lvl >= 18:
                base_dmg = max_dmg
            else:
                # 8레벨일 때 0, 18레벨일 때 1이 되는 비율
                ratio = (lvl - 8) / (18 - 8)
                base_dmg = min_dmg + (ratio * (max_dmg - min_dmg))

            # --- [B] 잃은 체력 비례 증폭 (남은 체력 30%에서 최대) ---
            # 1. 잃은 체력 비율 계산
            current_hp_ratio = target.current_hp / target.max_hp
            missing_hp_ratio = 1.0 - current_hp_ratio

            # 2. 증폭 계수 계산
            # 목표: 잃은 체력이 0.7(70%)일 때 추가 계수가 0.75(75%)가 되어야 함
            saturation_point = 0.7  # 70% 잃었을 때 (남은 체력 30%)
            max_bonus = 0.75  # 최대 75% 증폭

            if missing_hp_ratio >= saturation_point:
                # 체력이 30% 이하로 남았으면 최대 대미지 (1.75배)
                damage_multiplier = 1.0 + max_bonus
            else:
                # 0 ~ 70% 구간 선형 보간
                # 식: 1 + (현재잃은비율 / 0.7 * 0.75)
                current_bonus = (missing_hp_ratio / saturation_point) * max_bonus
                damage_multiplier = 1.0 + current_bonus

            # 최종 대미지 산출
            total_damage = base_dmg * damage_multiplier

        if total_damage > 0:
            return total_damage, 0, 0, 0  # (물리 피해, 마법 피해, 고정 평타, 고정 온힛)

        return 0, 0, 0, 0


class GuinsoosRageblade(Item):
    def __init__(self):
        # AD 30, AP 30, AS 25%
        super().__init__("Guinsoo's Rageblade", ad=30, ap=30, as_percent=0.25)
        self.is_guinsoo = True  # 핵심 플래그
        self.stack = 0
        self.full_stack_attack_counter = 0
        self.cost = 3000

    def on_hit(self, target, champion):
        # 기본 30 마법 피해
        base_magic = 30

        # 중첩당 공속 8% 증가 (최대 4회=32% 가정)
        if self.stack < 4:
            self.stack += 1
            champion.bonus_as_percent += 0.08
            # 공속 재계산 필요하므로 로그만 남김 (실제 적용은 다음 틱부터)

        return 0, base_magic, 0, 0

    def get_onhit_proc_count(self, champion):
        """
        풀스택 이후 3타마다 온힛 2회 처리.
        - 스택이 4 미만이면 일반 1회.
        - 풀스택 상태에서 공격 카운트를 누적해 3번째마다 2회.
        """
        if self.stack < 4:
            self.full_stack_attack_counter = 0
            return 1

        self.full_stack_attack_counter += 1
        if self.full_stack_attack_counter % 3 == 0:
            return 2
        return 1


class HextechScopeC44(Item):
    def __init__(self):
        # AD 50, Crit 25%, 가격 2800
        # 버프 적용: AD 50 -> 55
        super().__init__("Hextech Scope C44", ad=55, crit=0.25)
        self.cost = 2800

        # 비전 조준 활성화 여부 (필요 시 시뮬레이션 외부에서 True로 변경)
        self.is_buff_active = False

    def get_damage_modifier(self, target, champion):
        """
        확대: 적과의 거리(champion.range)에 따라 최대 10% 증가된 피해
        - 700 거리일 때 최대 (10%)
        - 버프 적용: 600 거리일 때 최대 (10%)
        """

        # 1. 현재 사거리 가져오기
        # (비전 조준 효과 등으로 champion.range가 이미 변해있다고 가정하거나, 여기서 더해서 계산)
        current_range = champion.range

        # 만약 아이템 자체적으로 사거리를 늘려주는 효과를 여기서 반영하고 싶다면:
        if self.is_buff_active:
            current_range += 100

        # 2. 증폭률 계산 (최대 600 거리 기준)
        # 거리 600 이상이면 1.0, 그 미만이면 (거리/600) 비율
        ratio = min(1.0, current_range / 600.0)

        # 3. 최대 10% 증폭
        modifier = ratio * 0.10

        return modifier

    # 시뮬레이션 중 킬/어시 발생 시 호출하여 사거리를 늘리고 싶을 때 사용
    def activate_vision_focus(self, champion):
        self.is_buff_active = True


class TheCollector(Item):
    def __init__(self):
        super().__init__("The Collector", ad=50, crit=0.25, lethality=10)
        self.execute_threshold = 0.05  # 체력 5% 미만 처형
        self.cost = 3000


class EssenceReaver(Item):
    def __init__(self):
        # AD 50, 스킬 가속 20, 치명타 25%
        super().__init__("Essence Reaver", ad=50, crit=0.25, cdr=20)
        self.cost = 3050
        self.is_spellblade_active = False
        self.spellblade_cd = 1.5
        self.last_activation_time = -999.0  # 마지막 활성화 시간
        self.last_spellblade_damage = 0.0

    def on_spell_cast(self, champion, time):
        # 주문검 내부 쿨: 마지막 활성화 시점 기준 1.5초
        if time >= self.last_activation_time + self.spellblade_cd:
            self.is_spellblade_active = True
            self.last_activation_time = time

    def on_hit(self, target, champion):
        self.last_spellblade_damage = 0.0
        # 주문검 효과 발동 (활성 상태에서 다음 기본 공격 1회)
        if self.is_spellblade_active:
            # 대미지: 기본 공격력 125% + 치명타 확률 * 50
            # 기본 공격력 = base_ad + ad_growth*(level-1) = total_ad - bonus_ad
            base_attack_ad = champion.total_ad - champion.bonus_ad
            damage = (base_attack_ad * 1.25) + (champion.crit_chance * 50)
            self.last_spellblade_damage = damage
            self.is_spellblade_active = False # 소모
            return damage, 0, 0, 0 # 물리 피해
            
        return 0, 0, 0, 0


class TrinityForce(Item):
    def __init__(self):
        # AD 36, AS 30%, HP 333, AH 15
        super().__init__("Trinity Force", ad=36, as_percent=0.30, hp=333, cdr=15)
        self.cost = 3333

        # 주문검
        self.is_spellblade_active = False
        self.last_spellblade_damage = 0.0
        self.spellblade_cd = 1.5
        self.last_activation_time = -999.0

        # 가속(이동속도 +20, 2초) - 현재 엔진에서는 이동속도 비전투 영향 없음
        self.haste_buff_end_time = 0.0

    def on_spell_cast(self, champion, time):
        # 주문검 내부 쿨: 마지막 활성화 시점 기준 1.5초
        if time >= self.last_activation_time + self.spellblade_cd:
            self.is_spellblade_active = True
            self.last_activation_time = time

    def on_hit(self, target, champion):
        self.last_spellblade_damage = 0.0
        current_time = getattr(champion, "_combat_time", 0.0)

        # 가속 버프 갱신 (엔진 내 이동속도 계산에는 아직 미연동)
        self.haste_buff_end_time = current_time + 2.0

        # 주문검: 다음 기본 공격에 기본 공격력 * 2 물리 피해
        if self.is_spellblade_active:
            base_attack_ad = champion.total_ad - champion.bonus_ad
            damage = base_attack_ad * 2.0
            self.last_spellblade_damage = damage
            self.is_spellblade_active = False
            return damage, 0, 0, 0

        return 0, 0, 0, 0


class Manamune(Item):
    def __init__(self):
        # AD 35, Mana 500, AH 15
        super().__init__("Manamune", ad=35, cdr=15)
        self.stats["mana"] = 500
        self.cost = 2900

        # 마나순환
        self.max_mana_stack = 360
        self.mana_stacked = 0.0
        self.charge_cd = 8.0
        self.max_charges = 4
        self.charges = 4
        self.next_charge_time = None

        # 진화
        self.is_muramana = False

    def _recover_charges(self, time):
        if self.next_charge_time is None:
            return
        while self.charges < self.max_charges and time >= self.next_charge_time:
            self.charges += 1
            if self.charges >= self.max_charges:
                self.next_charge_time = None
            else:
                self.next_charge_time += self.charge_cd

    def _consume_manaflow_charge(self, champion, target):
        time = getattr(champion, "_combat_time", 0.0)
        self._recover_charges(time)
        if self.charges <= 0:
            return

        was_full = (self.charges == self.max_charges)
        self.charges -= 1
        if was_full:
            self.next_charge_time = time + self.charge_cd

        gain = 6.0 if target is not None else 3.0
        if not self.is_muramana:
            self.mana_stacked = min(self.max_mana_stack, self.mana_stacked + gain)
            if self.mana_stacked >= self.max_mana_stack:
                self.is_muramana = True
                self.name = "Muramana"

    def get_bonus_mana(self, champion):
        # add_item으로 이미 500 마나가 더해짐.
        # 마나무네: +스택(최대 360), 무라마나: 총 1000 마나가 되도록 +500 보정
        if self.is_muramana:
            return 500.0
        return self.mana_stacked

    def get_bonus_ad(self, champion):
        # 경탄: 총 마나의 2% 추가 AD
        return 0.02 * champion.total_mana

    def on_hit(self, target, champion):
        self._consume_manaflow_charge(champion, target)

        if self.is_muramana:
            # 충격(평타): 총 마나의 1.2% 추가 물리 피해
            bonus_phys = 0.012 * champion.total_mana
            return bonus_phys, 0, 0, 0
        return 0, 0, 0, 0

    def on_skill_hit(self, target, champion, time):
        self._consume_manaflow_charge(champion, target)

        if self.is_muramana:
            # 충격(스킬): 총 마나의 3% 추가 물리 피해
            bonus_phys = 0.03 * champion.total_mana
            return bonus_phys, 0, 0
        return 0, 0, 0


class DemonHunterCrossbow(Item):
    def __init__(self):
        # 공속 45%, 치명타 25%, 이속 4%, 궁극기 가속 30
        super().__init__("Demon Hunter's Crossbow", as_percent=0.45, crit=0.25, ms=0.04, cdr=30) 
        self.cost = 2650
        self.buff_active = False
        self.buff_end_time = 0.0
        self.buff_stacks = 0 # 남은 강화 평타 횟수
        self.buff_as_applied = False
        self.last_ult_time = -999.0 # 궁극기 사용 시간 (쿨타임 45초)

    def on_ult_cast(self, champion, time):
        # 궁극기 사용 시 폭격 개시 활성화 (쿨타임 45초)
        if time >= self.last_ult_time + 45.0:
            self.buff_active = True
            self.buff_end_time = time + 8.0 # 8초 지속
            self.buff_stacks = 3 # 3회
            self.last_ult_time = time
            
            # 공속 50% 증가 (Champion에 직접 적용)
            champion.bonus_as_percent += 0.50
            self.buff_as_applied = True

    def on_hit(self, target, champion):
        # 폭격 개시 효과 적용 (기댓값 계산)
        phys_dmg = 0
        true_dmg = 0

        if self.buff_active and self.buff_stacks > 0:
            self.buff_stacks -= 1
            
            # 기댓값 계산
            crit_chance = champion.crit_chance
            crit_dmg_mod = champion.crit_damage_modifier
            ad = champion.total_ad

            # 1. 치명타가 터지지 않을 확률 (1 - crit_chance) -> 강제 치명타 (80% 효율)
            # 추가되는 물리 피해량 = (치명타 대미지 - 일반 대미지) * 0.8
            # 일반 대미지 = ad
            # 치명타 대미지 = ad * crit_dmg_mod
            # 추가분 = ad * (crit_dmg_mod - 1) * 0.8
            phys_bonus_from_non_crit = (1 - crit_chance) * ad * (crit_dmg_mod - 1) * 0.8
            phys_dmg += phys_bonus_from_non_crit
            
            # 2. 치명타가 터질 확률 (crit_chance) -> 15% 추가 고정 피해
            true_bonus_from_crit = crit_chance * ad * 0.15
            true_dmg += true_bonus_from_crit
            
            # 버프 종료 시 공속 롤백
            if self.buff_stacks <= 0:
                self.buff_active = False
                if self.buff_as_applied:
                    champion.bonus_as_percent -= 0.50
                    self.buff_as_applied = False

        return phys_dmg, 0, true_dmg, 0 # (물리, 마법, 고정 평타, 고정 온힛)


class YunTalWildarrows(Item):
    def __init__(self, crit=0.25):
        # AD 50, AS 40%, Crit 25% (기본값)
        # crit 인자를 통해 치명타 확률 조절 가능 (10% 등)
        super().__init__("Yun Tal Wildarrows", ad=50, as_percent=0.40, crit=crit)
        self.active_buff = False
        self.cost = 3100

    def on_hit(self, target, champion):
        # 효과 (광풍): 적 챔피언 공격 시 공속 30% 증가
        # 시뮬레이션 단순화를 위해 첫 타격 이후 항상 버프가 켜진다고 가정
        if not self.active_buff:
            champion.bonus_as_percent += 0.30
            self.active_buff = True
            # print(f"[Item] {self.name}: Attack Speed buff activated (+30%)")

        # 효과 (연습이 치명타를 낳는다): 치명타 확률 영구 증가 (최대 25%)
        # 복잡하므로 여기서는 생략하거나, 시간이 지남에 따라 crit을 올려주는 로직 필요
        return 0, 0, 0, 0


class InfinityEdge(Item):
    def __init__(self):
        super().__init__("Infinity Edge", ad=75, crit=0.25, add_crit_damage=0.3)
        self.cost = 3500


class LordDominiksRegards(Item):
    def __init__(self):
        super().__init__("Lord Dominik's Regards", ad=35, armor_pen_percent=0.35, crit=0.25)
        self.cost = 3300

    def get_damage_modifier(self, target, champion):
        # 거인 학살자: 대상의 추가 체력에 비례해 최대 15% 추가 피해
        # 조건: 추가 체력 0일 때 0%, 1500 이상일 때 15%

        # 1. 타겟에게 bonus_hp 속성이 없으면 0 반환 (안전장치)
        if not hasattr(target, 'bonus_hp'):
            return 0.0

        extra_hp = target.bonus_hp

        # 2. 계산 로직 (선형 비례)
        if extra_hp <= 0:
            return 0.0
        elif extra_hp >= 1500:
            return 0.15  # 최대 15%
        else:
            # 1500일 때 0.15이므로 => (현재추가체력 / 1500) * 0.15
            # 즉, 현재추가체력 / 10000 과 같음
            return (extra_hp / 1500) * 0.15


class MortalReminder(Item):
    def __init__(self):
        super().__init__("Mortal Reminder", ad=35, armor_pen_percent=0.30, crit=0.25)
        self.cost = 3000


class Terminus(Item):
    def __init__(self):
        # 스펙: AD 30, AS 35%
        super().__init__("Terminus", ad=30, as_percent=0.35)
        self.cost = 3000

        # 상태 관리 변수
        self.light_stacks = 0  # 빛 스택 (방/마저, 최대 3)
        self.dark_stacks = 0  # 어둠 스택 (관통력, 최대 3)
        self.is_light_turn = True  # True면 빛, False면 어둠 차례 (보통 빛부터 시작)

    def on_hit(self, target, champion):
        # 1. 적중 시 30 마법 피해 (고정)
        magic_dmg = 30

        # 2. 빛(방어/마저) 증가량 계산 (레벨 비례)
        # 구간: 1~6(+6), 7~11(+7), 12~18(+8)
        resist_gain = 0
        if champion.level <= 6:
            resist_gain = 6
        elif champion.level <= 11:
            resist_gain = 7
        else:
            resist_gain = 8

        # 3. 빛과 어둠 번갈아 적용
        if self.is_light_turn:
            # --- [빛] 차례: 방어력/마법 저항력 증가 ---
            if self.light_stacks < 3:  # 최대 3스택 제한
                self.light_stacks += 1

                if hasattr(champion, 'af'):
                    champion.ar += resist_gain
                if hasattr(champion, 'mr'):
                    champion.mr += resist_gain

        else:
            # --- [어둠] 차례: 방어구/마법 관통력 증가 ---
            if self.dark_stacks < 3:  # 최대 3스택 제한
                self.dark_stacks += 1
                if hasattr(champion, 'armor_pen_percent'):
                    champion.armor_pen_percent += 0.10
                if hasattr(champion, 'magic_pen_percent'):
                    champion.magic_pen_percent += 0.10

        # 4. 턴 교체 (빛 -> 어둠 -> 빛 ...)
        self.is_light_turn = not self.is_light_turn

        return 0, magic_dmg, 0, 0


# ==========================================
# 5. 코어 아이템 3 - 생존 및 유지력
# ==========================================
class WitsEnd(Item):
    def __init__(self):
        super().__init__("Wit's End", as_percent=0.5, mr=45, tenacity=0.2)
        self.cost = 2800

    def on_hit(self, target, champion):
        # 적중 시 45의 온힛 마법 피해
        return 0, 45, 0, 0


class ExpHexplate(Item):
    def __init__(self):
        super().__init__("Experimental Hexplate", ad=40, as_percent=0.2, hp=450)
        self.cost=3000
        self.ult_cdr=30
        # 궁극기 사용후 8초 동안 50% 공속, 20% 이속 얻음(재사용 대기시간 30초), 구현 아직 안함!


class Bloodthirster(Item):
    def __init__(self):
        super().__init__("Bloodthirster", ad=80, lifesteal=0.15)
        self.cost = 3400
        # 생명력 흡수는 DPS 영향 X


class ImmortalShieldbow(Item):
    def __init__(self):
        super().__init__("Immortal Shieldbow", ad=55, crit=0.25)
        self.cost = 3000


class MercurialScimitar(Item):
    def __init__(self):
        super().__init__("Mercurial Scimitar", ad=50)
        self.cost = 3200
        # 마저 35는 방어 스탯이므로 제외, 공속/이속 사용효과 있음


class GuardianAngel(Item):
    def __init__(self):
        super().__init__("Guardian Angel", ad=55)
        self.cost = 3200

class SerpentsFang(Item):
    def __init__(self):
        super().__init__("Serpent's Fang", ad=55, lethality=15)
        self.cost = 2500

class NashorsTooth(Item):
    def __init__(self):
        super().__init__("Nashor's Tooth", ap=80, as_percent=0.50, cdr=15)
        self.cost = 2900

    def on_hit(self, target, champion):
        # 적중 시 15 + 0.15 AP 마법 피해
        magic_dmg = 15 + (0.15 * champion.total_ap)
        return 0, magic_dmg, 0, 0

class RabadonsDeathcap(Item):
    def __init__(self):
        super().__init__("Rabadon's Deathcap", ap=130)
        self.cost = 3500
        # 패시브: 총 주문력 30% 증가 (Champion 클래스에서 처리)

class Shadowflame(Item):
    def __init__(self):
        super().__init__("Shadowflame", ap=110, magic_pen_flat=15)
        self.cost = 3200
        # 패시브: 체력 40% 이하 적에게 마법/고정 피해 20% 증가 (Champion 클래스에서 처리)

class HextechGunblade(Item):
    def __init__(self):
        super().__init__("Hextech Gunblade", ad=40, ap=80, omnivamp=0.10)
        self.cost = 3000
