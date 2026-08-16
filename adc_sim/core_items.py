"""전설급(코어) 아이템의 런타임 동작.

가격과 정적 능력치는 adc_sim.data.items_data 가 주입하며, 이 모듈은 적중 효과,
주문 검, 중첩처럼 상태가 필요한 동작을 담당한다.
"""

from adc_sim.item_base import Item
from adc_sim.growth import stat_at_level


def _level_scaled(min_value, max_value, level, min_level=8, max_level=18):
    """"레벨에 따라" 선형 보간. 기본 구간은 8~18레벨(크라켄 학살자와 같은 관례).

    min_level 이하는 min_value 로, max_level 이상은 max_value 로 클램프한다.
    """
    span = max_level - min_level
    ratio = (min(max_level, max(min_level, level)) - min_level) / span if span else 0.0
    return min_value + (max_value - min_value) * ratio


class PhantomDancer(Item):
    def __init__(self):
        super().__init__("Phantom Dancer", as_percent=0.65, crit=0.25)
        self.cost = 2650
        # 이동속도, 유체화는 DPS 수치에 직접 영향 X


class RunaansHurricane(Item):
    def __init__(self):
        super().__init__("Runaan's Hurricane", as_percent=0.40, crit=0.25)
        self.cost = 2650

    def on_hit(self, target, champion):
        # 단일 대상 DPS 측정 시에는 추가 대미지 없음.
        # 다수 타겟 시뮬레이션이라면 로직 추가 필요.
        # * 루난 자체에는 온힛 대미지가 없고 탄환에만 있음.
        # 여기서는 0, 0 반환이 맞음.
        return 0, 0, 0, 0


class RapidFirecannon(Item):
    def __init__(self):
        super().__init__("Rapid Firecannon", as_percent=0.35, crit=0.25)
        self.cost = 2650

    def on_hit(self, target, champion):
        # 충전 상태 구현 필요.
        # 단순화를 위해: 공격 속도 기반으로 대략 5초에 한번 40 마법 피해를 준다고 가정하거나
        # 시뮬레이터가 '이동'을 안 한다면 충전이 매우 느림.
        # 일단 0으로 둠.
        return 0, 0, 0, 0


# ==========================================
# 4. 코어 아이템 2 - dps/치명타 아이템
# ==========================================
class StatikkShiv(Item):
    def __init__(self):
        super().__init__("Statikk Shiv", ad=45, ap=45, as_percent=0.30)
        self.cooldown_timer = 0
        self.cost = 3000

    def on_hit(self, target, champion):
        # 8초 내 첫 3회 공격 시 60 마법 피해.
        # 시뮬레이션 상 8초에 한 번 세트가 돈다고 가정?
        # 복잡하므로 단순하게 '첫 타격'에만 60 데미지 주고
        # 이후 쿨타임 로직은 시뮬레이터 엔진 레벨에서 다루는 게 좋음.
        return 0, 0, 0, 0


class Stormrazor(Item):
    def __init__(self):
        # 스펙: AD 50, AS 20%, 치명타 25%
        super().__init__("Stormrazor", ad=50, as_percent=0.20, crit=0.25)
        self.cost = 3200


class BladeOfRuinedKing(Item):
    def __init__(self):
        super().__init__("Blade of the Ruined King", ad=40, as_percent=0.25, lifesteal=0.1)
        self.cost = 3200

    def on_hit(self, target, champion):
        # 원거리 챔피언은 적 챔피언의 현재 체력의 6퍼센트에 해당하는 온힛 물리 피해
        return target.current_hp * 0.06, 0, 0, 0


class KrakenSlayer(Item):
    def __init__(self):
        # 스펙: AD 45, AS 40% (25.14 패치 기준)
        super().__init__("Kraken Slayer", ad=45, as_percent=0.40)
        self.stack = 0
        self.cost = 3000

    def on_hit(self, target, champion):
        total_damage = 0.0 # 초기화

        # 1. 스택 쌓기
        stack_increment = 1
        if (
            champion.name == "Yunara"
            and getattr(champion, "q_active", False)
            and champion.target_count >= 2
            and any(item.name == "Runaan's Hurricane" for item in champion.inventory)
        ):
            extra_targets = min(2, champion.target_count - 1)
            stack_increment += extra_targets

        self.stack += stack_increment

        # 2. 3타 발동 조건 확인
        if self.stack >= 3:
            self.stack = 0  # 스택 초기화

            # --- [A] 기본 피해량 계산 (8~18레벨 선형 보간) ---
            lvl = champion.level
            min_dmg = 120
            max_dmg = 160

            if lvl < 8:
                base_dmg = min_dmg
            elif lvl >= 18:
                base_dmg = max_dmg
            else:
                # 8레벨일 때 0, 18레벨일 때 1이 되는 비율
                ratio = (lvl - 8) / (18 - 8)
                base_dmg = min_dmg + (ratio * (max_dmg - min_dmg))

            # --- [B] 잃은 체력 비례 증폭 (남은 체력 30%에서 최대) ---
            # 1. 잃은 체력 비율 계산
            current_hp_ratio = target.current_hp / target.max_hp
            missing_hp_ratio = 1.0 - current_hp_ratio

            # 2. 증폭 계수 계산
            # 목표: 잃은 체력이 0.7(70%)일 때 추가 계수가 0.75(75%)가 되어야 함
            saturation_point = 0.7  # 70% 잃었을 때 (남은 체력 30%)
            max_bonus = 0.75  # 최대 75% 증폭

            if missing_hp_ratio >= saturation_point:
                # 체력이 30% 이하로 남았으면 최대 대미지 (1.75배)
                damage_multiplier = 1.0 + max_bonus
            else:
                # 0 ~ 70% 구간 선형 보간
                # 식: 1 + (현재잃은비율 / 0.7 * 0.75)
                current_bonus = (missing_hp_ratio / saturation_point) * max_bonus
                damage_multiplier = 1.0 + current_bonus

            # 최종 대미지 산출
            total_damage = base_dmg * damage_multiplier

        if total_damage > 0:
            return total_damage, 0, 0, 0  # (물리 피해, 마법 피해, 고정 평타, 고정 온힛)

        return 0, 0, 0, 0


