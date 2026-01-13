import math

# ==========================================
# 1. 설정값 (Constants & Specs)
# ==========================================

# 챔피언: 유나라 (13레벨)
LEVEL = 13
BASE_AD = 55.0 + (2.5 * (LEVEL - 1))  # 85
BASE_AS = 0.65
AS_RATIO = 0.65
BONUS_AS_LVL = 0.02 * (LEVEL - 1)  # 24%

# 적 챔피언 (브루저/탱커 급)
TARGET_HP = 3000
TARGET_ARMOR = 100
TARGET_MR = 100

# 아이템 데이터베이스 (논의된 최신 스펙)
ITEMS = {
    "Nashor": {"ap": 90, "as": 0.50, "onhit_base": 15, "onhit_ratio": 0.20},
    "Guinsoo": {"ad": 30, "ap": 30, "as": 0.25, "onhit_flat": 30},  # 스택당 공속 8% (Max 32%)
    "Kraken": {"ad": 45, "as": 0.40, "ms": 0.04},  # 3타 proc: 140~250 (13렙 기준 약 200 + 0.4AD 가정)
    "Terminus": {"ad": 30, "as": 0.35, "onhit_flat": 30},  # 스택형 관통
    "Rabadon": {"ap": 140, "amp": 0.35},
    "Shadowflame": {"ap": 120, "pen_flat": 12},  # 마법 치명타 가설 적용
    "Berserker": {"as": 0.35},  # 신발
    "BoRK": {"ad": 40, "as": 0.25, "hp_cut": 0.06},  # 현재체력 6%
}


# ==========================================
# 2. 시뮬레이션 클래스
# ==========================================

