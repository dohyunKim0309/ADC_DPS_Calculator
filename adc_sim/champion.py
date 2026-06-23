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
        self.sub_rune = None # 보조 룬

        # 동적 스탯 (아이템으로 인해 변함)
        self.bonus_ad = 0
        self.bonus_ap = 0
        self.bonus_mana = 0
        self.bonus_as_percent = 0
        self.crit_chance = 0.0
        self.crit_damage_modifier = 2.00  # 기본 치명타 피해 200%
        self.armor_pen_percent = 0.0  # 방관 %
        self.magic_pen_percent = 0.0  # 마관 %
        self.lethality = 0  # 물리 관통력 (고정)
        self.magic_pen_flat = 0 # 마법 관통력 (고정)
        self.ability_haste = 0.0 # 스킬 가속
        self._combat_time = 0.0
        
        # 시뮬레이션 설정
        self.target_count = 1 # 적 수 (루난 효율 계산용)

    # 아이템 장착 함수
    def add_item(self, item):
        self.inventory.append(item)

        # 1. 스탯 단순 합산
        self.bonus_ad += item.stats.get('ad', 0)
        self.bonus_ap += item.stats.get('ap', 0)
        self.bonus_mana += item.stats.get('mana', 0)
        self.bonus_as_percent += item.stats.get('as', 0)
        self.crit_chance += item.stats.get('crit', 0)
        self.armor_pen_percent = 1 - (1 - self.armor_pen_percent) * (
                    1 - item.stats.get('armor_pen_percent', 0))  # 방관은 곱연산 적용이 정확하나 여기선 단순화 가능
        self.lethality += item.stats.get('lethality', 0)
        self.crit_damage_modifier += item.stats.get('add_crit_damage', 0)
        self.magic_pen_flat += item.stats.get('magic_pen_flat', 0)
        self.ability_haste += item.stats.get('cdr', 0)

    # 룬 장착 함수
    def set_rune(self, rune):
        self.rune = rune
        
    def set_sub_rune(self, rune):
        self.sub_rune = rune
        
    def set_target_count(self, count):
        self.target_count = count
        
    def cast_spell(self, time):
        """스킬 사용 시 호출 (주문검 활성화 등)"""
        for item in self.inventory:
            if hasattr(item, 'on_spell_cast'):
                item.on_spell_cast(self, time)
                
    def cast_ultimate(self, time):
        """궁극기 사용 시 호출 (아이템 효과 활성화 등)"""
        for item in self.inventory:
            if hasattr(item, 'on_ult_cast'):
                item.on_ult_cast(self, time)

    @property
    def base_attack_ad(self):
        # 현재 레벨 기준 "기본 공격력" (아이템 AD 제외)
        growth_ad = self.ad_growth * (self.level - 1)
        return self.base_ad + growth_ad

    @property
    def total_ad(self):
        dynamic_bonus_ad = 0.0
        for item in self.inventory:
            if hasattr(item, "get_bonus_ad"):
                dynamic_bonus_ad += item.get_bonus_ad(self)
        rune_bonus_ad = 0.0
        if self.rune and hasattr(self.rune, "get_bonus_ad"):
            rune_bonus_ad += self.rune.get_bonus_ad(self)
        if self.sub_rune and hasattr(self.sub_rune, "get_bonus_ad"):
            rune_bonus_ad += self.sub_rune.get_bonus_ad(self)
        return self.base_attack_ad + self.bonus_ad + dynamic_bonus_ad + rune_bonus_ad

    @property
    def total_ap(self):
        # 라바돈의 죽음모자 확인
        has_rabadon = any(item.name == "Rabadon's Deathcap" for item in self.inventory)
        multiplier = 1.30 if has_rabadon else 1.0
        return self.bonus_ap * multiplier

    @property
    def total_mana(self):
        base_mana = getattr(self, "base_mana", 0.0)
        mana_growth = getattr(self, "mana_growth", 0.0)
        growth_mana = mana_growth * (self.level - 1)

        dynamic_bonus_mana = 0.0
        for item in self.inventory:
            if hasattr(item, "get_bonus_mana"):
                dynamic_bonus_mana += item.get_bonus_mana(self)
        return base_mana + growth_mana + self.bonus_mana + dynamic_bonus_mana

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

    @property
    def cooldown_multiplier(self):
        # 스킬가속(AH): 최종 쿨타임 = 기본쿨 * (100 / (100 + AH))
        return 100.0 / (100.0 + max(0.0, self.ability_haste))

    @property
    def total_ability_haste(self):
        return self.ability_haste

    def apply_haste_to_cooldown(self, base_cooldown):
        return base_cooldown * (100.0 / (100.0 + max(0.0, self.total_ability_haste)))

    def get_champion_onhit(self, target):
        """챔피언 고유 스킬에 의한 온힛 대미지 (구인수 적용 대상)"""
        return 0, 0
    
    def on_shadowflame_crit(self, target):
        """그림자불꽃 발동 시 추가 효과 (챔피언별 오버라이딩)"""
        return 0, 0
        
    # 엔진 주도 이벤트 인터페이스 (기본: 스킬 이벤트 없음)
    def init_combat_state(self, skill_plan=None):
        self._combat_time = 0.0

    def advance_combat_time(self, delta_time, current_time, target):
        self._combat_time = current_time

    def get_time_to_next_skill_event(self, current_time):
        return float("inf")

    def get_time_to_next_state_event(self, current_time):
        return float("inf")

    def pop_due_skill_events(self, current_time, target):
        # event tuple: (skill_name, raw_phys, raw_magic, is_skill_hit)
        return []

    def get_on_skill_hit_damage(self, target, time=0.0):
        phys = 0.0
        magic = 0.0
        true = 0.0
        for item in self.inventory:
            if hasattr(item, "on_skill_hit"):
                p, m, t = item.on_skill_hit(target, self, time)
                phys += p
                magic += m
                true += t
        return phys, magic, true

    # [핵심] 챔피언별로 오버라이딩 할 메서드
    # 반환값: (물리_기본, 마법_기본, 물리_온힛, 마법_온힛, 물리_고정_기본, 물리_고정_온힛)
    def get_one_hit_damage(self, target, time=0):
        self._combat_time = time
        # ---------------------------------------------------------
        # 0. 룬 효과 발동 (공격 시)
        # ---------------------------------------------------------
        if self.rune:
            self.rune.on_attack(self)
        if self.sub_rune:
            self.sub_rune.on_attack(self)

        # ---------------------------------------------------------
        # 1. 기본 물리 피해 계산
        # ---------------------------------------------------------
        phys_base = self.total_ad * self.crit_damage_modifier * self.crit_chance + self.total_ad * (
                    1 - self.crit_chance)
        magic_base = 0
        phys_true_base = 0 # 평타 고정 피해
        phys_true_onhit = 0 # 온힛 고정 피해

        # ---------------------------------------------------------
        # 2. 아이템 및 챔피언 온힛 대미지 처리 (구인수 적용)
        # ---------------------------------------------------------

        # 2.0 내부 함수: 현재 인벤토리의 모든 온힛 효과를 한 번 실행하고 합산
        def get_all_onhit():
            p_sum = 0
            m_sum = 0
            pt_base_sum = 0 # 평타 고정 피해 합산
            pt_onhit_sum = 0 # 온힛 고정 피해 합산
            
            # 아이템 온힛
            for item in self.inventory:
                p, m, pt_b, pt_o = item.on_hit(target, self) # 4개 반환
                p_sum += p
                m_sum += m
                pt_base_sum += pt_b
                pt_onhit_sum += pt_o
            
            # 룬 온힛 (메인 룬)
            if self.rune:
                rp, rm = self.rune.get_on_hit_damage(target, self)
                p_sum += rp
                m_sum += rm
                
            # 챔피언 스킬 온힛 (추가됨)
            cp, cm = self.get_champion_onhit(target)
            p_sum += cp
            m_sum += cm

            return p_sum, m_sum, pt_base_sum, pt_onhit_sum

        # 2.1 실행 횟수(proc_count) 결정
        # 아이템이 온힛 처리 횟수를 확장할 수 있도록 훅 제공 (예: 구인수)
        proc_count = 1
        for item in self.inventory:
            if hasattr(item, "get_onhit_proc_count"):
                proc_count = max(proc_count, item.get_onhit_proc_count(self))

        # 2.2 결정된 횟수만큼 온힛 루프 실행
        total_phys_onhit = 0
        total_magic_onhit = 0
        total_true_base = 0
        total_true_onhit = 0

        for _ in range(proc_count):
            p, m, pt_b, pt_o = get_all_onhit()
            total_phys_onhit += p
            total_magic_onhit += m
            total_true_base += pt_b
            total_true_onhit += pt_o

        # ---------------------------------------------------------
        # 3. 대미지 증폭(Multiplier) 적용 (거인 학살자, 룬 등)
        # ---------------------------------------------------------
        damage_multiplier = 0.0
        c44_multiplier = 0.0 # C44는 별도 적용

        # 아이템 증폭
        for item in self.inventory:
            if hasattr(item, 'get_damage_modifier'):
                modifier = item.get_damage_modifier(target, self)
                if item.name == "Hextech Scope C44":
                    c44_multiplier += modifier
                else:
                    damage_multiplier += modifier
        
        # 룬 증폭 (메인 룬 + 보조 룬)
        if self.rune:
            damage_multiplier += self.rune.get_damage_modifier(target, self)
        if self.sub_rune:
            damage_multiplier += self.sub_rune.get_damage_modifier(target, self)

        # 일반 증폭 계수 적용 (예: 1.15)
        mod_factor = 1.0 + damage_multiplier

        phys_base *= mod_factor
        magic_base *= mod_factor
        total_phys_onhit *= mod_factor
        total_magic_onhit *= mod_factor
        
        # C44 증폭 적용 (기본 물리 피해에만 적용)
        if c44_multiplier > 0:
            phys_base *= (1.0 + c44_multiplier)
        
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
        return phys_base, magic_base, total_phys_onhit, total_magic_onhit, phys_true_base, total_true_onhit