class GuinsoosRageblade(Item):
    def __init__(self):
        # AD 30, AP 30, AS 25%
        super().__init__("Guinsoo's Rageblade", ad=30, ap=30, as_percent=0.25)
        self.is_guinsoo = True  # 핵심 플래그
        self.stack = 0
        self.full_stack_attack_counter = 0
        self.cost = 3000

    def on_hit(self, target, champion):
        # 기본 30 마법 피해
        base_magic = 30

        # 중첩당 공속 8% 증가 (최대 4회=32% 가정)
        if self.stack < 4:
            self.stack += 1
            champion.bonus_as_percent += 0.08
            # 공속 재계산 필요하므로 로그만 남김 (실제 적용은 다음 틱부터)

        return 0, base_magic, 0, 0

    def get_onhit_proc_count(self, champion):
        """
        풀스택 이후 3타마다 온힛 2회 처리.
        - 스택이 4 미만이면 일반 1회.
        - 풀스택 상태에서 공격 카운트를 누적해 3번째마다 2회.
        """
        if self.stack < 4:
            self.full_stack_attack_counter = 0
            return 1

        self.full_stack_attack_counter += 1
        if self.full_stack_attack_counter % 3 == 0:
            return 2
        return 1


class HextechScopeC44(Item):
    def __init__(self):
        # AD 50, Crit 25%, 가격 2800
        # 버프 적용: AD 50 -> 55
        super().__init__("Hextech Scope C44", ad=55, crit=0.25)
        self.cost = 2800

        # 비전 조준 활성화 여부 (필요 시 시뮬레이션 외부에서 True로 변경)
        self.is_buff_active = False

    def get_damage_modifier(self, target, champion):
        """
        확대: 적과의 거리(champion.range)에 따라 최대 10% 증가된 피해
        - 500 거리일 때 최대 (10%) [26.13 버프, 사용자 인게임 툴팁 확인]
        """

        # 1. 현재 사거리 가져오기
        # (비전 조준 효과 등으로 champion.range가 이미 변해있다고 가정하거나, 여기서 더해서 계산)
        current_range = champion.range

        # 만약 아이템 자체적으로 사거리를 늘려주는 효과를 여기서 반영하고 싶다면:
        if self.is_buff_active:
            current_range += 100

        # 2. 증폭률 계산 (최대 500 거리 기준 — 26.13 버프)
        # 거리 500 이상이면 1.0, 그 미만이면 (거리/500) 비율
        ratio = min(1.0, current_range / 500.0)

        # 3. 최대 10% 증폭
        modifier = ratio * 0.10

        return modifier

    # 시뮬레이션 중 킬/어시 발생 시 호출하여 사거리를 늘리고 싶을 때 사용
    def activate_vision_focus(self, champion):
        self.is_buff_active = True


class TheCollector(Item):
    def __init__(self):
        super().__init__("The Collector", ad=50, crit=0.25, lethality=10)
        self.execute_threshold = 0.05  # 체력 5% 미만 처형
        self.cost = 3000


class UmbralGlaive(Item):
    """그림자 검: 1초 이상 비노출 후 다음 평타에 고정 피해를 1회 적용한다."""

    def __init__(self):
        """정적 스탯 기본값과 밤의 추적자 1회 소비 상태를 초기화한다."""
        super().__init__("Umbral Glaive", ad=60, lethality=18, cdr=15)
        self.cost = 2800
        self.unseen_required = 1.0
        self._last_consumed_unseen_since = None

    def on_hit(self, target, champion):
        """충족된 비노출 구간을 소비하고 (50 + 물리 관통력 150%) 고정 피해를 반환한다."""
        unseen_since = getattr(champion, "unseen_since", None)
        unseen_duration = getattr(champion, "_combat_time", 0.0) - unseen_since if unseen_since is not None else 0.0
        if (
            unseen_since is None
            or unseen_duration + 1e-9 < self.unseen_required
            or unseen_since == self._last_consumed_unseen_since
        ):
            return 0, 0, 0, 0
        self._last_consumed_unseen_since = unseen_since
        true_damage = 50.0 + 1.5 * champion.lethality
        return 0, 0, 0, true_damage


