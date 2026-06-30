"""케이스 기반 코어 빌드 랭킹 — 모델 설정(데이터) 전용 모듈 (Phase B).

"4코어=방어템(고정 아님)" 실전 메타를 케이스로 나눠 1~5코어 파워커브로 평가한다.
정책(가중치/축/제약/후보풀)을 전부 '데이터'로 두어 하드코딩을 피하고 확장 가능하게 한다.
랭킹 엔진(adc_sim/simulations/case_ranking.py)은 이 설정을 소비만 한다.
출력 정책(top_n 등)은 글로벌 adc_sim/settings.py 의 CASE_RANKING_OUTPUT 에 있다.

(이 모듈은 순수 설정·헬퍼라 adc_sim 코어 모듈을 import 하지 않는다.)
"""

# ── 코어별 가중 프로파일 ───────────────────────────────────────────────────
# 이름 → 코어수 n 을 받아 가중치 리스트를 돌려주는 callable, 또는 명시 벡터.
# 점수 = Σ wᵢ·rel_DPGᵢ / Σ wᵢ × 100 (엔진에서 정규화). 새 성향은 여기 한 줄로 추가.
WEIGHT_PROFILES = {
    "early_heavy": lambda n: [round(0.80 ** i, 4) for i in range(n)],  # 초반 급가중
    "balanced":    lambda n: [round(0.90 ** i, 4) for i in range(n)],  # 완만
    "flat":        lambda n: [1.0] * n,                                # 균등
    "linear_down": lambda n: [float(n - i) for i in range(n)],         # n,n-1,… (≈5:4:3:2:1)
    # 명시 벡터도 허용(길이=n 이어야 함): "custom_54332": [5, 4, 3, 3, 2],
}
DEFAULT_WEIGHT_PROFILE = "early_heavy"


def get_weights(profile_name, n):
    """프로파일 이름 → 길이 n 가중치 리스트. callable/명시벡터 양쪽 지원."""
    prof = WEIGHT_PROFILES[profile_name]
    weights = prof(n) if callable(prof) else list(prof)
    if len(weights) != n:
        raise ValueError(f"weight profile '{profile_name}' 길이 {len(weights)} != n={n}")
    return weights


# ── 케이스 축(axes) ────────────────────────────────────────────────────────
# 축에 항목만 추가하면 케이스가 (조건부) 곱으로 자동 확장된다.
# 방어 타이밍: 방어템을 4코어/5코어에 넣거나(slot), 안 넣음(alldps, slot=None).
DEFENSIVE_TIMINGS = (
    {"key": "def@4",  "slot": 4},
    {"key": "def@5",  "slot": 5},
    {"key": "alldps", "slot": None},   # 예외: 5코어까지 풀딜(즐겜)
)
# 방어템 후보(방어 타이밍에서만 적용). 확장 예정: "zhonya"(카이사/유나라 AP스케일용).
DEFENSIVE_ITEMS = ("maw", "ga", "mercurial")
# 치유감소 축. True → 빌드에 치감템(HEAL_CUT_ITEM) 강제 포함. 확장 예정: 치감템 종류 축(mortal/chempunk).
HEAL_CUT_OPTIONS = (
    {"key": "nohc", "heal_cut": False},
    {"key": "hc",   "heal_cut": True},
)

# ── DPS 시퀀스 생성 제약 ───────────────────────────────────────────────────
# 슬롯(코어 위치)별 배치 제한 — 이 슬롯(위치)에만 허용. 명시 안 한 아이템은 전 슬롯 허용.
SLOT_RESTRICTED_ITEMS = {
    "yuntal25": (1, 2),       # 윤탈 야생화살: 1~2코어 이내만
    "manamune": (1, 2),       # 마나무네: 1~2코어 이내만
    "statikk":  (1, 2, 3),    # 스태틱: 라인클리어용 → 4·5코어는 비효율(계수 없음)이라 제외
}
# 스택 아이템: 구매한 코어 타이밍엔 스택 0(비활성), '다음' 코어 타이밍부터 풀스택으로 취급.
STACK_ITEMS = ("yuntal25", "manamune")
# 관통/방관 계열 상호 배타(한 빌드에 1개까지).
PEN_EXCLUSIVE_KEYS = ("ldr", "terminus", "mortal")
# 치유감소(hc) 케이스가 강제로 포함시키는 치감 아이템.
HEAL_CUT_ITEM = "mortal"
# Zeal(질풍검) 계열 — 이동속도+공속/치명. (윤탈·스태틱은 zeal 아이템으로 보지 않음.)
ZEAL_ITEMS = ("pd", "runaan", "rfc")
# zeal 제약은 '축'으로 분리: 제약 없음 / 오프닝(1~3코어)에 zeal≥1 — 둘 다 따로 랭킹(케이스 2배).
ZEAL_OPTIONS = (
    {"key": "zealfree", "required": False},
    {"key": "zealreq",  "required": True},
)

