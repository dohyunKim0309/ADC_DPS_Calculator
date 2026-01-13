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
    def __init__(self, name, base_ad, base_as, as_ratio, as_growth, level=1):
        self.name = name
        self.level = level

        # 기본 능력치
        self.base_ad = base_ad
        self.base_as = base_as
        self.as_ratio = as_ratio         # 공격 속도 계수
        self.as_growth = as_growth       # 레벨당 공속 증가량 (%)

        self.crit_chance = 0             # 치명타 확률

        # 인벤토리 및 상태
        self.inventory = []  # Item 객체들이 저장될 리스트
        self.hit_count = 0  # 평타 횟수 (구인수, 크라켄 등 카운팅용)

        # 동적 스탯 (아이템으로 인해 변함)
        self.bonus_ad = 0
        self.bonus_ap = 0
        self.bonus_as_percent = 0
        self.crit_chance = 0.0
        self.crit_damage_modifier = 1.75  # 기본 치명타 피해 175%
        self.armor_pen_percent = 0.0  # 방관 %
        self.lethality = 0  # 물리 관통력 (고정)

    # 아이템 장착 함수
    def add_item(self, item):
        self.inventory.append(item)

        # 1. 스탯 단순 합산
        self.bonus_ad += item.stats.get('ad', 0)
        self.bonus_as_percent += item.stats.get('as', 0)
        self.crit_chance += item.stats.get('crit', 0)
        self.armor_pen_percent = 1 - (1 - self.armor_pen_percent) * (
                    1 - item.stats.get('armor_pen_percent', 0))  # 방관은 곱연산 적용이 정확하나 여기선 단순화 가능
        self.lethality += item.stats.get('lethality', 0)
        self.crit_damage_modifier += item.stats.get('add_crit_damage', 0)

        # 2. 고유 패시브 적용 (무한의 대검 등)
        item.apply_passive(self)

    @property
    def total_ad(self):
        return self.base_ad + self.bonus_ad

    @property
    def total_ap(self):
        return self.bonus_ap

    @property
    def current_attack_speed(self):
        # 추가 공격속도 = (레벨업 보너스) + (아이템 보너스)
        # 일반적으로 레벨업 보너스는 (level-1) * 성장공속
        level_bonus = (self.as_growth * (self.level - 1)) / 100
        total_bonus = level_bonus + self.bonus_as_percent

        # 공식: 기본공속 + (공속계수 * 추가공속)
        final_as = self.base_as + (self.as_ratio * total_bonus)
        return round(final_as, 3)  # 소수점 3자리 반올림

    def get_attack_interval(self):
        # 초당 공격 횟수의 역수 = 공격 간격 (초)
        # 공속이 0이면 무한대 방지
        current_as = self.current_attack_speed
        if current_as <= 0: return 9999
        return 1.0 / current_as

    # [핵심] 챔피언별로 오버라이딩 할 메서드
    # 반환값: (물리_기본, 마법_기본, 물리_온힛, 마법_온힛)
    def get_one_hit_damage(self, target):
        # 1. 기본 물리 피해 계산
        phys_base = self.total_ad * self.crit_damage_modifier * self.crit_chance + self.total_ad * (
                    1 - self.crit_chance)
        magic_base = 0

        # ---------------------------------------------------------
        # 2. 아이템 온힛 대미지 및 구인수 로직 처리
        # ---------------------------------------------------------

        # 2.0 내부 함수: 현재 인벤토리의 모든 온힛 효과를 한 번 실행하고 합산
        def get_item_onhit():
            p_sum = 0
            m_sum = 0
            for item in self.inventory:
                p, m = item.on_hit(target, self)
                p_sum += p
                m_sum += m
            return p_sum, m_sum

        # 2.1 구인수 객체 찾기 및 상태 확인
        guinsoo_item = next((item for item in self.inventory if getattr(item, 'is_guinsoo', False)), None)

        # [조건] 구인수가 있고 + 스택이 4(풀스택)여야 함
        is_guinsoo_active = (guinsoo_item is not None) and (guinsoo_item.stack >= 4)

        # 2.2 실행 횟수(proc_count) 결정
        proc_count = 1

        # 구인수 풀스택 상태에서, 3번째 평타마다 2회 발동
        # !! 다만, hit_count는 시뮬레이션 전체에서 상대를 몇 번 때렸느냐이기 때문에, 상대를 쉬었다 때리는 것은 고려하지 않음.
        # !! 또 구인수 4스택이 모두 쌓인 후부터 3번마다 적용하는 게 맞지만, 편의상 3의 배수로 만들어서 적용함.
        if is_guinsoo_active and (self.hit_count > 0) and (self.hit_count % 3 == 0):
            proc_count = 2

        # 2.3 결정된 횟수만큼 온힛 루프 실행
        # (크라켄 슬레이어 스택도 이 루프 안에서 2번 쌓이거나 터지게 됨)
        total_phys_onhit = 0
        total_magic_onhit = 0

        for _ in range(proc_count):
            p, m = get_item_onhit()
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

        # 4. 평타 횟수 증가
        self.hit_count += 1

        # 5. 최종 반환
        return phys_base, magic_base, total_phys_onhit, total_magic_onhit