class EssenceReaver(Item):
    def __init__(self):
        # AD 50, 스킬 가속 20, 치명타 25%
        super().__init__("Essence Reaver", ad=50, crit=0.25, cdr=20)
        self.cost = 3050
        self.is_spellblade_active = False
        self.spellblade_cd = 1.5
        self.last_activation_time = -999.0  # 마지막 활성화 시간
        self.last_spellblade_damage = 0.0

    def on_spell_cast(self, champion, time):
        # 주문검 내부 쿨: 마지막 활성화 시점 기준 1.5초
        if time >= self.last_activation_time + self.spellblade_cd:
            self.is_spellblade_active = True
            self.last_activation_time = time

    def on_hit(self, target, champion):
        self.last_spellblade_damage = 0.0
        # 주문검 효과 발동 (활성 상태에서 다음 기본 공격 1회)
        if self.is_spellblade_active:
            # 대미지: 기본 공격력 125% + 치명타 확률 * 50
            # 기본 공격력 = base_ad + ad_growth*(level-1) = total_ad - bonus_ad
            base_attack_ad = champion.total_ad - champion.bonus_ad
            damage = (base_attack_ad * 1.25) + (champion.crit_chance * 50)
            self.last_spellblade_damage = damage
            self.is_spellblade_active = False # 소모
            return damage, 0, 0, 0 # 물리 피해
            
        return 0, 0, 0, 0


class DuskAndDawn(Item):
    """황혼과 새벽 (Dusk and Dawn) — 주문검 + 온힛 1회 추가. [H-DAWN-1]

    스탯(체력300/AP60/AH20/AS20%)은 items_data.py 가 주입(단일 출처). HP는 STAT_KEYS
    미포함이라 DPS 엔진 미반영(가격엔 포함 → DPG에 '죽은 골드'로 정확히 반영).
    주문 검(쿨 2초): 스킬 사용 후 다음 평타에 (기본AD 75% + AP 10%) 추가 마법피해 +
    온힛 효과 1회 추가 적용. 회복(AP10%+추가체력3%)은 생존 효과라 DPS 모델에서 무시.
    쿨은 EssenceReaver와 동일하게 시전시각 기준, 0.2초 추가타 딜레이는 같은 평타에 합산.
    (나무위키/LoL Wiki V26.09/Community Dragon id2510 교차검증)
    """
    def __init__(self):
        super().__init__("Dusk and Dawn", ap=60, as_percent=0.20, cdr=20)
        self.cost = 3100
        self.is_spellblade_active = False
        self.spellblade_cd = 2.0
        self.last_activation_time = -999.0
        self.last_spellblade_damage = 0.0

    def on_spell_cast(self, champion, time):
        # 주문검 내부 쿨: 마지막 활성화 시점 기준 2초 (EssenceReaver와 동일 가정)
        if time >= self.last_activation_time + self.spellblade_cd:
            self.is_spellblade_active = True
            self.last_activation_time = time

    def on_hit(self, target, champion):
        self.last_spellblade_damage = 0.0
        # 강화 평타 1회: 기본 공격력 75% + 주문력 10% 추가 마법피해 (버스트 1회 소비)
        if self.is_spellblade_active:
            magic = champion.base_attack_ad * 0.75 + champion.total_ap * 0.10
            self.last_spellblade_damage = magic
            self.is_spellblade_active = False
            return 0, magic, 0, 0  # 마법 온힛(증폭·그림자불꽃·마저는 부모 루프에서 적용)
        return 0, 0, 0, 0

    def get_extra_onhit_applications(self, champion):
        # 강화 평타에서 온힛 효과 1회 추가(구인수와 합산). 버스트와 같은 armed 상태에서 1.
        # 부모 get_one_hit_damage 가 온힛 루프 전(armed)에 읽고, 루프의 on_hit 이 버스트를 소비.
        return 1 if self.is_spellblade_active else 0


class NavoriFlickerblade(Item):
    """나보리 신속검 (Navori Flickerblade) — 공속40%/치확25%/이속4%(이속 미모델). [H-NAVORI-1]

    패시브 Transcendence: 평타마다 기본스킬(Q/W/E) 남은 쿨 15% 감소(치명타 무관, 궁=R 제외).
    실제 쿨감은 챔피언이 평타당 1회(`CogMaw.on_basic_attack`)에서 `cooldowns_remaining` 에 적용 —
    `on_hit` 이 아님(구인수 proc_count 에 안 곱해지도록). 아이템은 플래그/계수만 들고 있음.
    """
    def __init__(self):
        super().__init__("Navori Flickerblade", as_percent=0.40, crit=0.25)
        self.cost = 2650
        self.is_navori = True
        self.ability_cdr_per_attack = 0.15