# ── 룬: 정밀 "전설" 슬롯(택1) + 스탯 파편 3섹션(섹션별 택1) ──────────────────
# 선택형: SELECTED_RUNES 로 1세트를 고르고, 옵션 메뉴는 RUNE_OPTIONS 에서 직접 편집한다.
# DPS에 영향 있는 스탯만 모델링(ad / as / cdr=스킬가속). 피흡·체력·이속·강인함은
# DPS 0이라 빈 dict(미모델 — 선택은 가능, 효과는 1v1 모델에서 추후). 적응형 +9 → AD 5.4.
RUNE_OPTIONS = {
    "legend": {                       # 정밀 전설 슬롯
        "bloodline": {},              # 핏빛길: 흡혈6.75%(15×0.45)+HP85 (DPS 0)
        "alacrity":  {"as": 0.18},    # 민첩함: 공속 +18%
        "haste":     {"cdr": 15},     # 가속: 스킬가속 +15
    },
    "offense": {                      # 공격 파편
        "adaptive": {"ad": 5.4},      # 적응형 +9
        "as":       {"as": 0.10},     # 공속 +10%
        "haste":    {"cdr": 8},       # 스킬가속 +8
    },
    "flex": {                         # 유연 파편
        "adaptive": {"ad": 5.4},
        "ms":       {},               # 이동속도 +2.5% (DPS 0)
        "hp":       {},               # 체력 10~180 레벨선형 (DPS 0)
    },
    "defense": {                      # 방어 파편 (전부 DPS 0)
        "hp65":     {},               # 체력 +65
        "tenacity": {},               # 강인함·둔화저항 +15%
        "hp_scale": {},               # 체력 10~180 레벨선형
    },
}
# 현재 선택된 룬 세트(직접 바꿔 비교). 기본: 민첩함 + 공속파편 + 적응형 + 체력65.
SELECTED_RUNES = {"legend": "alacrity", "offense": "as", "flex": "adaptive", "defense": "hp65"}


def selected_rune_stats(selection=None):
    """선택된 룬 세트의 DPS 스탯 합(ad/as/cdr). 없는 키는 0."""
    sel = selection or SELECTED_RUNES
    out = {"ad": 0.0, "as": 0.0, "cdr": 0.0}
    for section, key in sel.items():
        for stat, val in RUNE_OPTIONS[section][key].items():
            out[stat] += val
    return out

# ── DPS 후보 풀 = "비-방어 전 아이템 전수조사" ─────────────────────────────
# 풀을 큐레이션하지 않고, ITEMS 에서 아래 제외 세트만 빼서 엔진이 자동 도출한다
# (아이템 추가 시 자동 반영, 하드코딩 풀 없음). 슬롯 제약은 SLOT_RESTRICTED_ITEMS 적용.
# 방어 기준: 존야/수호천사/멜모셔스처럼 특화된 강한 방어템만 제외. shieldbow(철갑궁)는
# 방어막이 미미해 공격 아이템으로 보고 풀에 포함.
NON_DPS_KEYS = frozenset({
    "ga", "mercurial", "maw",           # 방어 아이템(방어 슬롯에 별도 삽입)
    "berserker", "glutton", "plated",   # 신발
    "doranblade", "doranbow",           # 도란 시작템
    "botrk", "bot_as18",                # bot 중복키/변형
    "muramana",                         # 마나무네 진화상태(스택 규칙으로 런타임 처리)
    "yuntal",                           # yuntal25 와 동일 아이템(중복키)
})

# 케이스별 기준선(컨트롤) 1~3 오프닝. 기존 컨트롤 빌드 Krk-PD-IE-LDR 의 1~3코어.
# (각 케이스에서 이 오프닝에 동일 구조 — 방어 슬롯 삽입 + 최적 연계 — 를 적용해 baseline 으로 씀.)
CONTROL_OPENING = ("kraken", "pd", "ie")


def build_ranking_cases(weight_profile=DEFAULT_WEIGHT_PROFILE):
    """축들의 (조건부) 곱으로 케이스 목록 생성. 방어템 축은 방어 타이밍에서만 적용.

    반환 각 항목: {name, defensive_slot, defensive_item, heal_cut, zeal_required, weight_profile, n_cores}.
    현재 28케이스 (= [2타이밍 × 3방어템 + 1풀딜] × 2치감 × 2zeal).
    """
    cases = []
    for timing in DEFENSIVE_TIMINGS:
        item_axis = DEFENSIVE_ITEMS if timing["slot"] is not None else (None,)
        for def_item in item_axis:
            for hc in HEAL_CUT_OPTIONS:
                for zeal in ZEAL_OPTIONS:
                    parts = ([timing["key"]] + ([def_item] if def_item else [])
                             + [hc["key"], zeal["key"]])
                    cases.append({
                        "name": "/".join(parts),
                        "defensive_slot": timing["slot"],
                        "defensive_item": def_item,
                        "heal_cut": hc["heal_cut"],
                        "zeal_required": zeal["required"],
                        "weight_profile": weight_profile,
                        "n_cores": 5,
                    })
    return cases
