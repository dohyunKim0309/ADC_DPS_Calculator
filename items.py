# items.py

class Item:
    def __init__(self, name, ad=0, as_percent=0.0, crit=0.0, add_crit_damage=0.0, armor_pen_percent=0.0,
                 lethality=0, lifesteal=0.0, hp=0, ms=0, ar=0, mr=0, cdr=0, omnivamp=0.0, tenacity=0.0):
        self.name = name
        self.cost = 0
        self.stats = {
            'ad': ad, 'as': as_percent, 'crit': crit,
            'armor_pen_percent': armor_pen_percent, 'lethality': lethality
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
        return 0, 0 # (Phys, Magic)

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
        super().__init__('Berserker Greaves', as_percent=25, ms=45)
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
        return 0, 0


class RapidFirecannon(Item):
    def __init__(self):
        super().__init__("Rapid Firecannon", as_percent=0.35, crit=0.25)
        self.cost = 2650

    def on_hit(self, target, champion):
        # 충전 상태 구현 필요.
        # 단순화를 위해: 공격 속도 기반으로 대략 5초에 한번 40 마법 피해를 준다고 가정하거나
        # 시뮬레이터가 '이동'을 안 한다면 충전이 매우 느림.
        # 일단 0으로 둠.
        return 0, 0


class NavoriFlickerblade(Item):
    def __init__(self):
        super().__init__("Navori Flickerblade", as_percent=0.40, crit=0.25)
        self.cost = 2650

    def on_hit(self, target, champion):
        # 쿨타임 감소 -> 스킬 사용 빈도 증가 -> DPS 증가
        # 평타 시뮬레이션에서는 구현이 어렵지만,
        # 루시안/이즈리얼 같은 경우 스킬 쿨타임 변수에 영향을 줌
        return 0, 0


# ==========================================
# 4. 코어 아이템 2 - dps/치명타 아이템
# ==========================================
class StatikkShiv(Item):
    def __init__(self):
        super().__init__("Statikk Shiv", ad=45, as_percent=0.30)
        self.cooldown_timer = 0
        self.cost = 2700

    def on_hit(self, target, champion):
        # 8초 내 첫 3회 공격 시 60 마법 피해.
        # 시뮬레이션 상 8초에 한 번 세트가 돈다고 가정?
        # 복잡하므로 단순하게 '첫 타격'에만 60 데미지 주고
        # 이후 쿨타임 로직은 시뮬레이터 엔진 레벨에서 다루는 게 좋음.
        return 0, 0


class BladeOfRuinedKing(Item):
    def __init__(self):
        super().__init__("Blade of the Ruined King", ad=40, as_percent=0.25, lifesteal=0.1)
        self.cost = 3200

    def on_hit(self, target, champion):
        # 원거리 챔피언은 적 챔피언의 현재 체력의 6퍼센트에 해당하는 온힛 물리 피해
        return target.current_hp * 0.06, 0


class KrakenSlayer(Item):
    def __init__(self):
        # 스펙: AD 45, AS 40% (25.14 패치 기준)
        super().__init__("Kraken Slayer", ad=45, as_percent=0.40)
        self.stack = 0
        self.cost = 3000

    def on_hit(self, target, champion):
        # 1. 스택 쌓기
        self.stack += 1

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
            final_damage = base_dmg * damage_multiplier

            return final_damage, 0  # (물리 피해, 마법 피해)

        return 0, 0


class GuinsoosRageblade(Item):
    def __init__(self):
        # AD 30, AP 30, AS 25%
        super().__init__("Guinsoo's Rageblade", ad=30, as_percent=0.25)
        self.is_guinsoo = True  # 핵심 플래그
        self.stack = 0
        self.cost = 3000

    def on_hit(self, target, champion):
        # 기본 30 마법 피해
        base_magic = 30

        # 중첩당 공속 8% 증가 (최대 4회=32% 가정)
        if self.stack < 4:
            self.stack += 1
            champion.bonus_as_percent += 0.08
            # 공속 재계산 필요하므로 로그만 남김 (실제 적용은 다음 틱부터)

        return 0, base_magic


class TheCollector(Item):
    def __init__(self):
        super().__init__("The Collector", ad=50, crit=0.25, lethality=10)
        self.execute_threshold = 0.05  # 체력 5% 미만 처형
        self.cost = 3000


# class EssenceReaver(Item):
#     def __init__(self):
#         # 스킬 가속은 DPS 시뮬레이션에서 평타 위주라면 제외하거나 쿨타임 감소로 구현
#         super().__init__("Essence Reaver", ad=60, crit=0.25)
#         self.cost = 2900
#
#     def on_hit(self, target, champion):
#         # 마나 회복은 대미지에 직접 영향 없으므로 패스
#         # 26.01 패치 시 주문검 효과(추가 피해) 생기면 여기에 로직 추가 필요
#         return 0, 0


class YunTalWildarrows(Item):
    def __init__(self):
        # AD 50, AS 40%, Crit 25%
        super().__init__("Yun Tal Wildarrows", ad=50, as_percent=0.40, crit=0.25)
        self.active_buff = False
        self.cost = 3100

    def on_hit(self, target, champion):
        # 효과 (광풍): 적 챔피언 공격 시 공속 30% 증가
        # 시뮬레이션 단순화를 위해 첫 타격 이후 항상 버프가 켜진다고 가정
        if not self.active_buff:
            champion.bonus_as_percent += 0.30
            self.active_buff = True
            print(f"[Item] {self.name}: Attack Speed buff activated (+30%)")

        # 효과 (연습이 치명타를 낳는다): 치명타 확률 영구 증가 (최대 25%)
        # 복잡하므로 여기서는 생략하거나, 시간이 지남에 따라 crit을 올려주는 로직 필요
        return 0, 0


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
        super().__init__("Terminus", ad=30, as_percent=0.35)
        self.stack = 0
        self.cost = 3000

    def on_hit(self, target, champion):
        # 적중 시 30 마법 피해
        magic_dmg = 30

        # 공격 시 방/마저 or 관통력 중첩
        if self.stack < 7:  # 가상의 최대 스택
            if self.stack % 2 == 1:
                # 8씩 방마저가 증가하는 것으로 했으나, 사실 챔피언 레벨이 1~6이면 6만큼, 7~11이면 7만큼, 12~18이면 8만큼씩 방마저가 증가함.
                champion.ar += 8
                champion.mr += 8
            else:
                champion.armor_pen_percent += 0.1
                champion.magic_pen_percent += 0.1
            self.stack += 1

        return 0, magic_dmg


# ==========================================
# 5. 코어 아이템 3 - 생존 및 유지력
# ==========================================
class WitsEnd(Item):
    def __init__(self):
        super().__init__("Wit's End", as_percent=0.5, mr=45, tenacity=0.2)
        self.cost = 2800

    def on_hit(self, target, champion):
        # 적중 시 45의 온힛 마법 피해
        return 0, 45


class ExpHexplate(Item):
    def __init__(self):
        super().__init__("Experimental Hexplate", ad=40, as_percent=0.2, hp=450)
        self.cost=3000
        self.ult_cdr=30
        # 궁극기 사용후 8초 동안 50% 공속, 20% 이속 얻음(재사용 대기시간 30초), 구현 아직 안함!


class Bloodthirster(Item):
    def __init__(self):
        super().__init__("Bloodthirster", ad=80)
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