class TrinityForce(Item):
    def __init__(self):
        # AD 36, AS 30%, HP 333, AH 15
        super().__init__("Trinity Force", ad=36, as_percent=0.30, hp=333, cdr=15)
        self.cost = 3333

        # 주문검
        self.is_spellblade_active = False
        self.last_spellblade_damage = 0.0
        self.spellblade_cd = 1.5
        self.last_activation_time = -999.0

        # 가속(이동속도 +20, 2초) - 현재 엔진에서는 이동속도 비전투 영향 없음
        self.haste_buff_end_time = 0.0

    def on_spell_cast(self, champion, time):
        # 주문검 내부 쿨: 마지막 활성화 시점 기준 1.5초
        if time >= self.last_activation_time + self.spellblade_cd:
            self.is_spellblade_active = True
            self.last_activation_time = time

    def on_hit(self, target, champion):
        self.last_spellblade_damage = 0.0
        current_time = getattr(champion, "_combat_time", 0.0)

        # 가속 버프 갱신 (엔진 내 이동속도 계산에는 아직 미연동)
        self.haste_buff_end_time = current_time + 2.0

        # 주문검: 다음 기본 공격에 기본 공격력 * 2 물리 피해
        if self.is_spellblade_active:
            base_attack_ad = champion.total_ad - champion.bonus_ad
            damage = base_attack_ad * 2.0
            self.last_spellblade_damage = damage
            self.is_spellblade_active = False
            return damage, 0, 0, 0

        return 0, 0, 0, 0


class Manamune(Item):
    def __init__(self):
        # AD 35, Mana 500, AH 15
        super().__init__("Manamune", ad=35, cdr=15)
        self.stats["mana"] = 500
        self.cost = 2900

        # 마나순환
        self.max_mana_stack = 360
        self.mana_stacked = 0.0
        self.charge_cd = 8.0
        self.max_charges = 4
        self.charges = 4
        self.next_charge_time = None

        # 진화
        self.is_muramana = False

    def _recover_charges(self, time):
        if self.next_charge_time is None:
            return
        while self.charges < self.max_charges and time >= self.next_charge_time:
            self.charges += 1
            if self.charges >= self.max_charges:
                self.next_charge_time = None
            else:
                self.next_charge_time += self.charge_cd

    def _consume_manaflow_charge(self, champion, target):
        time = getattr(champion, "_combat_time", 0.0)
        self._recover_charges(time)
        if self.charges <= 0:
            return

        was_full = (self.charges == self.max_charges)
        self.charges -= 1
        if was_full:
            self.next_charge_time = time + self.charge_cd

        gain = 6.0 if target is not None else 3.0
        if not self.is_muramana:
            self.mana_stacked = min(self.max_mana_stack, self.mana_stacked + gain)
            if self.mana_stacked >= self.max_mana_stack:
                self.is_muramana = True
                self.name = "Muramana"

    def get_bonus_mana(self, champion):
        # add_item으로 이미 500 마나가 더해짐.
        # 마나무네: +스택(최대 360), 무라마나: 총 1000 마나가 되도록 +500 보정
        if self.is_muramana:
            return 500.0
        return self.mana_stacked

    def get_bonus_ad(self, champion):
        # 경탄: 총 마나의 2% 추가 AD
        return 0.02 * champion.total_mana

    def on_hit(self, target, champion):
        self._consume_manaflow_charge(champion, target)

        if self.is_muramana:
            # 충격(평타): 총 마나의 1.2% 추가 물리 피해
            bonus_phys = 0.012 * champion.total_mana
            return bonus_phys, 0, 0, 0
        return 0, 0, 0, 0

    def on_skill_hit(self, target, champion, time):
        self._consume_manaflow_charge(champion, target)

        if self.is_muramana:
            # 충격(스킬): 총 마나의 3% 추가 물리 피해
            bonus_phys = 0.03 * champion.total_mana
            return bonus_phys, 0, 0
        return 0, 0, 0


class DemonHunterCrossbow(Item):
    def __init__(self):
        # 공속 45%, 치명타 25%, 이속 4%, 궁극기 가속 30
        super().__init__("Demon Hunter's Crossbow", as_percent=0.45, crit=0.25, ms=0.04, cdr=30) 
        self.cost = 2650
        self.buff_active = False
        self.buff_end_time = 0.0
        self.buff_stacks = 0 # 남은 강화 평타 횟수
        self.buff_as_applied = False
        self.last_ult_time = -999.0 # 궁극기 사용 시간 (쿨타임 45초)

    def on_ult_cast(self, champion, time):
        # 궁극기 사용 시 폭격 개시 활성화 (쿨타임 45초)
        if time >= self.last_ult_time + 45.0:
            self.buff_active = True
            self.buff_end_time = time + 8.0 # 8초 지속
            self.buff_stacks = 3 # 3회
            self.last_ult_time = time
            
            # 공속 50% 증가 (Champion에 직접 적용)
            champion.bonus_as_percent += 0.50
            self.buff_as_applied = True

    def on_hit(self, target, champion):
        # 폭격 개시 효과 적용 (기댓값 계산)
        phys_dmg = 0
        true_dmg = 0

        if self.buff_active and self.buff_stacks > 0:
            self.buff_stacks -= 1
            
            # 기댓값 계산
            crit_chance = champion.crit_chance
            crit_dmg_mod = champion.crit_damage_modifier
            ad = champion.total_ad

            # 1. 치명타가 터지지 않을 확률 (1 - crit_chance) -> 강제 치명타 (80% 효율)
            # 추가되는 물리 피해량 = (치명타 대미지 - 일반 대미지) * 0.8
            # 일반 대미지 = ad
            # 치명타 대미지 = ad * crit_dmg_mod
            # 추가분 = ad * (crit_dmg_mod - 1) * 0.8
            phys_bonus_from_non_crit = (1 - crit_chance) * ad * (crit_dmg_mod - 1) * 0.8
            phys_dmg += phys_bonus_from_non_crit
            
            # 2. 치명타가 터질 확률 (crit_chance) -> 15% 추가 고정 피해
            true_bonus_from_crit = crit_chance * ad * 0.15
            true_dmg += true_bonus_from_crit
            
            # 버프 종료 시 공속 롤백
            if self.buff_stacks <= 0:
                self.buff_active = False
                if self.buff_as_applied:
                    champion.bonus_as_percent -= 0.50
                    self.buff_as_applied = False

        return phys_dmg, 0, true_dmg, 0 # (물리, 마법, 고정 평타, 고정 온힛)