# 3. 개별 챔피언 구현 (예: 애쉬, 케이틀린)
class Ashe(Champion):
    def __init__(self, level=1, q_level=5):
        # 성장 공속 3.33% 적용, 성장 공격력 3.5 적용 (버프 반영)
        super().__init__(name="Ashe", base_ad=59, base_as=0.658, as_ratio=0.658, as_growth=3.33, base_range=600, level=level, ad_growth=3.5)
        
        # 스킬 레벨 설정
        self.q_level = q_level
        # 시뮬레이션 시작 조건 변경:
        # Q 준비 스택을 2부터 시작시키기 위해(평-평-Q평 캔슬),
        # 현재 Q 준비 조건에 사용 중인 hit_count를 2로 초기화한다.
        self.hit_count = 2
        
        # Q 상태 관리
        self.q_active = False
        self.q_start_time = 0.0
        self.q_as_buff_applied = False # 공속 버프 중복 적용 방지
        self.q_attack_reset_pending = False  # Q 활성화 직후 다음 평타 간격 0.2초 적용
        
        # Q 데이터 (레벨별)
        # 공격 속도: 20 / 30 / 40 / 50 / 60%
        self.q_as_amounts = [0.20, 0.30, 0.40, 0.50, 0.60]
        # 피해량 계수: 1.1 / 1.175 / 1.25 / 1.325 / 1.4
        self.q_dmg_multipliers = [1.1, 1.15, 1.20, 1.25, 1.3]

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
        p_base, m_base, p_onhit, m_onhit, pt_base, pt_onhit = super().get_one_hit_damage(target, time)

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

        return p_base, m_base, p_onhit, m_onhit, pt_base, pt_onhit

    def get_attack_interval(self):
        # Q 4스택 후 활성화되는 공격 직후에는 평타 딜레이 캔슬을 반영해 다음 평타를 0.2초로 처리
        if self.q_attack_reset_pending:
            self.q_attack_reset_pending = False
            return 0.2
        return super().get_attack_interval()

    def activate_q(self, time):
        self.q_active = True
        self.q_start_time = time
        self.q_attack_reset_pending = True
        
        # 공속 버프 적용
        if not self.q_as_buff_applied:
            idx = self.q_level - 1
            as_bonus = self.q_as_amounts[idx]
            self.bonus_as_percent += as_bonus
            self.q_as_buff_applied = True
            # print(f"[{time:.2f}s] Ashe Q Activated! (AS +{as_bonus*100:.0f}%, Dmg x{self.q_dmg_multipliers[idx]})")
            
            # 주문검 활성화 (정수 약탈자)
            self.cast_spell(time)
            
            # 궁극기 사용 (악마사냥꾼의 화살)
            self.cast_ultimate(time)

    def deactivate_q(self):
        self.q_active = False
        self.q_attack_reset_pending = False
        
        # 공속 버프 해제
        if self.q_as_buff_applied:
            idx = self.q_level - 1
            as_bonus = self.q_as_amounts[idx]
            self.bonus_as_percent -= as_bonus
            self.q_as_buff_applied = False
            # print(f"Ashe Q Expired.")
            
    def cast_w(self, target):
        # W: 일제 사격 (단순 대미지 계산용)
        # 200 (+1.1 추가 AD) - 5레벨 기준
        base_dmg = 200
        scaling = 1.1 * self.bonus_ad
        
        # 주문검 활성화 (정수 약탈자)
        self.cast_spell(0) # time 인자가 없으므로 0 전달 (단순 활성화용)
        
        return base_dmg + scaling


