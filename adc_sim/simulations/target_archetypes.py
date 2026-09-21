# -*- coding: utf-8 -*-
"""코어 타이밍별 상대 타깃 아키타입 — 딜러 / 브루저 / 탱커 (사용자 확정 2026-09-16).

**유나라·카이사가 이 모듈을 쓴다.** 나머지 챔피언 시뮬(ashe / vayne / cogmaw / azir /
ezreal / corki)은 아직 각자 파일 안에 `CORE_TARGET_STATS` 한 벌(1700/50/30 …
3000/150/95)을 복사해 들고 있다. **확장 예정이며, 옮길 때는 표를 새로 쓰지 말고 이 모듈을
쓸 것** — 챔피언별 표가 갈라지면 `power_compare` 의 챔피언 간 비교가 무의미해진다.
⚠️ 두 표가 섞인 상태라 **지금 power_compare 의 챔피언 간 비교는 타깃이 다른 값끼리 놓고
본다** — 이관이 끝날 때까지 그 표는 참고용으로만 읽을 것.

옮기는 방법(챔피언 시뮬 1개 기준):
    from adc_sim.simulations.target_archetypes import core_target_stats, half_target_stats
    CORE_TARGET_STATS = core_target_stats()          # 기본 아키타입
    # build_target_for_core() 는 그대로 CORE_TARGET_STATS 를 읽으면 된다.
⚠️ 옮기면 그 챔피언의 DPS 절대값이 바뀐다 → `tests/_baseline_dps.json` 재캡처
   (`python -m tests.regression_snapshot --write`)와 골든 테스트 갱신이 따라와야 한다.

── 표의 근거 ────────────────────────────────────────────────────────────────
· **딜러**: 방어템을 사지 않는 원딜·미드. **모델된 원딜 8종의 기본 스탯 평균**
  (체력 608.1+102.75 / 방어 25.0+4.39 / 마저 33.0+1.1)을 라이엇 성장 곡선(`adc_sim.growth`)에
  대입한 값이다. 도란템 체력 80 은 **실제로 들고 있는 1~2코어에만** 더한다(3코어부터는 팔았다고 본다).
  4~5코어 체력은 평균값에서 **각각 100 씩 낮춘 값**이다(사용자 확정 2026-09-20) — 후반 딜러가
  체력템을 거의 안 든다는 판단.
  ⚠️ **딜러만 레벨 가정이 한 칸 낮다 — 8/10/12/14/16**(사용자 확정 2026-09-16):
  현 메타에서 딜러가 5코어 시점에 18레벨을 못 찍는 경우가 많다는 판단. 브루저·탱커는
  9/11/13/15/17 기준이라 **아키타입 간 절대 비교는 이 레벨 차를 감안해서 읽어야 한다**
  (같은 아키타입 안에서 빌드끼리 비교하는 용도로는 무관).
  (이전 값은 유나라 본인 스탯 + 레벨 9~17 이라 5코어 체력이 2400 까지 갔다 — 유나라의 체력
   성장 110 이 원딜 8종 중 최고치라 표본 상단이었고, 레벨 가정도 한 칸 높았다.)
· **브루저**: 체력과 방어를 같이 올리는 전사. 딜러와 탱커 사이를 메운다.
  **마저는 코어당 +10, 1코어 30에서 시작**(사용자 확정 2026-09-16) — 탱커(코어당 +8, 45 시작)
  보다 증가폭은 크지만 시작이 낮아 5코어까지 탱커 아래(70 < 77)에 머문다.
· **탱커**: 방어템을 계속 쌓는 상대. **마저는 레벨당 +4**(코어 사이 2레벨 = +8).
· 마저 수치는 26 패치 원딜 마저 상향(+5)이 반영된 값이다.

하프 코어(아이템 사이 구간) 타깃은 인접 코어의 **선형 보간**이고, 1코어 하프는 코어 1 과
같다(`half_target_stats`). 유나라(공격자) 레벨은 하프 8/10/12/14/16 · 완성 9/11/13/15/17 이며,
타깃 레벨과는 별개다 — 위 딜러 항목의 레벨 주의 참조.

거인 학살자(LDR) 증폭 판정에 쓰는 타깃 추가 체력은 `max(0, 최대체력 − BONUS_HP_BASELINE)`
이며, 이 1600 규약은 전 챔피언 공통이다(사용자 확정 2026-08-31).
"""