# 3. 개별 챔피언 구현 (예: 애쉬, 케이틀린)
class Ashe(Champion):
    def __init__(self, level=1):
        # 애쉬 예시 스탯 (가상)
        super().__init__(name="Ashe", base_ad=59, base_as=0.658, as_ratio=0.658, as_growth=2.95, level=level)

    def get_one_hit_damage(self, target):
        ...


# 4. 시뮬레이션 엔진
def calculate_mitigation(phys_damage, magic_damage, ar, mr):
    """방어력/마법저항력 계산 공식: 100 / (100 + 저항력)"""
    ar_modifier = 100.0 / (100.0 + ar)
    mr_modifier = 100.0 / (100.0 + mr)
    return phys_damage * ar_modifier, magic_damage * mr_modifier


def run_simulation(champion: Champion, target: Target, verbose=True):
    current_time = 0.0
    history = []  # (시간, 남은체력) 기록
    attack_count = 0

    # 시뮬레이션 시작 전 초기 상태 기록
    history.append((0.0, target.current_hp))

    print(f"--- Simulation Start: {champion.name} vs Dummy ---")
    print(f"Stats - AD: {champion.total_ad}, AS: {champion.current_attack_speed}")

    while target.current_hp > 0:
        # 1. 대미지 성분 계산 (챔피언 클래스 내부 로직)
        p_base, m_base, p_onhit, m_onhit = champion.get_one_hit_damage(target)

        # 2. 방어력/마저 적용 (시뮬레이션 로직)
        # 물리 피해 합산 (기본 + 온힛) -> 방어력 적용
        raw_phys = p_base + p_onhit
        actual_phys = calculate_mitigation(raw_phys, target.armor)

        # 마법 피해 합산 (기본 + 온힛) -> 마저 적용
        raw_magic = m_base + m_onhit
        actual_magic = calculate_mitigation(raw_magic, target.magic_resist)

        total_damage = actual_phys + actual_magic

        # 3. 체력 차감
        target.current_hp -= total_damage
        attack_count += 1

        if verbose:
            print(
                f"[{current_time:.2f}s] Attack #{attack_count}: Dmg {total_damage:.1f} (Phys:{actual_phys:.1f}, Mag:{actual_magic:.1f}) -> HP: {max(0, target.current_hp):.1f}")

        # 4. 시간 경과 기록 (체력이 0이 되어도 이번 공격은 들어간 것으로 처리하고 시간 흐름)
        # 다음 공격까지의 딜레이 계산
        attack_interval = champion.get_attack_interval()
        current_time += attack_interval

        # 기록 (0 이하일 경우 0으로 기록)
        recorded_hp = max(0, target.current_hp)
        history.append((round(current_time, 2), recorded_hp))

    # 결과 요약
    dps = target.max_hp / current_time if current_time > 0 else 0
    print(f"--- Killed in {current_time:.2f}s | DPS: {dps:.2f} ---")

    return history, dps


# --- 메인 실행부 예시 ---
if __name__ == "__main__":
    # 1. 적 설정 (체력 2000, 방어 200, 마저 100)
    dummy = Target(hp=2000, armor=200, magic_resist=100)

    # 2. 챔피언 설정 (애쉬, 18레벨 가정)
    my_ashe = Ashe(level=18)

    # 아이템 장착 시뮬레이션 (예: 공격력 100, 공속 50% 추가)
    my_ashe.bonus_ad = 100
    my_ashe.bonus_as_percent = 0.5  # 50%

    # 3. 시뮬레이션 실행
    history_data, final_dps = run_simulation(my_ashe, dummy)

    # (선택 사항) 그래프 그리기
    # times, hps = zip(*history_data)
    # plt.plot(times, hps)
    # plt.show()