class Jinx(Champion):
    def __init__(self, level=1, q_level=5, minigun_stacks=3, q_mode="minigun"):
        # 요청 스펙 기준: AD 59(+3.15), AS 0.625(+1%)
        super().__init__(
            name="Jinx",
            base_ad=59,
            base_as=0.625,
            as_ratio=0.625,
            as_growth=1.0,
            base_range=525,
            level=level,
            ad_growth=3.15,
        )

        self.q_level = max(1, min(5, q_level))
        self.q_mode = q_mode
        self.minigun_stacks = max(0, min(3, minigun_stacks))
        self.minigun_stack_duration = 2.5
        self.last_minigun_hit_time = -999.0
        # Q 최대 3중첩 기준 총 공속 증가량
        self.q_max_as_bonus = [0.30, 0.55, 0.80, 1.05, 1.30]
        self.fishbones_ad_multiplier = 1.10
        self.fishbones_bonus_as_multiplier = 0.90

    def get_total_bonus_as_percent(self):
        # 파워스파이크 비교에서는 유지딜 기준으로 Q 모드를 고정 반영.
        base_bonus = super().get_total_bonus_as_percent()
        max_bonus = self.q_max_as_bonus[self.q_level - 1]
        stack_bonus = max_bonus * (self.minigun_stacks / 3.0)
        if self.q_mode == "fishbones":
            # 생선 대가리: "추가 공격 속도"에 곱연산 -10%
            # 요청 반영: Fishbones에서는 Q 스택 공속 증가 미적용
            return base_bonus * self.fishbones_bonus_as_multiplier

        # 미니건: 스택에 비례한 공속 보너스
        return base_bonus + stack_bonus

    def get_one_hit_damage(self, target, time=0):
        # 미니건 스택은 마지막 미니건 적중 후 2.5초 유지
        if self.q_mode == "minigun" and (time - self.last_minigun_hit_time > self.minigun_stack_duration):
            self.minigun_stacks = 0

        p_base, m_base, p_onhit, m_onhit, pt_base, pt_onhit = super().get_one_hit_damage(target, time)

        # 미니건 평타 적중 시 스택 증가 (최대 3)
        if self.q_mode == "minigun":
            self.minigun_stacks = min(3, self.minigun_stacks + 1)
            self.last_minigun_hit_time = time

        if self.q_mode == "fishbones":
            p_base *= self.fishbones_ad_multiplier
        return p_base, m_base, p_onhit, m_onhit, pt_base, pt_onhit


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
        p_base, m_base, p_onhit, m_onhit, pt_base, pt_onhit = super().get_one_hit_damage(target, time)

        # 4. 패시브: 치명타 시 추가 마법 피해 (10% + 0.1 AP)
        # 치명타가 터졌는지 여부는 확률적으로 결정되지만, 여기서는 기댓값(평균)으로 계산
        # 치명타 확률만큼의 비율로 추가 마법 피해 적용
        passive_dmg = (0.10 + 0.001 * self.total_ap) * self.total_ad
        m_base += passive_dmg * self.crit_chance * self.crit_damage_modifier

        # 5. 스택 관리 (공격 시 2스택 증가 - 챔피언 대상)
        # Q 활성화 중에는 스택이 쌓이지 않음
        if not self.q_active and self.q_stacks < 8:
            self.q_stacks = min(8, self.q_stacks + 2)
            
        # 6. Q 활성화 시 다중 타겟 로직 (크라켄 가속 & 루난 확산)
        if self.q_active and self.target_count >= 2:
            # 6-1. 크라켄 스택 가속 (루난 없어도 적용)
            kraken = next((item for item in self.inventory if item.name == "Kraken Slayer"), None)
            if kraken:
                # 크라켄 대미지 계산 (KrakenSlayer.on_hit 참조)
                lvl = self.level
                min_dmg = 120
                max_dmg = 160
                if lvl < 8: base_dmg = min_dmg
                elif lvl >= 18: base_dmg = max_dmg
                else:
                    ratio = (lvl - 8) / (18 - 8)
                    base_dmg = min_dmg + (ratio * (max_dmg - min_dmg))
                
                current_hp_ratio = target.current_hp / target.max_hp
                missing_hp_ratio = 1.0 - current_hp_ratio
                saturation_point = 0.7
                max_bonus = 0.75
                if missing_hp_ratio >= saturation_point:
                    damage_multiplier = 1.0 + max_bonus
                else:
                    current_bonus = (missing_hp_ratio / saturation_point) * max_bonus
                    damage_multiplier = 1.0 + current_bonus
                
                kraken_dmg = base_dmg * damage_multiplier
                
                # 추가 빈도 계산
                extra_proc_rate = (min(3, self.target_count) - 1) / 3.0
                
                p_onhit += kraken_dmg * extra_proc_rate

            # 6-2. 루난 확산 대미지 (루난 있을 때만)
            has_runaan = any(item.name == "Runaan's Hurricane" for item in self.inventory)
            if has_runaan:
                sub_targets = min(2, self.target_count - 1)
                
                # 기본(AD) 계열 증폭: 1 + (0.55 * 0.3 * 서브타겟수)
                ad_multiplier = 1.0 + (0.55 * 0.3 * sub_targets)
                p_base *= ad_multiplier
                m_base *= ad_multiplier
                
                # 온힛 계열 증폭: 1 + (1.0 * 0.3 * 서브타겟수)
                onhit_multiplier = 1.0 + (1.0 * 0.3 * sub_targets)
                p_onhit *= onhit_multiplier
                m_onhit *= onhit_multiplier

        return p_base, m_base, p_onhit, m_onhit, pt_base, pt_onhit

    def activate_q(self, time):
        self.q_active = True
        self.q_start_time = time
        self.q_stacks = 0
        if not self.q_as_buff_applied:
            idx = self.q_level - 1
            as_bonus = self.q_as_amounts[idx]
            self.bonus_as_percent += as_bonus
            self.q_as_buff_applied = True
            self.cast_spell(time)
            self.cast_ultimate(time)

    def deactivate_q(self):
        self.q_active = False
        if self.q_as_buff_applied:
            idx = self.q_level - 1
            as_bonus = self.q_as_amounts[idx]
            self.bonus_as_percent -= as_bonus
            self.q_as_buff_applied = False