# 타깃 "추가 체력" 판정 기준선 — 전 챔피언 공통 규약.
BONUS_HP_BASELINE = 1600

# 코어 티어(1~5)별 (hp, armor, mr).
TARGET_ARCHETYPES = {
    "dealer": {
        "label": "딜러",
        "desc": "원딜·미드. 원딜 8종 평균 스탯, 레벨 8/10/12/14/16, 도란 80 은 1~2코어만.",
        "tiers": {
            1: (1280, 50, 39),
            2: (1485, 59, 42),
            3: (1620, 68, 44),
            4: (1750, 78, 46),
            5: (1995, 89, 49),
        },
    },
    "bruiser": {
        "label": "브루저",
        "desc": "체력·방어를 같이 올리는 전사. 마저는 코어당 +10(시작 30)으로 일정.",
        "tiers": {
            1: (1900, 70, 30),
            2: (2250, 95, 40),
            3: (2650, 125, 50),
            4: (3000, 155, 60),
            5: (3350, 185, 70),
        },
    },
    "tank": {
        "label": "탱커",
        "desc": "방어템을 계속 쌓는 탱커. 마저는 레벨당 +4(코어 사이 +8).",
        "tiers": {
            1: (2100, 85, 45),
            2: (2550, 115, 53),
            3: (3050, 150, 61),
            4: (3550, 190, 69),
            5: (4050, 230, 77),
        },
    },
}

# 기본 아키타입 — 딜러와 탱커 사이의 중간값이라 단일 표를 써야 하는 소비처의 기본값.
DEFAULT_ARCHETYPE = "bruiser"

# 코어 티어 범위(다른 모듈이 하드코딩하지 않도록 노출).
CORE_TIERS = (1, 2, 3, 4, 5)


def _tiers(archetype=None):
    name = archetype or DEFAULT_ARCHETYPE
    if name not in TARGET_ARCHETYPES:
        raise ValueError(f"Unknown target archetype: {name} "
                         f"(가능: {', '.join(TARGET_ARCHETYPES)})")
    return TARGET_ARCHETYPES[name]["tiers"]


def core_target_stats(archetype=None):
    """아키타입의 코어 티어별 타깃 스탯 dict — `{tier: {hp, armor, mr}}`.

    기존 시뮬들의 `CORE_TARGET_STATS` 와 같은 모양이라 그대로 대입하면 된다.
    """
    return {tier: {"hp": hp, "armor": armor, "mr": mr}
            for tier, (hp, armor, mr) in _tiers(archetype).items()}


def half_target_stats(tier, archetype=None):
    """코어 `tier` **직전** 하프 구간의 타깃 스탯 — 인접 코어 선형 보간.

    tier=1 은 보간할 앞 코어가 없으므로 코어 1 과 같다.
    """
    tiers = _tiers(archetype)
    if tier <= 1:
        hp, armor, mr = tiers[1]
    else:
        prev = tiers[tier - 1]
        cur = tiers[min(max(CORE_TIERS), tier)]
        hp, armor, mr = ((prev[i] + cur[i]) / 2.0 for i in range(3))
    return {"hp": hp, "armor": armor, "mr": mr}


def bonus_hp(hp):
    """거인 학살자 판정용 타깃 추가 체력."""
    return max(0, hp - BONUS_HP_BASELINE)


def archetype_labels():
    """UI·표 출력용 `{id: label}`."""
    return {key: value["label"] for key, value in TARGET_ARCHETYPES.items()}
