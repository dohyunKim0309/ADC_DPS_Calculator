class Rune:
    def __init__(self, name):
        self.name = name

    def on_attack(self, champion):
        """공격 시 호출 (스택 쌓기 등)"""
        pass

    def get_bonus_as(self):
        """추가 공격 속도 반환 (단위: 1.0 = 100%)"""
        return 0.0

    def get_on_hit_damage(self, target, champion):
        """적중 시 추가 피해 반환 (물리, 마법)"""
        return 0, 0


class LethalTempo(Rune):
    def __init__(self):
        super().__init__("Lethal Tempo")
        self.stacks = 0
        self.max_stacks = 6
        self.stack_as = 0.048  # 스택당 4.8% (0.048)
        self.ranged_damage_penalty = 2 / 3  # 원거리 66% 피해

    def on_attack(self, champion):
        # 공격 시 스택 증가 (최대 6)
        if self.stacks < self.max_stacks:
            self.stacks += 1

    def get_bonus_as(self):
        # 현재 스택에 따른 추가 공속 반환
        return self.stacks * self.stack_as

    def get_on_hit_damage(self, target, champion):
        # 풀스택이 아니면 대미지 없음
        if self.stacks < self.max_stacks:
            return 0, 0

        # === 적응형 피해 계산 ===
        # 1. 기본 피해: 레벨 비례 9 ~ 30
        # 선형 보간: 9 + (21 * (level - 1) / 17)
        lvl = champion.level
        base_dmg = 9 + (21 * (lvl - 1) / 17)

        # 2. 계수: 1 + 100% 추가 공격 속도
        # 챔피언의 총 추가 공격 속도(%)를 가져와야 함
        # (아이템 + 성장 + 룬 포함)
        total_bonus_as = champion.get_total_bonus_as_percent()
        scaling = 1.0 + total_bonus_as

        # 3. 원거리 페널티 적용
        # (기본 + 계수) * 2/3
        damage = base_dmg * scaling * self.ranged_damage_penalty

        # 적응형 피해: ADC는 보통 물리 피해로 적용
        return damage, 0
