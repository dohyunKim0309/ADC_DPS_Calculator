# import matplotlib.pyplot as plt


# 1. 적 챔피언 (타겟) 클래스
class Target:
    def __init__(self, hp, armor, magic_resist, bonus_hp=0):
        self.max_hp = hp
        self.bonus_hp = bonus_hp
        self.current_hp = hp
        self.armor = armor
        self.magic_resist = magic_resist

    def reset(self):
        self.current_hp = self.max_hp


# 2. 챔피언 부모 클래스 (Base Class)
class Champion:
    def __init__(self, name, base_ad, base_as, as_ratio, as_growth, base_range, level=1, ad_growth=0):
        self.name = name
        self.level = level

        # 기본 능력치
        self.range = base_range
        self.base_ad = base_ad
        self.base_as = base_as
        self.as_ratio = as_ratio         # 공격 속도 계수
        self.as_growth = as_growth       # 레벨당 공속 증가량 (%)
        self.ad_growth = ad_growth       # 레벨당 공격력 증가량

        self.crit_chance = 0             # 치명타 확률

        # 인벤토리 및 상태
        self.inventory = []  # Item 객체들이 저장될 리스트
        self.hit_count = 0  # 평타 횟수 (구인수, 크라켄 등 카운팅용)
        self.rune = None    # 메인 룬

        # 동적 스탯 (아이템으로 인해 변함)
        self.bonus_ad = 0
        self.bonus_ap = 0
        self.bonus_as_percent = 0
        self.crit_chance = 0.0
        self.crit_damage_modifier = 2.00  # 기본 치명타 피해 200%
        self.armor_pen_percent = 0.0  # 방관 %
        self.magic_pen_percent = 0.0  # 마관 %
        self.lethality = 0  # 물리 관통력 (고정)
        self.magic_pen_flat = 0 # 마법 관통력 (고정)

    # 아이템 장착 함수
    def add_item(self, item):
        self.inventory.append(item)

        # 1. 스탯 단순 합산
        self.bonus_ad += item.stats.get('ad', 0)
        self.bonus_ap += item.stats.get('ap', 0)
        self.bonus_as_percent += item.stats.get('as', 0)
        self.crit_chance += item.stats.get('crit', 0)
        self.armor_pen_percent = 1 - (1 - self.armor_pen_percent) * (
                    1 - item.stats.get('armor_pen_percent', 0))  # 방관은 곱연산 적용이 정확하나 여기선 단순화 가능
        self.lethality += item.stats.get('lethality', 0)
        self.crit_damage_modifier += item.stats.get('add_crit_damage', 0)
        self.magic_pen_flat += item.stats.get('magic_pen_flat', 0)

    # 룬 장착 함수
    def set_rune(self, rune):
        self.rune = rune

    @property
    def total_ad(self):
        # 성장 공격력 반영: base_ad + (ad_growth * (level - 1)) + bonus_ad
        growth_ad = self.ad_growth * (self.level - 1)
        return self.base_ad + growth_ad + self.bonus_ad

    @property
    def total_ap(self):
        # 라바돈의 죽음모자 확인
        has_rabadon = any(item.name == "Rabadon's Deathcap" for item in self.inventory)
        multiplier = 1.30 if has_rabadon else 1.0
        return self.bonus_ap * multiplier

    def get_total_bonus_as_percent(self):
        """총 추가 공격 속도(%) 반환 (아이템 + 성장 + 룬)"""
        level_bonus = (self.as_growth * (self.level - 1)) / 100
        rune_bonus = self.rune.get_bonus_as() if self.rune else 0.0
        return level_bonus + self.bonus_as_percent + rune_bonus

    @property
    def current_attack_speed(self):
        # 추가 공격속도 = (레벨업 보너스) + (아이템 보너스) + (룬 보너스)
        total_bonus = self.get_total_bonus_as_percent()

        # 공식: 기본공속 + (공속계수 * 추가공속)
        final_as = self.base_as + (self.as_ratio * total_bonus)
        
        # 공격 속도 상한 3.0 적용
        final_as = min(final_as, 3.0)

        return round(final_as, 3)  # 소수점 3자리 반올림

    def get_attack_interval(self):
        # 초당 공격 횟수의 역수 = 공격 간격 (초)
        # 공속이 0이면 무한대 방지
        current_as = self.current_attack_speed
        if current_as <= 0: return 9999
        return 1.0 / current_as

    def get_champion_onhit(self, target):
        """챔피언 고유 스킬에 의한 온힛 대미지 (구인수 적용 대상)"""
        return 0, 0
    
    def on_shadowflame_crit(self, target):
        """그림자불꽃 발동 시 추가 효과 (챔피언별 오버라이딩)"""
        return 0, 0
        
    def update(self, time, target):
        """매 프레임마다 호출되어 스킬 쿨타임 등을 관리하고 스킬 대미지를 반환"""
        return 0, 0 # (Phys, Magic)

    # [핵심] 챔피언별로 오버라이딩 할 메서드
    # 반환값: (물리_기본, 마법_기본, 물리_온힛, 마법_온힛)
    def get_one_hit_damage(self, target, time=0):
        # ---------------------------------------------------------
        # 0. 룬 효과 발동 (공격 시)
        # ---------------------------------------------------------
        if self.rune:
            self.rune.on_attack(self)

        # ---------------------------------------------------------
        # 1. 기본 물리 피해 계산
        # ---------------------------------------------------------
        phys_base = self.total_ad * self.crit_damage_modifier * self.crit_chance + self.total_ad * (
                    1 - self.crit_chance)
        magic_base = 0

        # ---------------------------------------------------------
        # 2. 아이템 및 챔피언 온힛 대미지 처리 (구인수 적용)
        # ---------------------------------------------------------

        # 2.0 내부 함수: 현재 인벤토리의 모든 온힛 효과를 한 번 실행하고 합산
        def get_all_onhit():
            p_sum = 0
            m_sum = 0
            
            # 아이템 온힛
            for item in self.inventory:
                p, m = item.on_hit(target, self)
                p_sum += p
                m_sum += m
            
            # 룬 온힛
            if self.rune:
                rp, rm = self.rune.get_on_hit_damage(target, self)
                p_sum += rp
                m_sum += rm
                
            # 챔피언 스킬 온힛 (추가됨)
            cp, cm = self.get_champion_onhit(target)
            p_sum += cp
            m_sum += cm

            return p_sum, m_sum

        # 2.1 구인수 객체 찾기 및 상태 확인
        guinsoo_item = next((item for item in self.inventory if getattr(item, 'is_guinsoo', False)), None)

        # [조건] 구인수가 있고 + 스택이 4(풀스택)여야 함
        is_guinsoo_active = (guinsoo_item is not None) and (guinsoo_item.stack >= 4)

        # 2.2 실행 횟수(proc_count) 결정
        proc_count = 1

        # 구인수 풀스택 상태에서, 3번째 평타마다 2회 발동
        if is_guinsoo_active and (self.hit_count > 0) and (self.hit_count % 3 == 0):
            proc_count = 2

        # 2.3 결정된 횟수만큼 온힛 루프 실행
        total_phys_onhit = 0
        total_magic_onhit = 0

        for _ in range(proc_count):
            p, m = get_all_onhit()
            total_phys_onhit += p
            total_magic_onhit += m

        # ---------------------------------------------------------
        # 3. 대미지 증폭(Multiplier) 적용 (거인 학살자 등)
        # ---------------------------------------------------------
        damage_multiplier = 0.0

        for item in self.inventory:
            # item 클래스에 get_damage_modifier 메서드가 있다고 가정 (없으면 0 처리 필요)
            if hasattr(item, 'get_damage_modifier'):
                damage_multiplier += item.get_damage_modifier(target, self)

        # 증폭 계수 적용 (예: 1.15)
        mod_factor = 1.0 + damage_multiplier

        phys_base *= mod_factor
        magic_base *= mod_factor
        total_phys_onhit *= mod_factor
        total_magic_onhit *= mod_factor
        
        # ---------------------------------------------------------
        # 4. 그림자불꽃 (Shadowflame) 적용
        # ---------------------------------------------------------
        has_shadowflame = any(item.name == "Shadowflame" for item in self.inventory)
        if has_shadowflame and (target.current_hp / target.max_hp) <= 0.40:
            # 잿덩이꽃: 마법 피해 20% 증폭, 치명타 피해량에 영향 받음
            # 기본 20% 증폭. 무대(치명피해+30%)가 있으면 20% * 1.3 = 26% 증폭
            bonus_crit_damage = self.crit_damage_modifier - 2.0
            shadowflame_multiplier = 1.20 + (0.20 * bonus_crit_damage)
            
            # 유나라 패시브 재귀 적용 (가설 2)
            recursive_multiplier = 1.0
            if self.name == "Yunara":
                recursive_multiplier = 1.1 + (0.001 * self.total_ap)
            
            final_multiplier = shadowflame_multiplier * recursive_multiplier
            
            magic_base *= final_multiplier
            total_magic_onhit *= final_multiplier

        # 5. 평타 횟수 증가
        self.hit_count += 1

        # 6. 최종 반환
        return phys_base, magic_base, total_phys_onhit, total_magic_onhit


