"""아이템 정적 데이터 — 패치마다 갱신하는 '숫자'의 단일 출처(source of truth).

동작(on_hit / get_damage_modifier 등)은 adc_sim/items.py 의 클래스가 담당하고,
여기서는 스탯·가격·이름만 데이터로 둔다. 인스턴스는
adc_sim/data/items_registry.create_item_from_key(key) 로 생성한다.

stats 키 = 엔진이 실제 소비하는 스탯(STAT_KEYS). 명시 안 한 키는 0.
- as: 공격속도(%) 소수 / crit: 치명타확률 소수 / add_crit_damage: 치명타피해 가산
- armor_pen_percent: %방관 / magic_pen_flat: 고정 마관 / cdr: 스킬가속 / mana: 추가 마나
주의: hp/ms/ar/mr/lifesteal 등은 현재 엔진이 DPS 계산에 쓰지 않으므로 데이터에 없음.

yuntal/yuntal25 의 crit 은 구매 코어 타이밍별 런타임 파라미터라 base 에 미포함
(레지스트리가 yuntal_crit 으로 주입; None이면 yuntal_default_crit 사용).
"""

# 엔진이 소비하는 스탯 키 (champion.add_item 이 읽는 것과 동일)
STAT_KEYS = (
    "ad", "ap", "as", "crit", "add_crit_damage",
    "armor_pen_percent", "lethality", "magic_pen_flat", "magic_pen_percent", "cdr", "mana",
)

# 도란 시작 아이템 토글 — 최고 빌드 탐색 시 검/활 두 경우(2배)를 평가하고
# 빌드별로 점수 높은 쪽을 고른다. 표/그래프 라벨에 DORAN_SHORT 로 표기.
# (현재 Corki 만 이 자유 토글을 사용; Ashe/Yunara/KaiSa 는 ADC_PACKAGES 사용)
DORAN_OPTIONS = ("doranblade", "doranbow")
DORAN_SHORT = {"doranblade": "Blade", "doranbow": "Bow"}

# ADC 시작 "정배" 패키지 — "피흡 + 최소 공속 확보" 가정 하의 두 조합.
# 룬(핏빛길=피흡9% / 민첩함=공속18%)은 골드 무료. 엔진은 피흡을 무시하고 공속만 반영하므로:
#   A = 도란검 + 광전사(공속신) + 핏빛길(피흡룬) → 피흡=룬, 공속=신발
#   B = 도란활 + Gluttonous(피흡신) + 민첩함(공속룬) → 피흡=신발, 공속=도란활+룬
# Ashe/Yunara/KaiSa 최고 빌드 탐색은 이 둘 중 빌드별 우수 패키지를 선택(2배 평가).
ADC_PACKAGES = (
    {"key": "A", "label": "Bld+Zerk", "doran": "doranblade", "boots": "berserker", "rune_as": 0.0},
    {"key": "B", "label": "Bow+Glut", "doran": "doranbow",   "boots": "glutton",   "rune_as": 0.18},
)