class YunTalWildarrows(Item):
    def __init__(self, crit=0.25):
        # AD 50, AS 40%, Crit 25% (기본값)
        # crit 인자를 통해 치명타 확률 조절 가능 (10% 등)
        super().__init__("Yun Tal Wildarrows", ad=50, as_percent=0.40, crit=crit)
        self.active_buff = False
        self.cost = 3100

    def on_hit(self, target, champion):
        # 효과 (광풍): 적 챔피언 공격 시 공속 30% 증가
        # 시뮬레이션 단순화를 위해 첫 타격 이후 항상 버프가 켜진다고 가정
        if not self.active_buff:
            champion.bonus_as_percent += 0.30
            self.active_buff = True
            # print(f"[Item] {self.name}: Attack Speed buff activated (+30%)")

        # 효과 (연습이 치명타를 낳는다): 치명타 확률 영구 증가 (최대 25%)
        # 복잡하므로 여기서는 생략하거나, 시간이 지남에 따라 crit을 올려주는 로직 필요
        return 0, 0, 0, 0


class InfinityEdge(Item):
    def __init__(self):
        super().__init__("Infinity Edge", ad=75, crit=0.25, add_crit_damage=0.3)
        self.cost = 3500


class LordDominiksRegards(Item):
    def __init__(self):
        super().__init__("Lord Dominik's Regards", ad=35, armor_pen_percent=0.35, crit=0.25)
        self.cost = 3300

    def get_damage_modifier(self, target, champion):
        # 거인 학살자: 대상의 추가 체력에 비례해 최대 15% 추가 피해
        # 조건: 추가 체력 0일 때 0%, 1500 이상일 때 15%

        # 1. 타겟에게 bonus_hp 속성이 없으면 0 반환 (안전장치)
        if not hasattr(target, 'bonus_hp'):
            return 0.0

        extra_hp = target.bonus_hp

        # 2. 계산 로직 (선형 비례)
        if extra_hp <= 0:
            return 0.0
        elif extra_hp >= 1500:
            return 0.15  # 최대 15%
        else:
            # 1500일 때 0.15이므로 => (현재추가체력 / 1500) * 0.15
            # 즉, 현재추가체력 / 10000 과 같음
            return (extra_hp / 1500) * 0.15


class MortalReminder(Item):
    def __init__(self):
        super().__init__("Mortal Reminder", ad=35, armor_pen_percent=0.30, crit=0.25)
        self.cost = 3000