# 3. 개별 챔피언 구현 (예: 애쉬, 케이틀린)
class Ashe(Champion):
    def __init__(self, level=1, q_level=5):
        # 성장 공속 3.33% 적용, 성장 공격력 3.5 적용 (버프 반영)
        super().__init__(name="Ashe", base_ad=59, base_as=0.658, as_ratio=0.658, as_growth=3.33, base_range=600, level=level, ad_growth=3.5)
        
        # 스킬 레벨 설정
        self.q_level = q_level
        
        # Q 상태 관리
        self.q_active = False
        self.q_start_time = 0.0
        self.q_as_buff_applied = False # 공속 버프 중복 적용 방지
        
        # Q 데이터 (레벨별)
        # 공격 속도: 20 / 30 / 40 / 50 / 60%
        self.q_as_amounts = [0.20, 0.30, 0.40, 0.50, 0.60]
        # 피해량 계수: 1.1 / 1.175 / 1.25 / 1.325 / 1.4
        self.q_dmg_multipliers = [1.1, 1.175, 1.25, 1.325, 1.4]

    def get_one_hit_damage(self, target, time=0):
        # 1. Q 지속시간 확인 및 해제 (6초)
        if self.q_active:
            if time - self.q_start_time > 6.0:
                self.deactivate_q()

        # 2. Q 활성화 조건 확인
        # 평타 4회 적중 시 스택이 쌓이고, 그 다음 공격(5번째)부터 Q 사용 가능으로 가정
        if not self.q_active and self.hit_count >= 4:
            self.activate_q(time)

        # 3. 부모 클래스의 기본 대미지 계산 (기댓값 로직 포함)
        p_base, m_base, p_onhit, m_onhit = super().get_one_hit_damage(target, time)

        # 4. Q 활성화 시 기본 공격 피해 증폭
        if self.q_active:
            idx = self.q_level - 1
            multiplier = self.q_dmg_multipliers[idx]
            
            # 기본 물리 피해에 계수 곱연산 (예: 165 * 1.325)
            p_base *= multiplier
            
            # (선택) 온힛 대미지는 Q의 "다발 공격"에 의해 여러 번 적용되지 않고 1회만 적용됨(설명 참조).
            # 다만 Q 자체 계수가 온힛까지 증폭시키진 않으므로 p_base만 증폭하는 것이 일반적임.
            # 만약 "강화된 기본 공격" 전체가 증폭된다면 아래 주석 해제.
            # p_onhit *= multiplier 

        return p_base, m_base, p_onhit, m_onhit

    def activate_q(self, time):
        self.q_active = True
        self.q_start_time = time
        
        # 공속 버프 적용
        if not self.q_as_buff_applied:
            idx = self.q_level - 1
            as_bonus = self.q_as_amounts[idx]
            self.bonus_as_percent += as_bonus
            self.q_as_buff_applied = True
            print(f"[{time:.2f}s] Ashe Q Activated! (AS +{as_bonus*100:.0f}%, Dmg x{self.q_dmg_multipliers[idx]})")

    def deactivate_q(self):
        self.q_active = False
        
        # 공속 버프 해제
        if self.q_as_buff_applied:
            idx = self.q_level - 1
            as_bonus = self.q_as_amounts[idx]
            self.bonus_as_percent -= as_bonus
            self.q_as_buff_applied = False
            print(f"Ashe Q Expired.")
            
    def cast_w(self, target):
        # W: 일제 사격 (단순 대미지 계산용)
        # 200 (+1.1 추가 AD) - 5레벨 기준
        base_dmg = 200
        scaling = 1.1 * self.bonus_ad
        return base_dmg + scaling