class KaiSa(Champion):
    def __init__(self, level=1, q_level=5, w_level=5, e_level=5, r_level=3):
        super().__init__(
            name="Kai'Sa",
            base_ad=59,
            base_as=0.644,
            as_ratio=0.644,
            as_growth=1.8,
            base_range=525,
            level=level,
            ad_growth=2.6
        )

        # 기본 스탯 (현재 엔진에서 직접 사용하지 않는 항목도 보관)
        self.base_hp = 640
        self.hp_growth = 102
        self.base_hp_regen = 4.0
        self.hp_regen_growth = 0.55
        self.base_mana = 345
        self.mana_growth = 40
        self.base_mana_regen = 8.2
        self.mana_regen_growth = 0.7
        self.base_armor = 25
        self.armor_growth = 4.2
        self.base_mr = 30
        self.mr_growth = 1.3
        self.base_ms = 335

        # 스킬 레벨
        self.q_level = q_level
        self.w_level = w_level
        self.e_level = e_level
        self.r_level = r_level

        # 스킬 데이터
        self.q_cd = [10, 9, 8, 7, 6]
        self.q_missile_base = [40, 55, 70, 85, 100]
        self.w_cd = [22, 20, 18, 16, 14]
        self.w_base = [30, 55, 80, 105, 130]
        self.e_cd = [16, 14.5, 13, 11.5, 10]
        self.e_as_bonus = [0.40, 0.50, 0.60, 0.70, 0.80]
        self.r_cd = [130, 100, 70]
        self.r_shield_base = [70, 90, 110]
        self.r_ad_ratio = [0.9, 1.35, 1.8]

        # 쿨타임/버프 상태
        self.cooldowns_remaining = {"q": 0.0, "w": 0.0, "e": 0.0, "r": 0.0}
        self.e_active = False
        self.e_end_time = 0.0
        self.e_buff_applied = False
        self.r_shield_value = 0.0
        self.r_shield_end_time = 0.0

        # 자동 시전 설정
        self.auto_cast_q = True
        self.auto_cast_w = True
        self.auto_cast_e = True
        self.auto_cast_r = False
        self.q_cast_count = 0
        self.w_cast_count = 0

        # 패시브(플라즈마) 및 스킬 스케줄 상태
        self.plasma_state = {}
        self.manual_skill_casts = []
        self.manual_skill_index = 0
        self.auto_skill_enabled = {"q": True, "w": True, "e": True, "r": False}
        self.auto_skill_order = ["q", "w", "e", "r"]

        # 시뮬레이션별 진화 오버라이드 (None이면 기본 조건 사용)
        self.q_evolved_override = None
        self.w_evolved_override = None

    def _lerp_by_level(self, lv1_value, lv18_value):
        if self.level <= 1:
            return lv1_value
        if self.level >= 18:
            return lv18_value
        ratio = (self.level - 1) / 17.0
        return lv1_value + (lv18_value - lv1_value) * ratio

    def _get_bonus_ad_for_scaling(self):
        # LoL 기준 bonus AD(아이템 + 성장 AD)에 가깝게 계산
        return self.bonus_ad + (self.ad_growth * (self.level - 1))

    def _get_evolution_bonus_as(self):
        # 진화 조건은 레벨/아이템 기반 추가 공속만 사용 (룬/버프 제외)
        return self.bonus_as_percent + (self.as_growth * (self.level - 1) / 100.0)

    def has_q_evolved(self):
        if self.q_evolved_override is not None:
            return self.q_evolved_override
        return self._get_bonus_ad_for_scaling() >= 100.0

    def has_w_evolved(self):
        if self.w_evolved_override is not None:
            return self.w_evolved_override
        return self.total_ap >= 100.0

    def has_e_evolved(self):
        return self._get_evolution_bonus_as() >= 1.0

    def _get_plasma(self, target, time):
        key = id(target)
        stacks, expire_time = self.plasma_state.get(key, (0, 0.0))
        if time > expire_time:
            stacks = 0
        return stacks, expire_time

    def _set_plasma(self, target, stacks, time):
        key = id(target)
        expire_time = time + 4.0 if stacks > 0 else 0.0
        self.plasma_state[key] = (stacks, expire_time)

    def _get_plasma_base_damage(self):
        # 4 ~ 24 (레벨 선형 보간) (+0.12 AP)
        return self._lerp_by_level(4.0, 24.0) + (0.12 * self.total_ap)

    def _get_plasma_per_stack_damage(self):
        # 1 ~ 6 (레벨 선형 보간) (+0.03 AP)
        return self._lerp_by_level(1.0, 6.0) + (0.03 * self.total_ap)

    def _get_plasma_execute_damage(self, target):
        # 잃은 체력의 15(+0.06 AP)% (마법)
        missing_hp = max(0.0, target.max_hp - target.current_hp)
        execute_ratio = 0.15 + (0.0006 * self.total_ap)
        detonate_damage = missing_hp * execute_ratio

        if getattr(target, 'is_monster', False):
            detonate_damage = min(detonate_damage, 400.0)

        return detonate_damage

    def _apply_single_plasma_stack(self, target, time, include_passive_damage=True):
        """
        플라즈마 1회 적용 시 피해:
        - 기본 공격 계열(include_passive_damage=True):
          기본 추가 피해 + 현재 중첩 기반 추가 피해
        - 스택 부여 계열(include_passive_damage=False, 예: W):
          스택/폭발만 처리
        - 4중첩 상태에서 다음(5번째) 적용이면 폭발 피해 후 중첩 초기화
        """
        pre_stacks, _ = self._get_plasma(target, time)
        damage = 0.0
        if include_passive_damage:
            damage += self._get_plasma_base_damage() + (self._get_plasma_per_stack_damage() * pre_stacks)

        # 5번째 적용 시 폭발
        if pre_stacks >= 4:
            damage += self._get_plasma_execute_damage(target)
            self._set_plasma(target, 0, time)
        else:
            self._set_plasma(target, pre_stacks + 1, time)

        return damage

    def _apply_plasma_stacks(self, target, time, count, include_passive_damage=True):
        total = 0.0
        for _ in range(count):
            total += self._apply_single_plasma_stack(target, time, include_passive_damage=include_passive_damage)
        return total

    def get_champion_onhit(self, target):
        # 패시브 온힛: 평타 1회당 플라즈마 1회 적용 피해
        time = self._combat_time
        return 0, self._apply_plasma_stacks(target, time, 1, include_passive_damage=True)

    def init_combat_state(self, skill_plan=None):
        super().init_combat_state(skill_plan)
        self.cooldowns_remaining = {"q": 0.0, "w": 0.0, "e": 0.0, "r": 0.0}
        self.e_active = False
        self.e_end_time = 0.0
        self.e_buff_applied = False
        self.r_shield_value = 0.0
        self.r_shield_end_time = 0.0
        self.plasma_state = {}
        self.q_cast_count = 0
        self.w_cast_count = 0

        plan = skill_plan or {}
        auto_cfg = plan.get("auto_cast", {})
        self.auto_skill_enabled = {
            "q": auto_cfg.get("q", self.auto_cast_q),
            "w": auto_cfg.get("w", self.auto_cast_w),
            "e": auto_cfg.get("e", self.auto_cast_e),
            "r": auto_cfg.get("r", self.auto_cast_r),
        }
        self.auto_skill_order = list(plan.get("auto_order", ["q", "w", "e", "r"]))
        self.manual_skill_casts = sorted(list(plan.get("manual_casts", [])), key=lambda x: x[0])
        self.manual_skill_index = 0

    def advance_combat_time(self, delta_time, current_time, target):
        super().advance_combat_time(delta_time, current_time, target)
        if delta_time > 0:
            for key in self.cooldowns_remaining:
                self.cooldowns_remaining[key] = max(0.0, self.cooldowns_remaining[key] - delta_time)

        # 버프 종료 처리
        if self.e_active and current_time >= self.e_end_time:
            self.e_active = False
            if self.e_buff_applied:
                idx = self.e_level - 1
                self.bonus_as_percent -= self.e_as_bonus[idx]
                self.e_buff_applied = False

        if self.r_shield_end_time and current_time >= self.r_shield_end_time:
            self.r_shield_value = 0.0
            self.r_shield_end_time = 0.0

    def _can_cast_skill(self, skill_name):
        eps = 1e-9
        if skill_name not in self.cooldowns_remaining:
            return False
        if self.cooldowns_remaining[skill_name] > eps:
            return False
        if skill_name == "e" and self.e_active:
            return False
        return True

    def _cast_skill(self, skill_name, target, time):
        if skill_name == "q":
            p, m = self._cast_q(time)
            return skill_name, p, m, True
        if skill_name == "w":
            p, m = self._cast_w(target, time)
            return skill_name, p, m, True
        if skill_name == "e":
            self._cast_e(time)
            return skill_name, 0.0, 0.0, False
        if skill_name == "r":
            self._cast_r(time)
            return skill_name, 0.0, 0.0, False
        return skill_name, 0.0, 0.0, False

    def _cast_q(self, time):
        idx = self.q_level - 1

        # 요청 반영:
        # 추가 공격력 = 현재 공격력(total_ad) - 1레벨 카이사 공격력(base_ad=59)
        bonus_ad_for_q = max(0.0, self.total_ad - self.base_ad)

        if self.has_q_evolved():
            # 진화 후 단일 대상 최대 피해
            # 150 / 206.25 / 262.5 / 318.75 / 375
            q_single_base_evolved = [150.0, 206.25, 262.5, 318.75, 375.0]
            q_damage = q_single_base_evolved[idx] + (1.875 * bonus_ad_for_q) + (0.75 * self.total_ap)
        else:
            # 진화 전 단일 대상 피해
            # 90 / 123.75 / 157.5 / 191.25 / 225
            q_single_base = [90.0, 123.75, 157.5, 191.25, 225.0]
            q_damage = q_single_base[idx] + (1.125 * bonus_ad_for_q) + (0.45 * self.total_ap)

        self.cooldowns_remaining["q"] = self.apply_haste_to_cooldown(self.q_cd[idx])
        self.q_cast_count += 1
        self.cast_spell(time)
        return q_damage, 0.0

    def _cast_w(self, target, time):
        idx = self.w_level - 1
        w_damage = self.w_base[idx] + (1.3 * self.total_ad) + (0.45 * self.total_ap)

        self.cooldowns_remaining["w"] = self.apply_haste_to_cooldown(self.w_cd[idx])
        if self.has_w_evolved():
            # 진화 W가 챔피언 적중 시 쿨타임 75% 환급 -> 남은 쿨타임 25%
            self.cooldowns_remaining["w"] = self.apply_haste_to_cooldown(self.w_cd[idx]) * 0.25

        self.w_cast_count += 1
        self.cast_spell(time)
        w_plasma_stacks = 3 if self.has_w_evolved() else 2
        plasma_magic = self._apply_plasma_stacks(target, time, w_plasma_stacks, include_passive_damage=True)
        return 0.0, w_damage + plasma_magic

    def _cast_e(self, time):
        idx = self.e_level - 1
        self.cooldowns_remaining["e"] = self.apply_haste_to_cooldown(self.e_cd[idx])
        self.e_active = True
        self.e_end_time = time + 4.0

        if not self.e_buff_applied:
            self.bonus_as_percent += self.e_as_bonus[idx]
            self.e_buff_applied = True

        self.cast_spell(time)

    def _cast_r(self, time):
        idx = self.r_level - 1
        self.cooldowns_remaining["r"] = self.apply_haste_to_cooldown(self.r_cd[idx])
        self.r_shield_value = self.r_shield_base[idx] + (self.r_ad_ratio[idx] * self.total_ad) + (1.2 * self.total_ap)
        self.r_shield_end_time = time + 2.0
        self.cast_spell(time)
        self.cast_ultimate(time)

    def get_time_to_next_skill_event(self, current_time):
        eps = 1e-9
        candidates = []

        if self.manual_skill_index < len(self.manual_skill_casts):
            next_manual_time, _ = self.manual_skill_casts[self.manual_skill_index]
            candidates.append(max(0.0, next_manual_time - current_time))

        for skill_name, enabled in self.auto_skill_enabled.items():
            if not enabled:
                continue
            if skill_name == "e" and self.e_active:
                continue
            remaining = self.cooldowns_remaining.get(skill_name, float("inf"))
            candidates.append(max(0.0, remaining))

        valid = [dt for dt in candidates if dt >= -eps]
        if not valid:
            return float("inf")
        return max(0.0, min(valid))

    def get_time_to_next_state_event(self, current_time):
        candidates = []
        if self.e_active:
            candidates.append(max(0.0, self.e_end_time - current_time))
        if self.r_shield_end_time:
            candidates.append(max(0.0, self.r_shield_end_time - current_time))
        if not candidates:
            return float("inf")
        return min(candidates)

    def pop_due_skill_events(self, current_time, target):
        eps = 1e-9
        events = []

        # 수동 스케줄 스킬
        while self.manual_skill_index < len(self.manual_skill_casts):
            cast_time, skill_name = self.manual_skill_casts[self.manual_skill_index]
            if cast_time > current_time + eps:
                break
            self.manual_skill_index += 1
            if self._can_cast_skill(skill_name):
                events.append(self._cast_skill(skill_name, target, current_time))

        # 자동 스킬
        for skill_name in self.auto_skill_order:
            if not self.auto_skill_enabled.get(skill_name, False):
                continue
            if self._can_cast_skill(skill_name):
                events.append(self._cast_skill(skill_name, target, current_time))

        return events

    def get_one_hit_damage(self, target, time=0):
        self._combat_time = time
        p_base, m_base, p_onhit, m_onhit, pt_base, pt_onhit = super().get_one_hit_damage(target, time)

        # E: 기본 공격 시 쿨타임 0.5초 감소
        self.cooldowns_remaining["e"] = max(0.0, self.cooldowns_remaining["e"] - 0.5)
        return p_base, m_base, p_onhit, m_onhit, pt_base, pt_onhit