class Terminus(Item):
    def __init__(self):
        # 스펙: AD 30, AS 35%
        super().__init__("Terminus", ad=30, as_percent=0.35)
        self.cost = 3000

        # 상태 관리 변수
        self.light_stacks = 0  # 빛 스택 (방/마저, 최대 3)
        self.dark_stacks = 0  # 어둠 스택 (관통력, 최대 3)
        self.is_light_turn = True  # True면 빛, False면 어둠 차례 (보통 빛부터 시작)

    @staticmethod
    def light_resist_per_stack(level):
        """빛 스택 1개당 방어력·마저 증가량(레벨 구간별). on_hit 과 같은 표를 쓴다."""
        if level <= 6:
            return 6
        if level <= 11:
            return 7
        return 8

    def apply_full_light_stacks(self, champion, stacks=3):
        """전투 없이 빛 스택을 즉시 반영한다(EHP 정적 스냅샷용, adc_sim.simulations.ehp).

        지속 전투에서는 빛 3스택이 금방 차므로 EHP 표에서는 풀스택을 기본으로 본다.
        이미 on_hit 으로 쌓인 만큼은 중복 적용하지 않는다.
        """
        target_stacks = max(0, min(3, stacks))
        missing = target_stacks - self.light_stacks
        if missing <= 0:
            return
        gain = self.light_resist_per_stack(champion.level) * missing
        champion.bonus_armor += gain
        champion.bonus_mr += gain
        self.light_stacks = target_stacks

    def on_hit(self, target, champion):
        # 1. 적중 시 30 마법 피해 (고정)
        magic_dmg = 30

        # 2. 빛(방어/마저) 증가량 계산 (레벨 비례)
        # 구간: 1~6(+6), 7~11(+7), 12~18(+8)
        resist_gain = 0
        if champion.level <= 6:
            resist_gain = 6
        elif champion.level <= 11:
            resist_gain = 7
        else:
            resist_gain = 8

        # 3. 빛과 어둠 번갈아 적용
        if self.is_light_turn:
            # --- [빛] 차례: 방어력/마법 저항력 증가 ---
            if self.light_stacks < 3:  # 최대 3스택 제한
                self.light_stacks += 1
                # 2026-08-11 수정: 기존 `hasattr(champion,'af')` 는 오타('ar')였고 Champion 에
                # ar/mr 속성 자체가 없어 빛 스택이 완전히 죽은 코드였다. 이제 방어 스탯이
                # bonus_armor/bonus_mr 로 존재하므로 EHP 에 실제로 반영된다(딜 계산엔 무관).
                champion.bonus_armor += resist_gain
                champion.bonus_mr += resist_gain

        else:
            # --- [어둠] 차례: 방어구/마법 관통력 증가 ---
            if self.dark_stacks < 3:  # 최대 3스택 제한
                self.dark_stacks += 1
                if hasattr(champion, 'armor_pen_percent'):
                    champion.armor_pen_percent += 0.10
                if hasattr(champion, 'magic_pen_percent'):
                    champion.magic_pen_percent += 0.10

        # 4. 턴 교체 (빛 -> 어둠 -> 빛 ...)
        self.is_light_turn = not self.is_light_turn

        return 0, magic_dmg, 0, 0


# ==========================================
# 5. 코어 아이템 3 - 생존 및 유지력
# ==========================================
class WitsEnd(Item):
    """마법사의 최후: 기본 공격 적중 시 45의 마법 피해를 추가한다."""

    def __init__(self):
        super().__init__("Wit's End", as_percent=0.5, mr=45, tenacity=0.2)
        self.cost = 2800

    def on_hit(self, target, champion):
        # 적중 시 45의 온힛 마법 피해
        return 0, 45, 0, 0


class ExpHexplate(Item):
    def __init__(self):
        super().__init__("Experimental Hexplate", ad=40, as_percent=0.2, hp=450)
        self.cost=3000
        self.ult_cdr=30
        # 궁극기 사용후 8초 동안 50% 공속, 20% 이속 얻음(재사용 대기시간 30초), 구현 아직 안함!


class Bloodthirster(Item):
    """피바라기. 스탯 출처는 items_data.ITEMS['bt'] (AD80/생명력흡수15%, 3400골드).

    피갑(Ichorshield): 생명력 흡수의 초과 회복분이 방어막으로 쌓인다.
    최대 **65~315, 8~18레벨 선형** (사용자 확정 2026-08-11).

    [H-BT-EHP-1] EHP 환산 가정: 지속 전투(K=2 처치)에서 흡혈이 계속 돌아 방어막이
    상한까지 찬다고 보고 최대치를 추가 체력으로 가산한다. 실제로는 만피 상태에서만
    초과분이 쌓이므로 교전 기준 상한선이다.
    ※ '포식(Engorge)'은 라이브에 없는 예정 패치 내용이었다(2026-08-11 확인) → 미모델.
    """

    SHIELD_RANGE = (65.0, 315.0)     # 8레벨 → 18레벨

    def __init__(self):
        super().__init__("Bloodthirster", ad=80, lifesteal=0.15)
        self.cost = 3400
        # 생명력 흡수 자체는 DPS 영향 X (회복은 EHP 가 아니라 지속력 지표에서 다룬다)

    def get_bonus_ehp(self, champion, damage_type="physical"):
        """피갑 방어막 상한을 추가 유효 체력으로 반환한다. 전 속성 흡수."""
        return _level_scaled(*self.SHIELD_RANGE, champion.level)


class ImmortalShieldbow(Item):
    """불멸의 철갑궁. 스탯 출처는 items_data.ITEMS['shieldbow'] (AD55/치확25%, 3000골드).

    생명선(Lifeline): 체력이 30% 아래로 떨어질 피해를 받으면 3초간 방어막.
    **원거리 320~560 / 근접 400~700, 8~18레벨 선형** (사용자 확정 2026-08-11).
    이 프로젝트의 챔피언은 전부 원거리라 SHIELD_RANGED 를 쓴다.

    [H-SHIELDBOW-EHP-1] EHP 환산 가정: 한 교전에서 생명선이 1회 발동한다고 보고
    방어막량을 그대로 추가 체력으로 가산한다. 3초 지속, 쿨다운, 30% 문턱을 넘기 전엔
    아무 값이 없다는 점은 미반영 → 교전 기준 상한선이다.
    """

    SHIELD_RANGED = (320.0, 560.0)   # 8레벨 → 18레벨 (원거리)
    SHIELD_MELEE = (400.0, 700.0)    # 8레벨 → 18레벨 (근접, 현재 미사용)
    HP_THRESHOLD = 0.30              # 이 비율 아래로 떨어질 피해에 발동
    SHIELD_DURATION = 3.0            # 초

    def __init__(self):
        super().__init__("Immortal Shieldbow", ad=55, crit=0.25)
        self.cost = 3000

    def get_bonus_ehp(self, champion, damage_type="physical"):
        """생명선 방어막(원거리 기준)을 추가 유효 체력으로 반환한다. 전 속성 흡수."""
        return _level_scaled(*self.SHIELD_RANGED, champion.level)


