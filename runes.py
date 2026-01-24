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
    
    def get_damage_modifier(self, target, champion):
        """최종 대미지 증폭 비율 반환 (예: 0.08 = 8% 증가)"""
        return 0.0


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


class PressTheAttack(Rune):
    def __init__(self):
        super().__init__("Press the Attack")
        self.stacks = 0
        self.active = False # 3타 터진 후 활성화 상태

    def on_attack(self, champion):
        # 3타 스택 쌓기
        if not self.active:
            self.stacks += 1
            if self.stacks >= 3:
                self.active = True
                # 3타 터질 때 추가 피해는 get_on_hit_damage에서 처리
                # 여기서는 상태만 변경

    def get_on_hit_damage(self, target, champion):
        # 3타가 터지는 순간 추가 적응형 피해
        if self.stacks == 3 and not self.active: # on_attack이 먼저 호출되므로 로직 주의
            # on_attack에서 active가 True로 바뀌므로, 여기서는 active가 True인 첫 순간을 잡아야 함
            # 하지만 구조상 on_attack -> get_one_hit_damage 순서라면
            # on_attack에서 active=True가 되었을 때, 이번 공격에 추가 피해를 줘야 함
            pass
        
        # 구조상 on_attack이 먼저 호출되고, 그 다음 get_one_hit_damage가 호출됨.
        # on_attack에서 stacks가 2->3이 되고 active=True가 됨.
        # 따라서 active가 True이고 stacks가 3인 경우에만 추가 피해를 주고 stacks를 유지?
        # 아니면 active 상태면 계속 증폭?
        
        # PTA 메커니즘: 3타 적중 시 추가 피해 + 이후 8% 증폭
        # 추가 피해는 1회성.
        
        # 여기서는 1회성 추가 피해만 반환
        # 증폭은 get_damage_modifier에서 처리
        
        # on_attack에서 3스택이 되면 active=True로 만듦.
        # 이번 턴에 추가 피해를 줘야 함.
        # 이를 구분하기 위해 별도 플래그나 카운터가 필요할 수 있음.
        # 간단하게: active가 True이고 stacks가 3이면 추가 피해 반환하고 stacks를 4로 변경? (내부적으로 처리)
        
        if self.active and self.stacks == 3:
            self.stacks = 4 # 추가 피해 줬음을 표시
            
            # 추가 적응형 피해: 40 ~ 160
            lvl = champion.level
            damage = 40 + (120 * (lvl - 1) / 17)
            return damage, 0 # 물리 피해
            
        return 0, 0

    def get_damage_modifier(self, target, champion):
        # 활성화 상태면 모든 피해 8% 증가
        if self.active:
            return 0.08
        return 0.0


class CoupDeGrace(Rune):
    def __init__(self):
        super().__init__("Coup de Grace")

    def get_damage_modifier(self, target, champion):
        # 적 체력 40% 이하 시 8% 증가
        if (target.current_hp / target.max_hp) <= 0.40:
            return 0.08
        return 0.0


class CutDown(Rune):
    def __init__(self):
        super().__init__("Cut Down")

    def get_damage_modifier(self, target, champion):
        # 적 체력 60% 이상 시 8% 증가
        if (target.current_hp / target.max_hp) >= 0.60:
            return 0.08
        return 0.0
