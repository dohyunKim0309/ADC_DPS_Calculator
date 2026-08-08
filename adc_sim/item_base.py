"""아이템 동작의 베이스 클래스.

스탯·가격·이름의 단일 출처는 `adc_sim/data/items_data.py` 이고, 인스턴스 생성은
`adc_sim/data/items_registry.create_item_from_key` 가 담당한다. 여기(그리고 역할별
동작 모듈)에 남은 스탯 리터럴은 레지스트리의 `_apply_data` 가 런타임에 덮어쓴다.
"""


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