class Yunara(Champion):
    def __init__(self, level=1, q_level=5):
        # Base AD 55, AS 0.65, AS Ratio 0.65, AS Growth 2.75, AD Growth 2.5
        super().__init__(name="Yunara", base_ad=55, base_as=0.650, as_ratio=0.650, as_growth=2.75, base_range=575, level=level, ad_growth=2.5)
        
        self.q_level = q_level
        
        # Q 상태 관리
        self.q_active = False
        self.q_start_time = 0.0
        self.q_as_buff_applied = False
        self.q_stacks = 0 # 방출 스택 (최대 8)
        
        # Q 데이터 (레벨별)
        # 추가 공속: 20 / 30 / 40 / 50 / 60%
        self.q_as_amounts = [0.20, 0.30, 0.40, 0.50, 0.60]
        # 적중 시 마법 피해: 5 / 10 / 15 / 20 / 25 (+0.1 AP)
        self.q_onhit_base = [5, 10, 15, 20, 25]

    def get_champion_onhit(self, target):
        """유나라 Q 스킬 온힛 대미지 (구인수 적용)"""
        idx = self.q_level - 1
        base_q_dmg = self.q_onhit_base[idx] + (0.1 * self.total_ap)
        
        # Q 활성화 시 추가 피해 적용 (기본 + 추가 = 2배)
        if self.q_active:
            return 0, base_q_dmg * 2
        else:
            return 0, base_q_dmg

    def on_shadowflame_crit(self, target):
        """그림자불꽃 발동 시 유나라 패시브 추가 발동 (재귀 로직으로 통합되어 사용 안 함)"""
        return 0, 0

    def get_one_hit_damage(self, target, time=0):
        # 1. Q 지속시간 확인 및 해제 (5초)
        if self.q_active:
            if time - self.q_start_time > 5.0:
                self.deactivate_q()

        # 2. Q 활성화 조건 확인 (8스택 이상)
        if not self.q_active and self.q_stacks >= 8:
            self.activate_q(time)

        # 3. 부모 클래스의 기본 대미지 계산 (여기서 get_champion_onhit이 호출됨)
        p_base, m_base, p_onhit, m_onhit = super().get_one_hit_damage(target, time)

        # 4. 패시브: 치명타 시 추가 마법 피해 (10% + 0.1 AP)
        # 치명타가 터졌는지 여부는 확률적으로 결정되지만, 여기서는 기댓값(평균)으로 계산
        # 치명타 확률만큼의 비율로 추가 마법 피해 적용
        passive_dmg = (0.10 + 0.001 * self.total_ap) * self.total_ad
        m_base += passive_dmg * self.crit_chance * self.crit_damage_modifier

        # 5. 스택 관리 (공격 시 2스택 증가 - 챔피언 대상)
        # Q 활성화 중에는 스택이 쌓이지 않음
        if not self.q_active and self.q_stacks < 8:
            self.q_stacks = min(8, self.q_stacks + 2)

        return p_base, m_base, p_onhit, m_onhit

    def activate_q(self, time):
        self.q_active = True
        self.q_start_time = time
        self.q_stacks = 0 # 스택 소모
        
        # 공속 버프 적용
        if not self.q_as_buff_applied:
            idx = self.q_level - 1
            as_bonus = self.q_as_amounts[idx]
            self.bonus_as_percent += as_bonus
            self.q_as_buff_applied = True
            print(f"[{time:.2f}s] Yunara Q Activated! (AS +{as_bonus*100:.0f}%)")

    def deactivate_q(self):
        self.q_active = False
        
        # 공속 버프 해제
        if self.q_as_buff_applied:
            idx = self.q_level - 1
            as_bonus = self.q_as_amounts[idx]
            self.bonus_as_percent -= as_bonus
            self.q_as_buff_applied = False
            print(f"Yunara Q Expired.")