class YunaraSim:
    def __init__(self, build_names):
        self.build_names = build_names
        self.time = 0.0
        self.total_dmg = 0.0

        # 스탯 초기화
        self.bonus_ad = 0.0
        self.bonus_ap = 0.0
        self.bonus_as = 0.0  # 아이템 합산
        self.crit_chance = 0.0  # 기본 0, 아이템 추가 시
        self.crit_dmg_add = 0.0  # 무대 등
        self.flat_magic_pen = 0.0  # 그불
        self.ap_amp = 1.0  # 라바돈

        # 상태 변수
        self.q_stacks = 0  # 4스택 시 활성화
        self.q_active = False
        self.q_duration = 0.0  # 활성화 지속시간

        self.guinsoo_stacks = 0  # 0~4
        self.guinsoo_phantom = 0  # 0~2 (3타째 발동)

        self.kraken_stacks = 0  # 0~2

        self.terminus_stacks = 0  # 0~6

        # 아이템 스탯 적용
        for name in build_names:
            item = ITEMS.get(name, {})
            self.bonus_ad += item.get("ad", 0)
            self.bonus_ap += item.get("ap", 0)
            self.bonus_as += item.get("as", 0)
            self.flat_magic_pen += item.get("pen_flat", 0)
            if "amp" in item: self.ap_amp += item["amp"]
            # 치명타 확률/대미지 아이템이 있다면 여기서 추가 (현재 리스트엔 없음, 무대 추가 시 로직 필요)

        # 적 상태
        self.target_hp = TARGET_HP
        self.target_max_hp = TARGET_HP

    def get_stats(self):
        total_ad = BASE_AD + self.bonus_ad
        total_ap = self.bonus_ap * self.ap_amp

        # 공속 계산
        # 유나라 Q 활성화 시 65% 추가
        q_as = 0.65 if self.q_active else 0.0
        # 구인수 스택 (스택당 8%, 최대 32%)
        g_as = 0.08 * self.guinsoo_stacks if "Guinsoo" in self.build_names else 0.0

        total_bonus_as = BONUS_AS_LVL + self.bonus_as + q_as + g_as
        current_as = BASE_AS + (AS_RATIO * total_bonus_as)
        return total_ad, total_ap, min(2.5, current_as)

    def calculate_mitigation(self, raw_dmg, armor, mr, is_magic):
        # 관통력 계산
        # 1. 경계(Terminus) % 관통
        term_pen = 0.0
        if "Terminus" in self.build_names:
            if self.terminus_stacks >= 5:
                term_pen = 0.30
            elif self.terminus_stacks >= 3:
                term_pen = 0.20
            elif self.terminus_stacks >= 1:
                term_pen = 0.10

        eff_armor = armor * (1 - term_pen)
        eff_mr = mr * (1 - term_pen)

        if is_magic:
            # 2. 그림자불꽃 고정 관통 (Flat Pen)
            eff_mr = max(0, eff_mr - self.flat_magic_pen)
            mitigation = 100 / (100 + eff_mr)
        else:
            mitigation = 100 / (100 + eff_armor)

        return raw_dmg * mitigation

    def hit_damage(self, is_phantom=False):
        ad, ap, _ = self.get_stats()

        dmg_log = 0.0

        # ===========================
        # A. 물리 대미지 (평타)
        # ===========================
        if not is_phantom:  # 환영 타격은 물리 평타 데미지 없음
            # 치명타 기댓값 (현재 치명타템 없으면 0%)
            crit_chance = self.crit_chance
            crit_mult = 1.75 + self.crit_dmg_add

            phys_avg = (ad * (1 - crit_chance)) + (ad * crit_mult * crit_chance)
            dmg_log += self.calculate_mitigation(phys_avg, TARGET_ARMOR, TARGET_MR, False)

        # ===========================
        # B. 온힛 대미지 (마법/물리)
        # ===========================
        # 1. Q 온힛 (마법)
        # 비활성: 25+0.25AP / 활성: 50+0.5AP
        if self.q_active:
            q_onhit = 50 + (0.5 * ap)
        else:
            q_onhit = 25 + (0.25 * ap)

        # 2. 아이템 온힛
        item_magic_onhit = 0.0
        item_phys_onhit = 0.0

        if "Nashor" in self.build_names:
            item_magic_onhit += 15 + (0.2 * ap)
        if "Guinsoo" in self.build_names:
            item_magic_onhit += 30
        if "Terminus" in self.build_names:
            item_magic_onhit += 30
        if "BoRK" in self.build_names:
            item_phys_onhit += max(15, self.target_hp * 0.06)

        # ===========================
        # C. 유나라 패시브 (마법 치명타)
        # ===========================
        # 공식: {0.1 + 0.001*AP} * CritMult * AD
        # 이는 "온힛"이 아니라 "공격 시 발동 효과"이므로 구인수 환영타격 대상 X (사용자 정의)
        magic_crit_bonus = 0.0
        if not is_phantom and self.crit_chance > 0:
            crit_mult = 1.75 + self.crit_dmg_add
            passive_dmg = (0.1 + 0.001 * ap) * crit_mult * ad
            # 기댓값 적용
            magic_crit_bonus = passive_dmg * self.crit_chance

        # ===========================
        # D. 그림자불꽃 & 특수 연산
        # ===========================
        # 가설: 그불 보유 시 마법 대미지(온힛 포함)가 증폭됨
        # 조건: 체력 35% 이하 혹은 "그불 버그" 가정 시 상시 적용?
        # -> 일단 "체력 35% 이하일 때 치명타(1.2배) 적용"을 정석으로 하되,
        # 사용자가 언급한 "재귀적 증폭"은 1.2가 아니라 더 크게 들어가는 것으로 시뮬레이션.

        magic_total = q_onhit + item_magic_onhit + magic_crit_bonus

        sf_mult = 1.0
        if "Shadowflame" in self.build_names:
            # 체력 35% 이하일 때 발동 (시뮬레이션 정교화)
            if (self.target_hp / self.target_max_hp) <= 0.35:
                sf_mult = 1.2  # 기본 20% 증가
                # 여기에 유나라 패시브와 결합된 "재귀 버그"가 있다면?
                # 사용자 요청: "재귀적 치명타 뻥튀기". 즉 1.2 * 1.2 느낌 혹은 그 이상.
                # 일단 1.25(25% 증폭) 정도로 보정해서 넣겠습니다.
                sf_mult = 1.25

        magic_total *= sf_mult

        # 적용
        dmg_log += self.calculate_mitigation(magic_total, TARGET_ARMOR, TARGET_MR, True)
        dmg_log += self.calculate_mitigation(item_phys_onhit, TARGET_ARMOR, TARGET_MR, False)

        # ===========================
        # E. 크라켄 학살자 (물리)
        # ===========================
        if "Kraken" in self.build_names:
            self.kraken_stacks += 1
            if self.kraken_stacks >= 3:
                # 13레벨 기준 약 200 + 0.4 추가 AD
                k_dmg = 200 + (self.bonus_ad * 0.4)
                dmg_log += self.calculate_mitigation(k_dmg, TARGET_ARMOR, TARGET_MR, False)
                self.kraken_stacks = 0

        # ===========================
        # F. 아이템 스택 관리
        # ===========================
        # 경계 (Terminus)
        if "Terminus" in self.build_names and self.terminus_stacks < 6:
            self.terminus_stacks += 1

        # 구인수 예열
        if "Guinsoo" in self.build_names and self.guinsoo_stacks < 4:
            self.guinsoo_stacks += 1

        return dmg_log

    def run(self):
        while self.target_hp > 0 and self.time < 15.0:  # 최대 15초
            _, _, current_as = self.get_stats()
            attack_delay = 1.0 / current_as

            # Q 활성화 체크 (4타 예열)
            if not self.q_active:
                if self.q_stacks >= 4:
                    self.q_active = True
                    # 평타 캔슬 효과: 이번 딜레이를 0.1초로 단축 (모션)
                    attack_delay = 0.1

            # 공격 실행
            dmg = self.hit_damage(is_phantom=False)
            self.target_hp -= dmg
            self.total_dmg += dmg
            self.q_stacks += 1

            # 구인수 환영 타격 체크
            if "Guinsoo" in self.build_names and self.guinsoo_stacks == 4:
                self.guinsoo_phantom += 1
                if self.guinsoo_phantom >= 3:
                    # 환영 타격 발동! (온힛만 한번 더)
                    # 중요: 환영 타격은 크라켄/경계 스택도 한번 더 쌓아줌 (사용자 로직)
                    dmg_phantom = self.hit_damage(is_phantom=True)
                    self.target_hp -= dmg_phantom
                    self.total_dmg += dmg_phantom
                    self.guinsoo_phantom = 0  # 리셋

            if self.target_hp <= 0:
                break

            self.time += attack_delay

        dps = self.total_dmg / self.time if self.time > 0 else 0
        return self.time, dps