ITEMS = {
    # key          name                            cost  behavior(=adc_sim.items 클래스)   stats
    "kraken":      {"name": "Kraken Slayer",            "cost": 3000, "behavior": "KrakenSlayer",        "stats": {"ad": 45, "as": 0.40}},
    "storm":       {"name": "Stormrazor",               "cost": 3200, "behavior": "Stormrazor",          "stats": {"ad": 50, "as": 0.20, "crit": 0.25}},
    "statikk":     {"name": "Statikk Shiv",             "cost": 3000, "behavior": "StatikkShiv",         "stats": {"ad": 45, "ap": 45, "as": 0.30}},
    "c44":         {"name": "Hextech Scope C44",        "cost": 2800, "behavior": "HextechScopeC44",     "stats": {"ad": 55, "crit": 0.25}},
    "bot":         {"name": "Blade of the Ruined King", "cost": 3200, "behavior": "BladeOfRuinedKing",   "stats": {"ad": 40, "as": 0.25}},
    "botrk":       {"name": "Blade of the Ruined King", "cost": 3200, "behavior": "BladeOfRuinedKing",   "stats": {"ad": 40, "as": 0.25}},
    "bot_as18":    {"name": "BotRK (AS+18%)",           "cost": 3200, "behavior": "BladeOfRuinedKing",   "stats": {"ad": 40, "as": 0.43}},
    "pd":          {"name": "Phantom Dancer",           "cost": 2650, "behavior": "PhantomDancer",       "stats": {"as": 0.65, "crit": 0.25}},
    "runaan":      {"name": "Runaan's Hurricane",       "cost": 2650, "behavior": "RunaansHurricane",    "stats": {"as": 0.40, "crit": 0.25}},
    "terminus":    {"name": "Terminus",                 "cost": 3000, "behavior": "Terminus",            "stats": {"ad": 30, "as": 0.35}},
    "guinsoo":     {"name": "Guinsoo's Rageblade",      "cost": 3000, "behavior": "GuinsoosRageblade",   "stats": {"ad": 30, "ap": 30, "as": 0.25}},
    "ie":          {"name": "Infinity Edge",            "cost": 3500, "behavior": "InfinityEdge",        "stats": {"ad": 75, "crit": 0.25, "add_crit_damage": 0.30}},
    "ldr":         {"name": "Lord Dominik's Regards",   "cost": 3300, "behavior": "LordDominiksRegards", "stats": {"ad": 35, "crit": 0.25, "armor_pen_percent": 0.35}},
    "mortal":      {"name": "Mortal Reminder",          "cost": 3000, "behavior": "MortalReminder",      "stats": {"ad": 35, "crit": 0.25, "armor_pen_percent": 0.30}},
    "bt":          {"name": "Bloodthirster",            "cost": 3400, "behavior": "Bloodthirster",       "stats": {"ad": 80}},
    "ga":          {"name": "Guardian Angel",           "cost": 3200, "behavior": "GuardianAngel",       "stats": {"ad": 55}},
    "mercurial":   {"name": "Mercurial Scimitar",       "cost": 3200, "behavior": "MercurialScimitar",   "stats": {"ad": 50}},
    "nashor":      {"name": "Nashor's Tooth",           "cost": 2900, "behavior": "NashorsTooth",        "stats": {"ap": 80, "as": 0.50, "cdr": 15}},
    "rabadon":     {"name": "Rabadon's Deathcap",       "cost": 3500, "behavior": "RabadonsDeathcap",    "stats": {"ap": 130}},
    "shadowflame": {"name": "Shadowflame",              "cost": 3200, "behavior": "Shadowflame",         "stats": {"ap": 110, "magic_pen_flat": 15}},
    "void":        {"name": "Void Staff",               "cost": 3000, "behavior": "VoidStaff",           "stats": {"ap": 95, "magic_pen_percent": 0.40}},
    "shieldbow":   {"name": "Immortal Shieldbow",       "cost": 3000, "behavior": "ImmortalShieldbow",   "stats": {"ad": 55, "crit": 0.25}},
    "trinity":     {"name": "Trinity Force",            "cost": 3333, "behavior": "TrinityForce",        "stats": {"ad": 36, "as": 0.30, "cdr": 15}},
    "essence":     {"name": "Essence Reaver",           "cost": 3050, "behavior": "EssenceReaver",       "stats": {"ad": 50, "crit": 0.25, "cdr": 20}},
    "collector":   {"name": "The Collector",            "cost": 3000, "behavior": "TheCollector",        "stats": {"ad": 50, "crit": 0.25, "lethality": 10}},
    "rfc":         {"name": "Rapid Firecannon",         "cost": 2650, "behavior": "RapidFirecannon",     "stats": {"as": 0.35, "crit": 0.25}},
    "manamune":    {"name": "Manamune",                 "cost": 2900, "behavior": "Manamune",            "stats": {"ad": 35, "cdr": 15, "mana": 500}},
    "muramana":    {"name": "Muramana",                 "cost": 2900, "behavior": "Manamune",            "stats": {"ad": 35, "cdr": 15, "mana": 500}},
    "plated":      {"name": "Plated Steelcaps",         "cost": 1200, "behavior": "Plated_Steelcaps",    "stats": {}},
    "berserker":   {"name": "Berserker Greaves",        "cost": 1100, "behavior": "BerserkerGreaves",    "stats": {"as": 0.25}},
    "glutton":     {"name": "Gluttonous Greaves",       "cost": 1000, "behavior": "GluttonousGreaves",   "stats": {}},
    "doranblade":  {"name": "Doran's Blade",            "cost": 450,  "behavior": "Doranblade",          "stats": {"ad": 10}},
    "doranbow":    {"name": "Doran's Bow",              "cost": 400,  "behavior": "DoransBow",           "stats": {"ad": 8, "as": 0.15}},
    "yuntal":      {"name": "Yun Tal Wildarrows",       "cost": 3100, "behavior": "YunTalWildarrows",    "stats": {"ad": 50, "as": 0.40}, "yuntal_default_crit": 0.25},
    "yuntal25":    {"name": "Yun Tal Wildarrows",       "cost": 3100, "behavior": "YunTalWildarrows",    "stats": {"ad": 50, "as": 0.40}, "yuntal_default_crit": 0.25},
}
