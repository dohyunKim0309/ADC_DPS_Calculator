"""모든 아이템 동작 클래스가 공유하는 기본 인터페이스."""

class Item:
    """정적 능력치와 전투 훅을 보관하는 범용 아이템."""

    def __init__(self, name, ad=0, ap=0, as_percent=0.0, crit=0.0, add_crit_damage=0.0, armor_pen_percent=0.0,
                 lethality=0, lifesteal=0.0, hp=0, ms=0, ar=0, mr=0, cdr=0, omnivamp=0.0, tenacity=0.0, magic_pen_flat=0):
        """아이템 이름과 정적 능력치를 초기화한다.

        퍼센트 능력치는 1.0을 100%로 표현하며, 반환값은 없다.
        """
        self.name = name
        self.cost = 0
        self.stats = {
            'ad': ad, 'ap': ap, 'as': as_percent, 'crit': crit,
            'add_crit_damage': add_crit_damage,
            'armor_pen_percent': armor_pen_percent, 'lethality': lethality,
            'magic_pen_flat': magic_pen_flat,
            'cdr': cdr, # 스킬 가속
            'mana': 0,  # 기본값
            'lifesteal': lifesteal, 'omnivamp': omnivamp,
            'hp': hp, 'ms': ms, 'armor': ar, 'mr': mr,
            'tenacity': tenacity,
        }
        # 구인수 확인용 태그
        self.is_guinsoo = False


    def get_bonus_ehp(self, champion, damage_type="physical"):
        """유효 체력에 더해질 '추가 체력 상당분'을 반환한다(기본 0).

        방어막·부활처럼 스탯이 아닌 방어 패시브를 EHP 로 환산할 때 쓴다.
        반환값은 체력 단위이며, 저항 배수는 호출부(champion.effective_hp)가 곱한다.

        damage_type: "physical" | "magic" | "true". 멜모셔스 생명선처럼 특정 속성만
        흡수하는 보호막은 해당 축에서만 값을 돌려주면 된다. 전 속성 보호막·부활은
        인자를 무시하고 같은 값을 반환한다.
        """
        return 0.0

    def get_conditional_omnivamp(self, champion):
        """조건부로 얻는 '모든 피해 흡혈' 비율(기본 0).

        멜모셔스 생명선처럼 발동 후에야 붙는 흡혈을 지속력 집계에 태울 때 쓴다.
        발동 조건은 모델링하지 않으므로 이 값은 교전 기준 상한선이다.
        """
        return 0.0

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

    def get_extra_onhit_applications(self, champion):
        """온힛 효과를 '추가로' 몇 회 더 적용할지(가산). 주문검류(황혼과 새벽)용.
        proc_count(max)와 달리 합산되어 구인수(2회)와 겹쳐도 시너지가 유지된다. 기본 0회.
        """
        return 0

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