# ==========================================
# 3. 시나리오 실행
# ==========================================
# 공통: 광전사의 군화 기본 포함
# 1. 2코어 비교
scenarios = {
    "Guinsoo + Kraken": ["Berserker", "Guinsoo", "Kraken"],
    "Guinsoo + Terminus": ["Berserker", "Guinsoo", "Terminus"],
    "Guinsoo + Shadowflame": ["Berserker", "Guinsoo", "Shadowflame"],
    "Guinsoo + Nashor": ["Berserker", "Guinsoo", "Nashor"],
    "Yuntal + PD" : ["Berserker", "Yuntal", "PD"],

    # 2. 3코어 비교 (라바돈 추가)
    "Gui+Term+Rabadon": ["Berserker", "Guinsoo", "Terminus", "Rabadon"],
    "Gui+Krak+Rabadon": ["Berserker", "Guinsoo", "Kraken", "Rabadon"],
    "Gui+Shad+Rabadon": ["Berserker", "Guinsoo", "Shadowflame", "Rabadon"],
}

print(f"{'Build':<25} | {'TTK (sec)':<10} | {'DPS':<10}")
print("-" * 50)

results = []
for name, build in scenarios.items():
    sim = YunaraSim(build)
    ttk, dps = sim.run()
    results.append((name, ttk, dps))

# DPS 순으로 정렬
results.sort(key=lambda x: x[2], reverse=True)

for res in results:
    print(f"{res[0]:<25} | {res[1]:<10.2f} | {int(res[2])}")