class Corki(Champion):
    def __init__(self, level=1, q_level=5, e_level=5, r_level=3, w_level=5):
        super().__init__(
            name="Corki",
            base_ad=52,
            base_as=0.644,
            as_ratio=0.644,
            as_growth=2.8,
            base_range=550,
            level=level,
            ad_growth=2.0,
        )

        # 기본 스탯 보관
        self.base_hp = 610
        self.hp_growth = 100
        self.base_hp_regen = 5.5
        self.hp_regen_growth = 0.55
        self.base_mana = 350
        self.mana_growth = 40
        self.base_armor = 27
        self.armor_growth = 4.5
        self.base_mr = 30
        self.mr_growth = 1.3

        # 스킬 레벨
        self.q_level = q_level
        self.w_level = w_level
        self.e_level = e_level
        self.r_level = r_level

        # 자동 시전
        self.auto_cast_q = True
        self.auto_cast_w = True
        self.auto_cast_e = True
        self.auto_cast_r = True

        # Q: 인광탄
        self.q_cd = [9.0, 8.5, 8.0, 7.5, 7.0]
        self.q_base = [60.0, 105.0, 150.0, 195.0, 240.0]

        # W: 발키리 (경로 트레일이 0.5초당 마법 피해, 2.5초 지속 = 최대 5틱)
        # 가정(Hypothesis): 단일 고정 대상이 트레일 전체(5틱)를 맞는다고 본다.
        self.w_cd = [20.0, 18.0, 16.0, 14.0, 12.0]
        self.w_tick_base = [30.0, 45.0, 60.0, 75.0, 90.0]
        self.w_tick_bonus_ad = 0.4
        self.w_tick_ap = 0.3
        self.w_ticks = 5

        # E: 개틀링 건
        self.e_cd = 12.0
        self.e_base = [80.0, 130.0, 180.0, 230.0, 280.0]
        self.e_shred = [12.0, 14.0, 16.0, 18.0, 20.0]
        self.e_debuff_target = None
        self.e_debuff_end_time = 0.0
        self.e_debuff_armor = 0.0
        self.e_debuff_mr = 0.0

        # R: 미사일 폭격
        self.r_charge_cd = 20.0
        self.r_cast_cd = 2.0
        self.r_base = [90.0, 170.0, 250.0]
        self.r_initial_delay = 1.5
        self.r_charges = 4
        self.r_max_charges = 4
        self.r_charge_remaining = None
        self.cooldowns_remaining = {"q": 0.0, "w": 0.0, "e": 0.0, "r_cast": self.r_initial_delay}

        # 스킬 스케줄 상태
        self.manual_skill_casts = []
        self.manual_skill_index = 0
        self.auto_skill_enabled = {"e": True, "q": True, "w": True, "r": True}
        self.auto_skill_order = ["e", "q", "w", "r"]
        # 첫 4발을 강화-일반-일반-강화로 시작시키기 위해 2에서 시작
        self.r_missile_count = 2

    def _get_bonus_ad(self):
        return max(0.0, self.total_ad - self.base_attack_ad)

    def _cast_q(self, time):
        idx = self.q_level - 1
        damage = self.q_base[idx] + (1.25 * self._get_bonus_ad()) + (1.0 * self.total_ap)
        self.cooldowns_remaining["q"] = self.apply_haste_to_cooldown(self.q_cd[idx])
        self.cast_spell(time)
        return 0.0, damage

    def _cast_w(self, time):
        # 발키리 트레일: 0.5초당 [30~90] + 0.4 추가AD + 0.3 AP, 2.5초간 5틱.
        # 단일 고정 대상이 트레일 전체를 맞는다고 가정 → 한 번에 5틱 합산 마법 피해.
        idx = self.w_level - 1
        per_tick = self.w_tick_base[idx] + (self.w_tick_bonus_ad * self._get_bonus_ad()) + (self.w_tick_ap * self.total_ap)
        damage = per_tick * self.w_ticks
        self.cooldowns_remaining["w"] = self.apply_haste_to_cooldown(self.w_cd[idx])
        self.cast_spell(time)
        return 0.0, damage

    def _clear_e_debuff(self):
        if self.e_debuff_target is not None:
            self.e_debuff_target.armor += self.e_debuff_armor
            self.e_debuff_target.magic_resist += self.e_debuff_mr
        self.e_debuff_target = None
        self.e_debuff_end_time = 0.0
        self.e_debuff_armor = 0.0
        self.e_debuff_mr = 0.0

    def _cast_e(self, time, target):
        idx = self.e_level - 1
        damage = self.e_base[idx] + (2.4 * self._get_bonus_ad())
        shred = self.e_shred[idx]

        if self.e_debuff_target is not None:
            self._clear_e_debuff()

        target.armor = max(-99.0, target.armor - shred)
        target.magic_resist = max(-99.0, target.magic_resist - shred)
        self.e_debuff_target = target
        self.e_debuff_end_time = time + 2.0
        self.e_debuff_armor = shred
        self.e_debuff_mr = shred

        self.cooldowns_remaining["e"] = self.apply_haste_to_cooldown(self.e_cd)
        self.cast_spell(time)
        return damage, 0.0

    def _cast_r(self, time):
        if self.r_charges <= 0 or self.cooldowns_remaining["r_cast"] > 1e-9:
            return 0.0, 0.0

        idx = self.r_level - 1
        self.r_missile_count += 1
        is_big = (self.r_missile_count % 3 == 0)

        if is_big:
            damage = (self.r_base[idx] * 2.0) + (1.7 * self._get_bonus_ad())
        else:
            damage = self.r_base[idx] + (0.85 * self._get_bonus_ad())

        self.r_charges -= 1
        if self.r_charges < self.r_max_charges and self.r_charge_remaining is None:
            self.r_charge_remaining = self.apply_haste_to_cooldown(self.r_charge_cd)

        self.cooldowns_remaining["r_cast"] = self.apply_haste_to_cooldown(self.r_cast_cd)
        self.cast_spell(time)
        self.cast_ultimate(time)
        return damage, 0.0

    def _update_r_charges(self, delta_time):
        if self.r_charge_remaining is None:
            return
        self.r_charge_remaining -= delta_time
        while self.r_charges < self.r_max_charges and self.r_charge_remaining <= 1e-9:
            self.r_charges += 1
            if self.r_charges >= self.r_max_charges:
                self.r_charge_remaining = None
            else:
                self.r_charge_remaining += self.apply_haste_to_cooldown(self.r_charge_cd)

    def init_combat_state(self, skill_plan=None):
        super().init_combat_state(skill_plan)
        self.cooldowns_remaining = {"q": 0.0, "w": 0.0, "e": 0.0, "r_cast": self.r_initial_delay}
        self.e_debuff_target = None
        self.e_debuff_end_time = 0.0
        self.e_debuff_armor = 0.0
        self.e_debuff_mr = 0.0
        self.r_charges = self.r_max_charges
        self.r_charge_remaining = None
        self.r_missile_count = 2

        plan = skill_plan or {}
        auto_cfg = plan.get("auto_cast", {})
        self.auto_skill_enabled = {
            "e": auto_cfg.get("e", self.auto_cast_e),
            "q": auto_cfg.get("q", self.auto_cast_q),
            "w": auto_cfg.get("w", self.auto_cast_w),
            "r": auto_cfg.get("r", self.auto_cast_r),
        }
        self.auto_skill_order = list(plan.get("auto_order", ["e", "q", "w", "r"]))
        self.manual_skill_casts = sorted(list(plan.get("manual_casts", [])), key=lambda x: x[0])
        self.manual_skill_index = 0

    def advance_combat_time(self, delta_time, current_time, target):
        super().advance_combat_time(delta_time, current_time, target)
        if delta_time > 0:
            for key in self.cooldowns_remaining:
                self.cooldowns_remaining[key] = max(0.0, self.cooldowns_remaining[key] - delta_time)

        if self.e_debuff_target is not None and current_time >= self.e_debuff_end_time:
            self._clear_e_debuff()

        self._update_r_charges(delta_time)

    def _can_cast_skill(self, skill_name):
        eps = 1e-9
        if skill_name == "r":
            return self.r_charges > 0 and self.cooldowns_remaining["r_cast"] <= eps
        if skill_name == "q":
            return self.cooldowns_remaining["q"] <= eps
        if skill_name == "w":
            return self.cooldowns_remaining["w"] <= eps
        if skill_name == "e":
            return self.cooldowns_remaining["e"] <= eps
        return False

    def _cast_skill(self, skill_name, target, time):
        if skill_name == "q":
            p, m = self._cast_q(time)
            return skill_name, p, m, True
        if skill_name == "w":
            p, m = self._cast_w(time)
            return skill_name, p, m, True
        if skill_name == "e":
            p, m = self._cast_e(time, target)
            return skill_name, p, m, True
        if skill_name == "r":
            p, m = self._cast_r(time)
            return skill_name, p, m, True
        return skill_name, 0.0, 0.0, False

    def get_time_to_next_skill_event(self, current_time):
        eps = 1e-9
        candidates = []

        if self.manual_skill_index < len(self.manual_skill_casts):
            next_manual_time, _ = self.manual_skill_casts[self.manual_skill_index]
            candidates.append(max(0.0, next_manual_time - current_time))

        if self.auto_skill_enabled.get("e", False):
            candidates.append(max(0.0, self.cooldowns_remaining["e"]))
        if self.auto_skill_enabled.get("q", False):
            candidates.append(max(0.0, self.cooldowns_remaining["q"]))
        if self.auto_skill_enabled.get("w", False):
            candidates.append(max(0.0, self.cooldowns_remaining["w"]))
        if self.auto_skill_enabled.get("r", False) and self.r_charges > 0:
            candidates.append(max(0.0, self.cooldowns_remaining["r_cast"]))

        valid = [dt for dt in candidates if dt >= -eps]
        if not valid:
            return float("inf")
        return max(0.0, min(valid))

    def get_time_to_next_state_event(self, current_time):
        candidates = []
        if self.r_charge_remaining is not None:
            candidates.append(max(0.0, self.r_charge_remaining))
        if self.e_debuff_target is not None:
            candidates.append(max(0.0, self.e_debuff_end_time - current_time))
        if not candidates:
            return float("inf")
        return min(candidates)

    def pop_due_skill_events(self, current_time, target):
        eps = 1e-9
        events = []

        while self.manual_skill_index < len(self.manual_skill_casts):
            cast_time, skill_name = self.manual_skill_casts[self.manual_skill_index]
            if cast_time > current_time + eps:
                break
            self.manual_skill_index += 1
            if self._can_cast_skill(skill_name):
                events.append(self._cast_skill(skill_name, target, current_time))

        for skill_name in self.auto_skill_order:
            if not self.auto_skill_enabled.get(skill_name, False):
                continue
            if self._can_cast_skill(skill_name):
                events.append(self._cast_skill(skill_name, target, current_time))

        return events

    def get_one_hit_damage(self, target, time=0):
        self._combat_time = time
        p_base, m_base, p_onhit, m_onhit, pt_base, pt_onhit = super().get_one_hit_damage(target, time)

        # 패시브: 기본 공격/주문검 대미지의 20% 고정 피해
        spellblade_phys = 0.0
        for item in self.inventory:
            spellblade_phys += getattr(item, "last_spellblade_damage", 0.0)
        pt_base += 0.2 * (p_base + spellblade_phys)

        # R 충전시간 단축: 챔피언 대상 기본 공격 적중 시
        if self.r_charges < self.r_max_charges and self.r_charge_remaining is not None:
            reduction = 2.0 + (self.crit_damage_modifier * 2.0)
            self.r_charge_remaining = max(0.0, self.r_charge_remaining - reduction)
            self._update_r_charges(0.0)

        return p_base, m_base, p_onhit, m_onhit, pt_base, pt_onhit


