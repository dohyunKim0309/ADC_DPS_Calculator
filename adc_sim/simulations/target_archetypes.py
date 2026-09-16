# -*- coding: utf-8 -*-
"""코어 타이밍별 상대 타깃 아키타입 — 딜러 / 브루저 / 탱커 (사용자 확정 2026-09-16).

**지금은 유나라만 이 모듈을 쓴다.** 나머지 챔피언 시뮬(ashe / vayne / cogmaw / kaisa /
azir / ezreal / corki)은 아직 각자 파일 안에 `CORE_TARGET_STATS` 한 벌(1700/50/30 …
3000/150/95)을 복사해 들고 있다. **확장 예정이며, 옮길 때는 표를 새로 쓰지 말고 이 모듈을
쓸 것** — 챔피언별 표가 갈라지면 `power_compare` 의 챔피언 간 비교가 무의미해진다.

옮기는 방법(챔피언 시뮬 1개 기준):
    from adc_sim.simulations.target_archetypes import core_target_stats, half_target_stats
    CORE_TARGET_STATS = core_target_stats()          # 기본 아키타입
    # build_target_for_core() 는 그대로 CORE_TARGET_STATS 를 읽으면 된다.
⚠️ 옮기면 그 챔피언의 DPS 절대값이 바뀐다 → `tests/_baseline_dps.json` 재캡처
   (`python -m tests.regression_snapshot --write`)와 골든 테스트 갱신이 따라와야 한다.

── 표의 근거 ────────────────────────────────────────────────────────────────
· **딜러**: 유나라 본인의 성장 능력치(체력 590+110 / 방어 25+4.4 / 마저 33+1.1)를
  라이엇 성장 곡선(`adc_sim.growth`)으로 레벨 9/11/13/15/17 에 대입하고 도란템 체력 80 을
  더한 값 = "거울 상대". 원딜·미드처럼 방어템을 사지 않는 상대를 뜻한다.
· **브루저**: 체력과 방어를 같이 올리는 전사. 딜러와 탱커 사이를 메운다.
  **마저는 코어당 +10, 1코어 30에서 시작**(사용자 확정 2026-09-16) — 탱커(코어당 +8, 45 시작)
  보다 증가폭은 크지만 시작이 낮아 5코어까지 탱커 아래(70 < 77)에 머문다.
· **탱커**: 방어템을 계속 쌓는 상대. **마저는 레벨당 +4**(코어 사이 2레벨 = +8).
· 마저 수치는 26 패치 원딜 마저 상향(+5)이 반영된 값이다.

하프 코어(아이템 사이 구간) 타깃은 인접 코어의 **선형 보간**이고, 1코어 하프는 코어 1 과
같다(`half_target_stats`). 레벨은 하프 8/10/12/14/16 · 완성 9/11/13/15/17.

거인 학살자(LDR) 증폭 판정에 쓰는 타깃 추가 체력은 `max(0, 최대체력 − BONUS_HP_BASELINE)`
이며, 이 1600 규약은 전 챔피언 공통이다(사용자 확정 2026-08-31).
"""

# 타깃 "추가 체력" 판정 기준선 — 전 챔피언 공통 규약.
BONUS_HP_BASELINE = 1600

# 코어 티어(1~5)별 (hp, armor, mr).
TARGET_ARCHETYPES = {
    "dealer": {
        "label": "딜러",
        "desc": "원딜·미드. 유나라 성장 능력치 + 도란템 체력 80 = 거울 상대.",
        "tiers": {
            1: (1410, 55, 40),
            2: (1640, 64, 43),
            3: (1880, 73, 45),
            4: (2130, 83, 48),
            5: (2400, 94, 50),
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
