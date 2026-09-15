"""시작 아이템·장화·소모품의 선택적 런타임 동작.

수치의 단일 출처는 adc_sim.data.items_data 이며, 이 모듈에는 전투 훅이 필요한
아이템 클래스만 둔다.
"""

from adc_sim.item_base import Item


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



# ── Azir(미드 AP) 추가분 — 2026-08-27. 스탯/가격의 단일 출처는 data/items_data.py ──────────────
class DoransRing(Item):
    """도란의 반지. AP18/체력90 + 흡수(전투 중 초당 2 마나 = MP5 10, items_data 'mana_regen').
    도움의 손길(미니언 추가 피해)은 더미 시뮬과 무관 → 미모델."""
    def __init__(self):
        super().__init__("Doran's Ring", ap=18, hp=90)
        self.cost = 400


class SorcererShoes(Item):
    """마법사의 신발: 고정 마관 12 / 이속 45."""
    def __init__(self):
        super().__init__("Sorcerer's Shoes", ms=45, magic_pen_flat=12)
        self.cost = 1100


class SpellslingerShoes(Item):
    """주문투척자의 신발(3티어, 미드 퀘스트 무료 승급): 고정 마관 20 + %마관 8% / 이속 45.
    %마관은 items_data 'magic_pen_percent' 로 주입 → champion.add_item 이 곱연산 합성."""
    def __init__(self):
        super().__init__("Spellslinger's Shoes", ms=45, magic_pen_flat=20)
        self.cost = 1100


class CrimsonLucidity(Item):
    """핏빛 명석함(3티어): 스킬가속 20 / 이속 45. 녹서스의 가속(이속)은 DPS 무관 → 미모델."""
    def __init__(self):
        super().__init__("Crimson Lucidity", cdr=20, ms=45)
        self.cost = 900


class GunmetalGreaves(Item):
    """건메탈 군화(3티어): 공속 45% / 생명력 흡수 5% / 이속 45."""
    def __init__(self):
        super().__init__("Gunmetal Greaves", as_percent=0.45, ms=45, lifesteal=0.05)
        self.cost = 1100


class Swiftmarch(Item):
    """신속행진(3티어): 이속 65 + 녹서스의 열광(전체 이속의 5% 만큼 적응형 능력치).
    적응형은 아지르=AP(1:1). 이속 = 기본 330 + 신발 65 (다른 이속 아이템 미모델) → AP ≈ 19.75.
    챔피언이 get_bonus_ap 훅을 읽어야 반영된다(현재 Azir.total_ap 만 읽음). [H-AZIR-SWIFT-1]"""
    ADAPTIVE_RATIO = 0.05

    def __init__(self):
        super().__init__("Swiftmarch", ms=65)
        self.cost = 1000

    def get_bonus_ap(self, champion):
        base_ms = getattr(champion, "base_move_speed", 330.0)
        return self.ADAPTIVE_RATIO * (base_ms + self.stats.get("ms", 0))
