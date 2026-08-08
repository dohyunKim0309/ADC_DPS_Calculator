"""하위(조합용) 아이템 동작.

스탯/가격은 data/items_data.py 및 ITEM_CATALOG 가 주입한다(여기 리터럴은 레거시 참고값).
현재 전투 효과가 검증된 하위템은 곡궁(RecurveBow)의 적중 시 물리 피해뿐이다.
"""
from adc_sim.item_base import Item


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