class MercurialScimitar(Item):
    """헤르메스의 시미터. 스탯 출처는 items_data.ITEMS['mercurial'].

    AD 50 / 마법저항 35 / 생명력 흡수 10% (사용자 확정 2026-08-11).
    마저 35 는 마법 EHP 에, 생명력 흡수 10% 는 지속력 집계에 각각 반영된다.

    수은(Quicksilver, 액티브 쿨 90초): 군중제어 해제 + 이동속도.
    "받는 피해량"으로 환산할 수 없어 EHP 미반영 — 쿨다운만 상수로 보존한다.
    [H-MERCURIAL-1] 실전 가치(에어본·속박 해제)는 이 모델의 지표 밖이다.
    """

    QUICKSILVER_COOLDOWN = 90.0      # 초. 현재 지표엔 미반영 — 발동률 보정 시 사용.

    def __init__(self):
        super().__init__("Mercurial Scimitar", ad=50, mr=35, lifesteal=0.10)
        self.cost = 3200


class GuardianAngel(Item):
    """수호천사. 스탯 출처는 items_data.ITEMS['ga'] (AD55/방어력45, 3200골드).

    재생(Rebirth): 치명타 피해를 받으면 4초 스테이시스 후 부활하며 **기본 체력의 50%**
    (+최대 마나 100%)를 회복한다. 쿨 300초. (전부 사용자 확정 2026-08-11)

    [H-GA-REBIRTH-1] EHP 환산 가정: 한 번의 교전에서 재생이 켜져 있다고 보고
    부활 체력을 그대로 유효 체력에 가산한다. 즉 "적이 나를 죽이려면 이만큼 더 때려야 한다".
      · '기본 체력' = 아이템 체력 제외, 레벨 성장 포함(`growth.stat_at_level`, 실 LoL 곡선).
      · 4초 스테이시스 동안 받는 딜이 0인 것, 300초 쿨, 부활 후 무방비 상태는 미반영.
        따라서 이 값은 재생이 살아 있는 교전 기준의 상한선이다.
    """

    REBIRTH_BASE_HP_RATIO = 0.50
    REBIRTH_COOLDOWN = 300.0         # 초. 현재 EHP 계산엔 미반영 — 교전 빈도 보정 시 사용.

    def __init__(self):
        super().__init__("Guardian Angel", ad=55)
        self.cost = 3200

    def get_bonus_ehp(self, champion, damage_type="physical"):
        """부활로 되찾는 기본 체력 50% 를 추가 유효 체력으로 반환한다. 속성 무관."""
        base_hp_at_level = stat_at_level(champion.base_hp, champion.hp_growth, champion.level)
        return base_hp_at_level * self.REBIRTH_BASE_HP_RATIO


class MawOfMalmortius(Item):
    """멜모셔스의 아귀. DPS 기여 = AD 60 + 스킬가속 15(cdr → 애쉬 Q 쿨 감소).

    스탯/가격의 실제 출처는 items_data.ITEMS['maw'] (ad60/cdr15/mr40, 3100골드).
    마저 40은 방어 스탯이라 딜엔 무영향이지만 마법 EHP 에는 반영된다.

    생명선(Lifeline, 쿨 90초) — 사용자 확정 2026-08-11:
      체력이 30% 밑으로 떨어질 만큼 **마법 피해**를 입으면 2.5초 동안
      (근접 200 + 추가AD 150% | **원거리 150 + 추가AD 112.5%**)의
      **마법 피해를 흡수하는** 보호막. 발동하면 전투 끝까지 모든 피해 흡혈 10%.

    [H-MAW-LIFELINE-1] EHP 환산 가정:
      · 보호막은 **마법 축에만** 가산한다(물리·고정 피해는 못 막는다).
      · 한 교전에 1회 발동을 가정 — 30% 문턱, 2.5초 지속, 쿨 90초는 미반영 → 상한선.
      · 발동 후 옴니뱀 10% 도 조건 없이 붙는 것으로 계산 → 회복량도 상한선.
    """

    SHIELD_BASE_RANGED = 150.0
    SHIELD_BONUS_AD_RATIO_RANGED = 1.125
    SHIELD_BASE_MELEE = 200.0
    SHIELD_BONUS_AD_RATIO_MELEE = 1.50
    SHIELD_DURATION = 2.5
    LIFELINE_COOLDOWN = 90.0

    def __init__(self):
        super().__init__("Maw of Malmortius", ad=60)
        self.cost = 3100
        self.lifeline_omnivamp = 0.10        # 발동 후 전투종료까지 모든 피해 흡혈
        self.lifeline_shield_active = False  # 1대1 엔진이 HP<30% 마법피해 시점에 토글

    def get_bonus_ehp(self, champion, damage_type="physical"):
        """생명선 보호막을 마법 축에만 추가 유효 체력으로 반환한다(원거리 기준)."""
        if damage_type != "magic":
            return 0.0
        return self.SHIELD_BASE_RANGED + self.SHIELD_BONUS_AD_RATIO_RANGED * champion.bonus_ad

    def get_conditional_omnivamp(self, champion):
        """생명선 발동 후 붙는 모든 피해 흡혈 10%(발동 조건 미모델 → 상한선)."""
        return self.lifeline_omnivamp


