# 챔피언에 따라 달라지는 변수
base_ad = 55                   # 원거리 딜러 기본 ad
ad_growth = 2.5                # 레벨의 제곱에 비례해 증가하는 공격력 계수
base_as = 0.65                 # 기본 공격속도
as_growth = 0.02               # 성장 공격속도
as_ratio = 0.65                # 공격속도 계수

base_ar = 25                   # 기본 방어력
ar_growth = 4.4                # 레벨 제곱에 비례해 증가하는 방어력 계수
base_mr = 30                   # 기본 마법 저항력
mr_growth = 1.3                # 레벨 제곱에 비례해 증가하는 마법 저항력 계수

# 레벨 입력에 따라 달라지는 변수
level = 1                      # 1 ~ 18, 모든 원딜 챔피언 공통
q_level = 1                    # 1 ~ 5

# 룬, 아이템 입력에 따라 달라지는 변수
item_ad = 100                  # 아이템 추가 공격력
item_ap = 0                    # 아이템 추가 주문력
item_as = 0                    # 아이템 추가 공격속도(%, 실제는 100으로 나눈 값)
crit_chance = 0                # 아이템으로 얻은 치명타 확률
crit_additional_damage = 0.75  # 치명타 시 추가 대미지 ad 계수

item_mr = 0                    # 아이템 추가 공격력
item_ar = 0                    # 아이템 추가 방어력

rune_ad = 0                    # 룬 추가 공격력
rune_ap = 0                    # 룬 추가 주문력
physical_penetration = 0       # 물리 관통력
armor_penetration = 0          # 방어구 관통력(%, 실제는 0 ~ 1 사이 수)
fixed_magical_penetration = 0  # 고정 마법 관통력
magical_penetration = 0        # 마법 관통력(%, 실제는 0 ~ 1 사이 수)

# 특수 효과 아이템 소지 여부
yuntal = False                 # 윤 탈 야생화살 아이템 소지 여부
nashor = False                 # 내셔의 이빨 아이템 소지 여부
termius = False                # 경계 아이템 소지 여부
witend = False                 # 마법사의 최후 소지 여부
gooinsoo = False               # 구인수 아이템 소지 여부
kraken = False                 # 크라켄 학살자 아이템 소지 여부
botrk = False                  # 몰락한 왕의 검 아이템 소지 여부

# 룬, 아이템 입력, 버프, 스펠에 따라 달라지지만, dps에 직접적인 영향은 없는 유틸 변수
movement_speed = 325
attack_range = 575

# 적 챔피언 스탯
total_hp = 2000                # 적 총 체력
hp = 2000                      # 적 현재 체력
enemy_ar = 100                 # 적 방어력
enemy_mr = 50                  # 적 마법 저항력

# 챔피언 조작에 의해 달라지는 변수
q_is_activated = False
skill_as = 0 if q_level == 0 else 10 + q_level * 10

# 챔피언 총 스탯 계산 수식
total_ad = base_ad + ad_growth * level * level + item_ad + rune_ad
total_ap = item_ap + rune_ap
total_mr = base_mr + mr_growth * level * level + item_mr
expected_ad = total_ad * (1 + crit_additional_damage * crit_chance)

# 챔피언에 따라 달라지는 챔피언 스킬셋 고려 대미지 계산 수식 (Yunara - q, passive 만 고려)
q_magic_onhit_damage = q_level * (5 + 0.2 * total_ap) * (1 + q_is_activated)        # Yunara의 q가 평타 1대당 추가하는 온힛 대미지
passive_magic_damage = (10 + 0.1 * total_ap) * total_ad * crit_chance               # 유나라의 패시브에 의해, 치명타가 터질 시 평타 1대당 추가되는 마법 대미지를 기댓값으로 환산

# 아이템, 스킬, 치속 고려 총 평타별 대미지 계산
onhit_physical_damage = 0
onhit_magical_damage = 0

# 1대별 총 대미지 계산 (총 피해 = 물리 대미지 방어력 보정 + 마법 대미지 마법 저항력 보정 + 고정 대미지)
total_physical_damage_per_hit = (expected_ad + onhit_physical_damage) / (100 + enemy_ar * (1 - armor_penetration) - physical_penetration)
total_magic_damage_per_hit = (passive_magic_damage + onhit_magical_damage) / (100 + enemy_mr * (1 - magical_penetration) - fixed_magical_penetration) * 100
total_true_damage_per_hit = 0

total_damage_per_hit = total_physical_damage_per_hit + total_magic_damage_per_hit + total_true_damage_per_hit

# 현재 공격 속도 계산 (공격속도 상한 3)
attack_per_second = min(base_as + (as_growth * level + skill_as + item_as) * as_ratio / 100, 3)
