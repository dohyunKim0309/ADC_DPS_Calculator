"""시작 아이템·신발 등 유틸리티 아이템 동작.

스탯/가격은 data/items_data.py 가 주입한다(여기 리터럴은 레거시 참고값).
"""
from adc_sim.item_base import Item


# ==========================================
# 1. 시작 아이템 및 신발
# ==========================================
class Doranblade(Item):
    def __init__(self):
        # 스펙: AD 10, 체력 80, 피흡 2.5%
        super().__init__('Doran Blade', ad=10, hp=80, omnivamp=0.025)
        self.cost = 450


class DoransBow(Item):
    def __init__(self):
        # 스펙: AD 8, 공속 15%, 옴니뱀프 1.5% (옴니뱀프는 엔진 미사용)
        # 스탯/가격의 단일 출처는 data/items_data.py
        super().__init__("Doran's Bow", ad=8, as_percent=0.15, omnivamp=0.015)
        self.cost = 400


class DdongShin(Item):
    def __init__(self):
        super().__init__('ddongshin', ms=25)
        self.cost = 300


class BerserkerGreaves(Item):
    def __init__(self):
        super().__init__('Berserker Greaves', as_percent=0.25, ms=45)
        self.cost = 1100


class GluttonousGreaves(Item):
    def __init__(self):
        # 스펙: 이속 45, 옴니뱀프 4% (둘 다 엔진 미사용 → DPS 기여 0)
        # 처치 시 옴니뱀프 스택 패시브는 비전투/단일대상 DPS 모델과 무관해 미구현
        super().__init__('Gluttonous Greaves', ms=45, omnivamp=0.04)
        self.cost = 1000


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
