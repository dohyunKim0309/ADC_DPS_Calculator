"""기본·서사급 재료 아이템의 선택적 런타임 동작.

패시브가 없는 재료는 레지스트리가 Item으로 직접 생성할 수 있고, 이 모듈에는
별도 전투 훅이 필요한 클래스만 남긴다. 현재 클래스들은 기존 구현을 보존한다.
"""

from adc_sim.item_base import Item


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


