from adc_sim.champion import CogMaw, Target
import matplotlib.pyplot as plt
from adc_sim.runes import LethalTempo, CutDown
from adc_sim.engine import run_simulation
from adc_sim.data.items_registry import create_item_from_key
from adc_sim.data.items_data import ADC_PACKAGES

# 코어 단계별 고정 타겟 (Ashe/KaiSa 시뮬과 동일)
CORE_TARGET_STATS = {
    1: {"hp": 1700, "armor": 50, "mr": 25},
    2: {"hp": 1900, "armor": 70, "mr": 30},
    3: {"hp": 2400, "armor": 100, "mr": 50},
    4: {"hp": 2600, "armor": 120, "mr": 70},
    5: {"hp": 3000, "armor": 150, "mr": 90},
}
CORE_COGMAW_LEVELS = {1: {"level": 9}, 2: {"level": 11}, 3: {"level": 13},
                      4: {"level": 15}, 5: {"level": 17}}


def build_target_for_core(core_tier):
    s = CORE_TARGET_STATS[core_tier]
    return Target(hp=s["hp"], armor=s["armor"], magic_resist=s["mr"],
                  bonus_hp=max(0, s["hp"] - 1500))


def _skill_levels_for_core(core_tier):
    """코어별 스킬레벨 가정: W 선마, 그 다음 Q. R은 6렙부터(tier1=lvl9 → r 가능)."""
    # 단순화: q/w/e는 코어가 오를수록 최대로, r은 레벨 기반.
    lvl = CORE_COGMAW_LEVELS[core_tier]["level"]
    w = min(5, max(1, core_tier + 1))
    q = min(5, max(1, core_tier))
    e = min(5, max(1, core_tier - 1)) if core_tier > 1 else 1
    r = 1 if lvl < 11 else (2 if lvl < 16 else 3)
    return q, w, e, r


def simulate_cogmaw_core_path(full_path, core_tier, doran_key="doranblade",
                              boots_key="berserker", rune_as_bonus=0.0):
    """Cog'Maw DPS + total gold for a core timing. W/Q/E/R 쿨마다 시전(마나 바운드)."""
    target = build_target_for_core(core_tier)
    lvl = CORE_COGMAW_LEVELS[core_tier]["level"]
    q, w, e, r = _skill_levels_for_core(core_tier)
    cog = CogMaw(level=lvl, q_level=q, w_level=w, e_level=e, r_level=r)
    cog.set_rune(LethalTempo())
    cog.set_sub_rune(CutDown())

    items = ([create_item_from_key(doran_key)] if doran_key else []) + [create_item_from_key(boots_key)]
    for key in full_path[:core_tier]:
        items.append(create_item_from_key(key))
    total_cost = 0
    for it in items:
        total_cost += it.cost
        cog.add_item(it)
    cog.bonus_as_percent += rune_as_bonus

    # W를 t=0에 시전(버프 시작), 이후 Q/E/R + W 재시전 모두 쿨마다 자동.
    skill_plan = {
        "manual_casts": [(0.0, "w")],
        "auto_cast": {"q": True, "w": True, "e": True, "r": True},
        "auto_order": ["w", "q", "e", "r"],
    }
    _, dps, _ = run_simulation(cog, target, verbose=False, skill_plan=skill_plan)
    return dps, total_cost


if __name__ == "__main__":
    # Task 6에서 랭킹·표·그래프 추가
    d, c = simulate_cogmaw_core_path(("guinsoo", "kraken", "nashor", "terminus"), 4)
    print(f"[smoke] 4-core guinsoo-kraken-nashor-terminus: DPS {d:.1f} / Gold {c}")