class BlackCleaver(Item):
    """칠흑의 양날도끼. 스탯 출처는 items_data.ITEMS['cleaver'] (AD45/체력400/AH20, 3300골드).

    깎아내기: 챔피언에게 물리 피해를 입히면 대상 방어력 6% 감소, 최대 5중첩(=30%).
    구현 — 대상의 `armor` 를 직접 깎는다(CogMaw Q 셔레드와 같은 방식). 감소는 관통보다
    먼저 적용되어야 하므로 engine.calculate_mitigation 이전에 armor 자체를 줄이는 이 방식이
    실 LoL 순서(감소 → 관통)와 일치한다. 중첩은 '기준 방어력의 6%×스택' 가산이라
    최초 적중 시 기준 방어력을 저장해 두고 매번 그 값에서 다시 계산한다(복리 방지).

    [H-CLEAVER-1] 모델 가정 (사용자 확정 2026-08-11 수치, 동작은 아래로 단순화):
      · 지속 6초는 미모델 — 지속 전투(K=2 처치) 가정에서 평타 간격이 6초보다 짧아
        디버프가 만료되지 않는다고 본다. 따라서 한 번 쌓인 스택은 유지된다.
      · 스택은 온힛 1회당 1중첩(구인수 팬텀히트는 별도 인스턴스라 함께 카운트).
        평타 외 물리 스킬 피해로도 쌓이지만 현재 엔진은 온힛 훅만 있어 미반영.
      · 열정(이동속도)은 DPS 무관 → 미모델. 체력 400 은 데이터로 보존만.
    """

    MAX_STACKS = 5
    SHRED_PER_STACK = 0.06

    def __init__(self):
        super().__init__("Black Cleaver", ad=45, hp=400, cdr=20)
        self.cost = 3000
        self.stacks = 0
        self._base_armor = None   # 최초 적중 시점의 대상 방어력(복리 방지 기준값)

    def on_hit(self, target, champion):
        """적중 시 깎아내기 스택을 1 올리고 대상 방어력을 기준값 대비 재계산한다."""
        if self._base_armor is None:
            self._base_armor = target.armor
        if self.stacks < self.MAX_STACKS:
            self.stacks += 1
            target.armor = self._base_armor * (1.0 - self.SHRED_PER_STACK * self.stacks)
        return 0, 0, 0, 0


class ZhonyasHourglass(Item):
    """존야의 모래시계. 스탯 출처는 items_data.ITEMS['zhonya'] (AP105/방어력50, 3250골드).

    시간 정지(스테이시스 2.5초)는 '피해를 막는 시간'이라 고정 유효 체력으로 환산할 수
    없어 미모델이다. EHP 에는 방어력 50 만 반영된다. AP 는 딜 계산에 정상 반영.
    """

    STASIS_DURATION = 2.5            # 초
    STASIS_COOLDOWN = 120.0          # 초. 현재 EHP 계산엔 미반영 — 교전 빈도 보정 시 사용.

    def __init__(self):
        super().__init__("Zhonya's Hourglass", ap=105, ar=50)
        self.cost = 3250


class SerpentsFang(Item):
    def __init__(self):
        super().__init__("Serpent's Fang", ad=55, lethality=15)
        self.cost = 2500

class NashorsTooth(Item):
    def __init__(self):
        super().__init__("Nashor's Tooth", ap=80, as_percent=0.50, cdr=15)
        self.cost = 2900

    def on_hit(self, target, champion):
        # 적중 시 15 + 0.15 AP 마법 피해
        magic_dmg = 15 + (0.15 * champion.total_ap)
        return 0, magic_dmg, 0, 0

class RabadonsDeathcap(Item):
    def __init__(self):
        super().__init__("Rabadon's Deathcap", ap=130)
        self.cost = 3500
        # 패시브: 총 주문력 30% 증가 (Champion 클래스에서 처리)

class Shadowflame(Item):
    def __init__(self):
        super().__init__("Shadowflame", ap=110, magic_pen_flat=15)
        self.cost = 3200
        # 패시브: 체력 40% 이하 적에게 마법/고정 피해 20% 증가 (Champion 클래스에서 처리)

class VoidStaff(Item):
    def __init__(self):
        # 공허의 지팡이: AP 95, %마법관통 40% (스탯은 items_data 에서 주입)
        super().__init__("Void Staff", ap=95)
        self.cost = 3000

class HextechGunblade(Item):
    def __init__(self):
        super().__init__("Hextech Gunblade", ad=40, ap=80, omnivamp=0.10)
        self.cost = 3000