class Ezreal(Champion):
    """이즈리얼 — 스킬샷 포크형 원딜. [Hypothesis 다수 — 스펙 §9 참조]

    모델: 평타 연속 + Q/W/E 쿨마다 시전(R 제외). 마나 자원 미모델(무한마나)이나
    마나무네 스택은 on_hit/on_skill_hit로 정확 충전됨.
    - 패시브 Rising Spell Force[H]: 스킬 적중당 공속 +10%/스택, 최대 5, 6초(적중 시 갱신).
    - Q Mystic Shot[H]: 물리(비치명) base + 1.30*총AD + 0.15*AP. 적중 시 전 스킬 −1.5초.
      온힛 적용(Manamune/Muramana·룬=엔진 스킬경로; Kraken/BotRK/Guinsoo/Terminus/Nashor's/
      Wit's End=allow-list 로컬). 주문검은 장전만(다음 평타서 발동).
    - W Essence Flux[H]: 마법 base + 1.0*추가AD + 0.9*AP(단일 더미 즉시 기폭 단순화).
    - E Arcane Shift[H]: 마법 base + 0.6*추가AD + 0.75*AP.
    수치/가설 출처: docs/superpowers/specs/2026-06-24-ezreal-design.md
    """

    # Q 온힛 allow-list(이름 기준). Manamune(스킬경로)/주문검(평타)/에너자이즈드(평타) 제외.
    Q_ONHIT_ALLOW = {
        "Kraken Slayer", "Blade of the Ruined King", "Guinsoo's Rageblade",
        "Terminus", "Nashor's Tooth", "Wit's End",
    }

    def __init__(self, level=1, q_level=5, w_level=5, e_level=5, r_level=3):
        super().__init__(
            name="Ezreal", base_ad=60, base_as=0.625, as_ratio=0.625,
            as_growth=2.5, base_range=550, level=level, ad_growth=3.75,
        )
        # 보관(비-DPS): 미래 1대1 모델용
        self.base_hp = 600; self.hp_growth = 102
        self.base_mana = 375; self.mana_growth = 70
        self.base_armor = 24; self.armor_growth = 4.2
        self.base_mr = 30; self.mr_growth = 1.3

        self.q_level = q_level; self.w_level = w_level
        self.e_level = e_level; self.r_level = r_level

        # 패시브 Rising Spell Force [H]
        self.spell_stacks = 0
        self.max_spell_stacks = 5
        self.spell_stack_as = 0.10        # 스택당 공속
        self.spell_stack_duration = 6.0
        self.stack_expire_time = 0.0
        self._stack_as_applied = 0.0      # 현재 bonus_as_percent에 반영된 패시브 공속(환원용)

        # Q/W/E 데이터 [H]
        self.q_cd = [5.5, 5.25, 5.0, 4.75, 4.5]
        self.q_base = [20.0, 45.0, 70.0, 95.0, 120.0]
        self.q_total_ad_ratio = 1.30
        self.q_ap_ratio = 0.15
        self.q_cd_refund = 1.5

        self.w_cd = [8.0, 8.0, 8.0, 8.0, 8.0]
        self.w_base = [80.0, 135.0, 190.0, 245.0, 300.0]
        self.w_bonus_ad_ratio = 1.0
        self.w_ap_ratio = 0.9

        self.e_cd = [26.0, 23.0, 20.0, 17.0, 14.0]
        self.e_base = [80.0, 130.0, 180.0, 230.0, 280.0]
        self.e_bonus_ad_ratio = 0.6
        self.e_ap_ratio = 0.75

        # 자동 시전(R 제외)
        self.auto_cast_q = True; self.auto_cast_w = True; self.auto_cast_e = True
        self.cooldowns_remaining = {"q": 0.0, "w": 0.0, "e": 0.0}
        self.manual_skill_casts = []
        self.manual_skill_index = 0
        self.auto_skill_enabled = {"q": True, "w": True, "e": True}
        self.auto_skill_order = ["q", "w", "e"]

    # ---- 추가AD(W/E 계수용) ----
    def _bonus_ad(self):
        """아이템+동적(마나무네 경탄 등) 추가 AD = total_ad - 현재레벨 기본 AD."""
        return max(0.0, self.total_ad - self.base_attack_ad)

    # ---- 패시브 스택 ----
    def _sync_stack_as(self):
        """현재 스택 수에 맞춰 bonus_as_percent 보정(이전 적용분 환원 후 재적용)."""
        target_as = self.spell_stacks * self.spell_stack_as
        delta = target_as - self._stack_as_applied
        if delta != 0.0:
            self.bonus_as_percent += delta
            self._stack_as_applied = target_as

    def _add_spell_stack(self, time):
        """스킬 적중 1회 → 스택 +1(캡), 만료시간 갱신, 공속 반영. [H]"""
        self.spell_stacks = min(self.max_spell_stacks, self.spell_stacks + 1)
        self.stack_expire_time = time + self.spell_stack_duration
        self._sync_stack_as()

    def _expire_stacks_if_due(self, time):
        """만료시간 경과 시 스택 0 + 공속 환원."""
        if self.spell_stacks > 0 and time >= self.stack_expire_time:
            self.spell_stacks = 0
            self._sync_stack_as()

    # ---- 이벤트 인터페이스 ----
    def init_combat_state(self, skill_plan=None):
        super().init_combat_state(skill_plan)
        self.cooldowns_remaining = {"q": 0.0, "w": 0.0, "e": 0.0}
        # 패시브 초기화(이전 전투 잔여 공속 환원)
        self.spell_stacks = 0
        self.stack_expire_time = 0.0
        self._sync_stack_as()  # _stack_as_applied 만큼 환원
        self._stack_as_applied = 0.0

        plan = skill_plan or {}
        auto_cfg = plan.get("auto_cast", {})
        self.auto_skill_enabled = {
            "q": auto_cfg.get("q", self.auto_cast_q),
            "w": auto_cfg.get("w", self.auto_cast_w),
            "e": auto_cfg.get("e", self.auto_cast_e),
        }
        self.auto_skill_order = list(plan.get("auto_order", ["q", "w", "e"]))
        self.manual_skill_casts = sorted(list(plan.get("manual_casts", [])), key=lambda x: x[0])
        self.manual_skill_index = 0

    def advance_combat_time(self, delta_time, current_time, target):
        super().advance_combat_time(delta_time, current_time, target)
        if delta_time > 0:
            for k in self.cooldowns_remaining:
                self.cooldowns_remaining[k] = max(0.0, self.cooldowns_remaining[k] - delta_time)
        self._expire_stacks_if_due(current_time)

    def get_time_to_next_state_event(self, current_time):
        if self.spell_stacks > 0:
            return max(0.0, self.stack_expire_time - current_time)
        return float("inf")

    def _can_cast(self, name):
        return self.cooldowns_remaining.get(name, float("inf")) <= 1e-9

    def get_time_to_next_skill_event(self, current_time):
        eps = 1e-9
        candidates = []
        if self.manual_skill_index < len(self.manual_skill_casts):
            t, _ = self.manual_skill_casts[self.manual_skill_index]
            candidates.append(max(0.0, t - current_time))
        for name, enabled in self.auto_skill_enabled.items():
            if enabled:
                candidates.append(max(0.0, self.cooldowns_remaining.get(name, float("inf"))))
        valid = [dt for dt in candidates if dt >= -eps]
        return max(0.0, min(valid)) if valid else float("inf")

    def pop_due_skill_events(self, current_time, target):
        eps = 1e-9
        events = []
        while self.manual_skill_index < len(self.manual_skill_casts):
            t, name = self.manual_skill_casts[self.manual_skill_index]
            if t > current_time + eps:
                break
            self.manual_skill_index += 1
            if self._can_cast(name):
                events.append(self._cast_skill(name, target, current_time))
        for name in self.auto_skill_order:
            if self.auto_skill_enabled.get(name, False) and self._can_cast(name):
                events.append(self._cast_skill(name, target, current_time))
        return events

    def _cast_skill(self, name, target, time):
        if name == "q":
            p, m = self._cast_q(target, time)
            return ("q", p, m, True)
        if name == "w":
            p, m = self._cast_w(time)
            return ("w", p, m, True)
        if name == "e":
            p, m = self._cast_e(time)
            return ("e", p, m, True)
        return (name, 0.0, 0.0, False)

    def _assemble_q_onhit(self, target):
        """Q에 적용할 평타 온힛 중 allow-list 아이템만 합산. [Hypothesis H-EZ-6]

        - Manamune/Muramana: 엔진 스킬경로(on_skill_hit)가 처리 → 여기서 제외(이중계산 방지).
        - 주문검/에너자이즈드: Q서 미적용(주문검은 _cast_q의 cast_spell로 장전만).
        - proc_count(구인수 팬텀히트)는 평타 경로와 동일하게 allow-list 번들 전체에 적용.
        - 현 allow-list 아이템은 고정(true) 온힛이 없어 (phys,magic)만 합산(검증됨).
        반환: (phys, magic)
        """
        def bundle_once():
            p = 0.0; m = 0.0
            for item in self.inventory:
                if item.name in self.Q_ONHIT_ALLOW:
                    ip, im, _t_base, _t_onhit = item.on_hit(target, self)
                    p += ip; m += im
            return p, m

        proc = 1
        for item in self.inventory:
            if item.name in self.Q_ONHIT_ALLOW and hasattr(item, "get_onhit_proc_count"):
                proc = max(proc, item.get_onhit_proc_count(self))

        phys = 0.0; magic = 0.0
        for _ in range(proc):
            bp, bm = bundle_once()
            phys += bp; magic += bm
        return phys, magic

    def _cast_q(self, target, time):
        """Q Mystic Shot. 물리(비치명) + allow-list 온힛. 적중 시 전 스킬 −1.5초. [H]

        반환: (phys, magic). Manamune/Muramana·룬 스킬훅은 엔진 스킬경로가 자동 처리.
        """
        self._combat_time = time
        idx = self.q_level - 1
        q_phys = self.q_base[idx] + (self.q_total_ad_ratio * self.total_ad) + (self.q_ap_ratio * self.total_ap)

        # allow-list 온힛(주문검/Manamune 제외)
        onhit_p, onhit_m = self._assemble_q_onhit(target)

        # 자기 쿨 설정 후, 적중 쿨 환급(−1.5초)을 전 스킬에 적용(자기 포함)
        self.cooldowns_remaining["q"] = self.apply_haste_to_cooldown(self.q_cd[idx])
        for k in self.cooldowns_remaining:
            self.cooldowns_remaining[k] = max(0.0, self.cooldowns_remaining[k] - self.q_cd_refund)

        # 주문검 장전(다음 평타서 발동)
        self.cast_spell(time)
        # 패시브 스택
        self._add_spell_stack(time)

        return q_phys + onhit_p, onhit_m

    def _cast_w(self, time):
        """W Essence Flux — 단일 더미 즉시 기폭 단순화. 마법. [H]"""
        self._combat_time = time
        idx = self.w_level - 1
        magic = self.w_base[idx] + (self.w_bonus_ad_ratio * self._bonus_ad()) + (self.w_ap_ratio * self.total_ap)
        self.cooldowns_remaining["w"] = self.apply_haste_to_cooldown(self.w_cd[idx])
        self.cast_spell(time)      # 주문검 장전
        self._add_spell_stack(time)
        return 0.0, magic

    def _cast_e(self, time):
        """E Arcane Shift — 순간이동 후 마법 볼트. [H]"""
        self._combat_time = time
        idx = self.e_level - 1
        magic = self.e_base[idx] + (self.e_bonus_ad_ratio * self._bonus_ad()) + (self.e_ap_ratio * self.total_ap)
        self.cooldowns_remaining["e"] = self.apply_haste_to_cooldown(self.e_cd[idx])
        self.cast_spell(time)      # 주문검 장전
        self._add_spell_stack(time)
        return 0.0, magic

    def get_one_hit_damage(self, target, time=0):
        # 평타 시점에 패시브 만료 동기화 후 부모 평타 로직(치명/주문검발동/온힛/증폭).
        self._expire_stacks_if_due(time)
        return super().get_one_hit_damage(target, time)