class Kaisa(Champion):
    def __init__(self, level=1, q_level=5, w_level=1, e_level=1):
        # Base AD 59, AD Growth 2.6, AS 0.644, AS Ratio 0.644, AS Growth 1.8
        super().__init__(name="Kaisa", base_ad=59, base_as=0.644, as_ratio=0.644, as_growth=1.8, base_range=525, level=level, ad_growth=2.6)
        
        self.q_level = q_level
        self.w_level = w_level
        self.e_level = e_level
        
        # 패시브 상태
        self.plasma_stacks = 0
        
        # 스킬 쿨타임 관리
        self.q_cooldown = 0.0
        self.w_cooldown = 0.0
        self.e_cooldown = 0.0
        self.last_q_time = -999
        self.last_w_time = -999
        self.last_e_time = -999
        
        # E 스킬 상태
        self.e_active = False
        self.e_end_time = 0.0
        self.e_as_buff_applied = False
        self.is_charging_e = False # E 충전 중 (공격 불가)
        self.e_charge_end_time = 0.0

    def get_evolved_status(self):
        # 진화 조건 확인
        # Q: 추가 AD 100 이상 (성장 AD 포함)
        bonus_ad_total = (self.ad_growth * (self.level - 1)) + self.bonus_ad
        q_evolved = bonus_ad_total >= 100
        
        # W: AP 100 이상
        w_evolved = self.total_ap >= 100
        
        # E: 추가 AS 100% 이상 (성장 AS 포함)
        bonus_as_total = self.get_total_bonus_as_percent()
        e_evolved = bonus_as_total >= 1.0
        
        return q_evolved, w_evolved, e_evolved

    def update(self, time, target):
        """매 프레임 호출: 스킬 사용 및 상태 관리"""
        q_evolved, w_evolved, e_evolved = self.get_evolved_status()
        
        total_phys_skill = 0
        total_magic_skill = 0
        
        # E 스킬 사용 (쿨타임 돌았고, 충전 중이 아닐 때)
        # 시뮬레이션 단순화를 위해 쿨타임마다 즉시 사용한다고 가정
        # 실제로는 평타 캔슬이나 상황에 따라 다르지만, DPS 측정용이므로 쿨마다 사용
        if time >= self.last_e_time + self.e_cooldown and not self.is_charging_e and not self.e_active:
            # E 쿨타임 계산: 16 / 14.5 / 13 / 11.5 / 10
            base_cd = [16, 14.5, 13, 11.5, 10][self.e_level - 1]
            # 쿨감 적용 (아이템 등) - 현재 Champion 클래스에 cdr 속성이 없으므로 생략하거나 추가 필요
            # 여기선 0% 가정
            self.e_cooldown = base_cd 
            
            # 충전 시간 계산: 1.2 ~ 0.6초 (공속 비례)
            # 추가 공속 0% -> 1.2초, 100% -> 0.6초 (대략적)
            bonus_as = self.get_total_bonus_as_percent()
            charge_time = max(0.6, 1.2 - (0.6 * (bonus_as / 1.0)))
            
            self.is_charging_e = True
            self.e_charge_end_time = time + charge_time
            self.last_e_time = time
            # print(f"[{time:.2f}s] Kaisa E Charging... ({charge_time:.2f}s)")
            
        # E 충전 완료 확인
        if self.is_charging_e and time >= self.e_charge_end_time:
            self.is_charging_e = False
            self.e_active = True
            self.e_end_time = time + 4.0 # 4초 지속
            
            # 공속 버프 적용
            if not self.e_as_buff_applied:
                # 40 / 50 / 60 / 70 / 80%
                as_buff = [0.4, 0.5, 0.6, 0.7, 0.8][self.e_level - 1]
                self.bonus_as_percent += as_buff
                self.e_as_buff_applied = True
                # print(f"[{time:.2f}s] Kaisa E Buff Activated! (+{as_buff*100:.0f}%)")
                
        # E 버프 종료 확인
        if self.e_active and time >= self.e_end_time:
            self.e_active = False
            if self.e_as_buff_applied:
                as_buff = [0.4, 0.5, 0.6, 0.7, 0.8][self.e_level - 1]
                self.bonus_as_percent -= as_buff
                self.e_as_buff_applied = False
                # print(f"[{time:.2f}s] Kaisa E Buff Expired.")

        # E 충전 중에는 공격/스킬 불가
        if self.is_charging_e:
            return 0, 0

        # Q 스킬 사용
        if time >= self.last_q_time + self.q_cooldown:
            # 쿨타임: 10 / 9 / 8 / 7 / 6
            base_cd = [10, 9, 8, 7, 6][self.q_level - 1]
            self.q_cooldown = base_cd # 쿨감 미적용
            self.last_q_time = time
            
            # 대미지 계산
            # 미사일 수: 기본 6, 진화 12
            missile_count = 12 if q_evolved else 6
            
            # 미사일 1개당 피해: 40~100 + 0.5 추가AD + 0.2 AP
            base_dmg = [40, 55, 70, 85, 100][self.q_level - 1]
            bonus_ad = (self.ad_growth * (self.level - 1)) + self.bonus_ad
            per_missile = base_dmg + (0.5 * bonus_ad) + (0.2 * self.total_ap)
            
            # 단일 대상 적중 시: 첫 발 100%, 나머지 25%
            total_q_dmg = per_missile + (per_missile * 0.25 * (missile_count - 1))
            
            total_phys_skill += total_q_dmg
            # print(f"[{time:.2f}s] Kaisa Q Cast! (Dmg: {total_q_dmg:.1f})")

        # W 스킬 사용 (쿨타임마다)
        if time >= self.last_w_time + self.w_cooldown:
            # 쿨타임: 22 / 20 / 18 / 16 / 14
            base_cd = [22, 20, 18, 16, 14][self.w_level - 1]
            self.w_cooldown = base_cd
            self.last_w_time = time
            
            # 대미지: 30~130 + 1.3 총AD + 0.45 AP
            base_w = [30, 55, 80, 105, 130][self.w_level - 1]
            w_dmg = base_w + (1.3 * self.total_ad) + (0.45 * self.total_ap)
            
            total_magic_skill += w_dmg
            
            # 플라즈마 스택 적용: 기본 2, 진화 3
            stacks_to_add = 3 if w_evolved else 2
            
            # 스택 적용 및 폭발 처리 (패시브 로직 재사용 필요하지만 여기선 간단히 구현)
            # W로 인한 스택은 평타 스택과 별개로 즉시 적용
            # 4스택 폭발 로직은 get_one_hit_damage와 공유해야 하므로 별도 메서드로 분리하는 게 좋음
            # 일단 여기서는 스택만 쌓고, 폭발은 다음 평타나 W 자체에서 처리
            
            # W 적중 시에도 패시브 대미지가 터질 수 있음 (스택이 4가 되면)
            # 현재 스택 + 추가 스택
            current_stacks = self.plasma_stacks
            
            # 스택이 4를 초과하면 폭발하고 남은 스택 적용? 
            # 카이사 패시브는 4스택에서 '공격' 시 폭발. W도 공격으로 간주됨.
            
            # 시뮬레이션 편의상 W는 단순히 대미지와 스택만 주고, 폭발은 평타 사이클에서 처리하거나
            # 여기서 직접 계산. W로 폭발시키는 경우도 많음.
            
            # W 적중 -> 스택 증가 -> 4스택 도달 시 폭발 대미지 추가
            for _ in range(stacks_to_add):
                self.plasma_stacks += 1
                if self.plasma_stacks >= 5: # 0~4 쌓고 5가 되면 폭발
                    # 폭발 대미지 계산
                    # 잃은 체력 비례: 15% + (0.06% * AP)
                    missing_hp = target.max_hp - target.current_hp
                    ratio = 0.15 + (0.0006 * self.total_ap)
                    proc_dmg = missing_hp * ratio
                    
                    # 몬스터 대상 제한은 무시 (챔피언 기준)
                    total_magic_skill += proc_dmg
                    self.plasma_stacks = 0 # 초기화
            
            # 진화 시 챔피언 적중하면 쿨타임 75% 반환
            if w_evolved:
                self.w_cooldown *= 0.25
                
            # print(f"[{time:.2f}s] Kaisa W Hit! (Dmg: {w_dmg:.1f})")

        return total_phys_skill, total_magic_skill

    def get_one_hit_damage(self, target, time=0):
        # E 충전 중이면 공격 불가 (0 반환)
        if self.is_charging_e:
            return 0, 0, 0, 0

        # E 쿨타임 감소 (평타 시 0.5초)
        if self.e_cooldown > 0:
            self.last_e_time += 0.5 # 쿨타임 계산 기준 시간을 당겨줌 (간접적 쿨감)

        # 부모 클래스 대미지 계산
        p_base, m_base, p_onhit, m_onhit = super().get_one_hit_damage(target, time)

        # 패시브: 부식성 흉터
        # 1. 기본 추가 피해: 4~24 + 0.12 AP + (1~6 + 0.03 AP) * 중첩
        # 레벨 비례값 (1~18)
        base_proc = 4 + ((24-4) * (self.level-1) / 17)
        stack_proc = 1 + ((6-1) * (self.level-1) / 17)
        
        passive_magic = (base_proc + 0.12 * self.total_ap) + \
                        (self.plasma_stacks * (stack_proc + 0.03 * self.total_ap))
        
        m_onhit += passive_magic

        # 2. 스택 쌓기 (구인수 고려는 super().get_one_hit_damage 내부에서 처리되지 않음)
        # Champion 클래스의 구조상 get_one_hit_damage는 1회 공격에 대해 호출됨.
        # 구인수 효과는 내부적으로 get_item_onhit을 반복 호출함.
        # 카이사 패시브 스택은 '공격 시' 쌓이므로, 구인수 환영 타격에도 쌓여야 함.
        # 이를 위해 get_champion_onhit을 활용해야 함.
        
        # 하지만 get_champion_onhit은 대미지만 반환하고 상태(스택)를 변경하면 안 됨 (예측 불가)
        # 따라서 여기서 직접 스택을 관리하되, 구인수 여부를 확인해야 함.
        
        # 구인수 보유 확인
        has_guinsoo = any(getattr(item, 'is_guinsoo', False) for item in self.inventory)
        is_phantom_hit = has_guinsoo and (self.hit_count > 0) and (self.hit_count % 3 == 0)
        
        stacks_to_add = 2 if is_phantom_hit else 1
        
        # 스택 적용 및 폭발
        # 카이사 패시브는 공격 '시' 스택 적용 -> 5스택(4+1) 되면 폭발
        for _ in range(stacks_to_add):
            self.plasma_stacks += 1
            if self.plasma_stacks >= 5:
                # 폭발 대미지
                missing_hp = target.max_hp - target.current_hp
                ratio = 0.15 + (0.0006 * self.total_ap)
                proc_dmg = missing_hp * ratio
                m_onhit += proc_dmg
                self.plasma_stacks = 0

        return p_base, m_base, p_onhit, m_onhit
