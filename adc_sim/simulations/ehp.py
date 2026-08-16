# -*- coding: utf-8 -*-
"""코어 타이밍별 유효 체력(EHP) 계산 — 시뮬 없이 스탯 산술만 사용한다.

유효 체력 = 체력 × (100 + 저항)/100  (사용자 정의 2026-08-11).
`실피해 = raw × 100/(100+저항)` 의 역함수이므로, "이만큼의 원시 피해를 받아야 죽는다"
는 뜻이 되고 DPS 와 같은 단위계에서 비교할 수 있다.

DPS/DPG 와 달리 EHP 는 전투 진행에 의존하지 않으므로(레벨 + 장착 아이템만의 함수)
이벤트 루프를 돌릴 필요가 없다. 그래서 어떤 시뮬의 코어 타이밍 표에도 싸게 얹을 수 있다.

예외: 경계(Terminus)의 빛 스택은 전투 중 평타로 쌓이는 값이라 정적 스냅샷에는 없다.
지속 전투를 가정하는 이 프로젝트 관례(K=2 처치)에 맞춰 기본적으로 풀스택으로 본다
(`terminus_light_stacks=3`, 0 으로 주면 미적용). [H-EHP-TERMINUS-1]
"""

from adc_sim.data.items_registry import create_item_from_key


def build_champion_snapshot(champion_factory, level, item_keys,
                            yuntal_crit=None, terminus_light_stacks=3):
    """레벨과 아이템만 반영한 챔피언 인스턴스를 만들어 반환한다(전투 미실행).

    champion_factory: `lambda level: KaiSa(level=level, ...)` 형태의 호출 가능 객체.
    item_keys: 도란·신발을 포함한 실제 장착 키 목록.
    yuntal_crit: 윤탈 크리 오버라이드(EHP 에는 무관하지만 인터페이스 일관성 위해 유지).
    """
    champion = champion_factory(level=level)
    for key in item_keys:
        if key in ("yuntal", "yuntal25") and yuntal_crit is not None:
            item = create_item_from_key(key, yuntal_crit=yuntal_crit)
        else:
            item = create_item_from_key(key)
        champion.add_item(item)
        applier = getattr(item, "apply_full_light_stacks", None)
        if applier is not None and terminus_light_stacks:
            applier(champion, stacks=terminus_light_stacks)
    return champion


def core_timing_ehp(champion_factory, level, item_keys, **kwargs):
    """코어 타이밍 하나의 유효 체력 묶음을 반환한다.

    반환: {hp, armor, mr, physical, magic, true} — champion.effective_hp_all() 그대로.
    """
    return build_champion_snapshot(champion_factory, level, item_keys, **kwargs).effective_hp_all()


def ehp_curve(champion_factory, levels_by_tier, item_keys_by_tier, **kwargs):
    """코어 티어별 EHP 곡선을 계산한다.

    levels_by_tier: {tier: level}. item_keys_by_tier: {tier: [장착 키...]}.
    반환: {tier: {hp, armor, mr, physical, magic, true}}.
    """
    return {
        tier: core_timing_ehp(champion_factory, levels_by_tier[tier], item_keys_by_tier[tier], **kwargs)
        for tier in sorted(item_keys_by_tier)
    }


def ehp_per_1000_gold(ehp_value, gold):
    """골드당 유효 체력 — DPG(골드당 DPS)의 방어 쪽 대응 지표."""
    return ehp_value / (gold / 1000.0) if gold > 0 else 0.0


def survivability(ehp_all, healing_total=0.0):
    """생존성 = 기준 전투 동안 흡수 가능한 총 원시 피해 (유효 체력 + 회복 환산).

    회복도 체력과 같은 단위이므로 저항 배수를 동일하게 곱해 더한다:

        생존성(축) = EHP(축) + 회복량 × (100 + 저항)/100

    healing_total: 그 코어 타이밍의 기준 전투(K=2 처치) 누적 회복량
        (engine.sustain_metrics["total_healing"]). 0 이면 생존성 = EHP.

    ⚠️ 회복량은 전투 길이에 비례하는 값이라 생존성도 '기준 전투 기준'이다.
       DPS 와 마찬가지로 절대값이 아니라 같은 조건끼리의 비교용 지표로 읽어야 한다.
    반환: {physical, magic, true, healing_physical, healing_magic, healing_true}
    """
    resist_by_axis = {
        "physical": ehp_all["armor"],
        "magic": ehp_all["mr"],
        "true": 0.0,
    }
    out = {}
    for axis, resist in resist_by_axis.items():
        healing_ehp = healing_total * (100.0 + resist) / 100.0
        out[axis] = ehp_all[axis] + healing_ehp
        out[f"healing_{axis}"] = healing_ehp
    return out


def healing_effective(healing_total, ehp_all):
    """회복량을 물리/마법/고정 각 축의 '유효 체력 단위'로 환산한다.

    회복 300 이라도 방어력 100 이면 물리 피해 기준으로는 600 만큼을 더 버티는 셈이다.
    원시 회복량(체력 단위)은 축마다 값어치가 달라 그대로 비교하면 안 된다.

        회복(축) = 회복량 × (100 + 저항)/100

    반환: {physical, magic, true} — true 는 저항을 무시하므로 원시 회복량과 같다.
    """
    return {
        "physical": healing_total * (100.0 + ehp_all["armor"]) / 100.0,
        "magic": healing_total * (100.0 + ehp_all["mr"]) / 100.0,
        "true": healing_total,
    }


def survivability_per_1000_gold(survivability_value, gold):
    """골드당 생존성 — DPG(골드당 DPS)의 생존 쪽 대응 지표."""
    return survivability_value / (gold / 1000.0) if gold > 0 else 0.0
