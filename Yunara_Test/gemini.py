def get_level_index(gold):
    lvl = int(gold / 1000) - 1
    if lvl < 0: lvl = 0
    if lvl > 17: lvl = 17
    return lvl


def get_stats_by_level(gold):
    lvl = get_level_index(gold)

    # Corrected Linear Formulas
    base_ad = 55 + 2.5 * lvl
    enemy_mr = 30 + 1.3 * lvl
    enemy_ar = 25 + 4.4 * lvl

    return base_ad, enemy_ar, enemy_mr, lvl + 1


def calculate_final_damage(item_ad, item_ap, base_ad, enemy_ar, enemy_mr):
    total_ad = base_ad + item_ad
    total_ap = item_ap

    # Hypothesis 2 Logic
    phys_raw = 2.15 * total_ad
    term_inside = (0.1 + 0.001 * total_ap) * 2.15 * total_ad + 50 + 0.4 * total_ap
    multiplier = (1.1 + 0.001 * total_ap) * 1.28
    magic_raw = term_inside * multiplier

    phys_actual = phys_raw * (100 / (100 + enemy_ar))
    magic_actual = magic_raw * (100 / (100 + enemy_mr))

    return phys_actual + magic_actual


def optimize_full_model(budget):
    cost_ad = 35
    cost_ap = 20

    base_ad, enemy_ar, enemy_mr, current_lvl = get_stats_by_level(budget)

    max_dmg = -1
    opt_item_ad = 0
    opt_item_ap = 0
    max_ap_count = int(budget / cost_ap)

    for ap in range(max_ap_count + 1):
        gold_spent_on_ap = ap * cost_ap
        item_ad = (budget - gold_spent_on_ap) / cost_ad

        total_dmg = calculate_final_damage(item_ad, ap, base_ad, enemy_ar, enemy_mr)

        if total_dmg > max_dmg:
            max_dmg = total_dmg
            opt_item_ad = item_ad
            opt_item_ap = ap

    return opt_item_ad, opt_item_ap, max_dmg, base_ad, enemy_ar, enemy_mr, current_lvl


# Simulation
budgets = [2000, 3000, 5000, 7000, 9000, 11000, 13000, 15000, 19000]

print(
    f"{'Gold':<6} | {'Lv':<2} | {'BaseAD':<6} | {'E.AR/MR':<9} | {'Item AD':<7} | {'Tot AD':<7} | {'Item AP':<7} | {'Ratio':<12} | {'Dmg':<7}")
print("-" * 95)

for b in budgets:
    i_ad, i_ap, dmg, b_ad, e_ar, e_mr, lvl = optimize_full_model(b)

    # Calculate Total AD for display
    total_ad = b_ad + i_ad

    ratio = "All AD" if i_ap == 0 else "All AP" if i_ad == 0 else f"1 : {i_ap / i_ad:.2f}"
    if i_ap == 0: ratio = "All AD"
    if i_ad <= 1: ratio = "All AP"

    print(
        f"{b:<6} | {lvl:<2} | {int(b_ad):<6} | {int(e_ar)}/{int(e_mr):<3}   | {i_ad:<7.1f} | {int(total_ad):<7} | {i_ap:<7} | {ratio:<12} | {dmg:<7.1f}")