# 시뮬레이션 엔진
def calculate_mitigation(raw_phys, raw_magic, target, champion):
    """
    방어력/마법저항력 및 관통력을 적용하여 실제 피해량을 계산
    공식: Effective Stat = Stat * (1 - %Pen) - Flat Pen
    대미지 감소율: 100 / (100 + Effective Stat)
    """
    # 1. 물리 관통력 적용 (% 방관 -> 고정 방관)
    # champion 객체에서 관통력 정보를 가져옵니다.
    eff_armor = target.armor * (1 - champion.armor_pen_percent) - champion.lethality
    eff_armor = max(0, eff_armor)  # 관통력으로 방어력이 음수가 되지는 않음

    # 2. 마법 관통력 적용 (% 마관 -> 고정 마관)
    # Champion 클래스에 magic_pen_flat이 없으면 0으로 처리
    magic_pen_flat = getattr(champion, 'magic_pen_flat', 0)
    eff_mr = target.magic_resist * (1 - champion.magic_pen_percent) - magic_pen_flat
    eff_mr = max(0, eff_mr)

    actual_phys = raw_phys * (100.0 / (100.0 + eff_armor))
    actual_magic = raw_magic * (100.0 / (100.0 + eff_mr))

    return actual_phys, actual_magic


def run_simulation(champion, target, verbose=True, skill_plan=None, respawn_to_full_kills=2):
    """이벤트 루프. 처치 시 오버킬을 이월한 채 타깃을 풀피로 리필해
    respawn_to_full_kills 회만큼 처치할 때까지 지속(지속딜 측정).

    같은 크기의 체력바를 여러 번 처치 → 시작 버스트(W/궁캔슬)가 여러 바에 분산되어
    지속(steady-state) DPS 에 수렴. 바 크기를 키우지 않으므로 몰왕검(현재체력%)은
    과대평가되지 않는다. dps = 총 누적피해(오버킬 포함) / 마지막 처치 시각.

    **기본 K=2(리스폰 1회)** 가 프로젝트 표준. respawn_to_full_kills=1 로 단일 처치 복원.
    """
    eps = 1e-9
    current_time = 0.0
    next_attack_in = 0.0
    history = [(0.0, target.current_hp)]
    attack_count = 0
    total_damage_dealt = 0.0
    kills_done = 0

    champion.init_combat_state(skill_plan)

    if verbose:
        print(f"--- Simulation Start: {champion.name} vs Dummy ---")
        print(f"Stats - AD: {champion.total_ad}, AS: {champion.current_attack_speed}")

    while target.current_hp > 0:
        prev_time = current_time

        skill_dt = champion.get_time_to_next_skill_event(current_time)
        state_dt = champion.get_time_to_next_state_event(current_time)

        event_dt = min(next_attack_in, skill_dt, state_dt)
        if event_dt == float("inf"):
            break
        if event_dt < 0:
            event_dt = 0.0

        event_time = current_time + event_dt
        champion.advance_combat_time(event_dt, event_time, target)
        current_time = event_time
        next_attack_in = max(0.0, next_attack_in - event_dt)

        # 1) 스킬 이벤트 처리 (동시 시각이면 평타보다 먼저)
        if target.current_hp > 0 and skill_dt <= event_dt + eps:
            skill_events = champion.pop_due_skill_events(current_time, target)
            for skill_name, s_phys, s_magic, is_skill_hit in skill_events:
                setattr(champion, "_combat_time", current_time)

                skill_dmg = 0.0
                if is_skill_hit:
                    bonus_s_phys = 0.0
                    bonus_s_magic = 0.0
                    bonus_s_true = 0.0
                    if hasattr(champion, "get_on_skill_hit_damage"):
                        bonus_s_phys, bonus_s_magic, bonus_s_true = champion.get_on_skill_hit_damage(target, current_time)

                    actual_s_phys, actual_s_magic = calculate_mitigation(s_phys, s_magic, target, champion)
                    actual_bonus_phys, actual_bonus_magic = calculate_mitigation(
                        bonus_s_phys, bonus_s_magic, target, champion
                    )
                    skill_dmg = actual_s_phys + actual_s_magic + actual_bonus_phys + actual_bonus_magic + bonus_s_true

                    if champion.rune and hasattr(champion.rune, "on_skill_hit"):
                        champion.rune.on_skill_hit(champion)
                    if champion.sub_rune and hasattr(champion.sub_rune, "on_skill_hit"):
                        champion.sub_rune.on_skill_hit(champion)
                    if champion.rune and hasattr(champion.rune, "on_damage_dealt"):
                        champion.rune.on_damage_dealt(champion, skill_dmg)
                    if champion.sub_rune and hasattr(champion.sub_rune, "on_damage_dealt"):
                        champion.sub_rune.on_damage_dealt(champion, skill_dmg)

                    target.current_hp -= skill_dmg
                    total_damage_dealt += skill_dmg

                if verbose:
                    print(
                        f"[{current_time:.3f}s] Skill {skill_name.upper()}: "
                        f"{skill_dmg:.1f} -> HP: {max(0, target.current_hp):.1f}"
                    )

                if target.current_hp <= 0:
                    history.append((round(current_time, 2), 0.0))
                    kills_done += 1
                    if kills_done >= respawn_to_full_kills:
                        break
                    target.current_hp += target.max_hp  # 오버킬 이월 + 풀피 리필
                    break  # 이번 스텝의 남은 스킬 이벤트는 다음 바로 넘김

        # 2) 기본 공격 이벤트 처리
        #    시전 시간(cast_lockout_until) 동안은 평타 불가 — 락아웃 종료까지 지연.
        #    (스킬 시전이 평타 윈드업을 막는 모델; 미설정 챔피언은 0.0 이라 기존 동작 불변.)
        cast_lockout_until = getattr(champion, "cast_lockout_until", 0.0)
        if target.current_hp > 0 and next_attack_in <= eps and current_time + eps < cast_lockout_until:
            next_attack_in = cast_lockout_until - current_time
        if target.current_hp > 0 and next_attack_in <= eps:
            p_base, m_base, p_onhit, m_onhit, phys_true_base, phys_true_onhit = champion.get_one_hit_damage(target, current_time)
            raw_phys = p_base + p_onhit
            raw_magic = m_base + m_onhit

            actual_phys, actual_magic = calculate_mitigation(raw_phys, raw_magic, target, champion)
            total_damage = actual_phys + actual_magic + phys_true_base + phys_true_onhit
            if champion.rune and hasattr(champion.rune, "on_damage_dealt"):
                champion.rune.on_damage_dealt(champion, total_damage)
            if champion.sub_rune and hasattr(champion.sub_rune, "on_damage_dealt"):
                champion.sub_rune.on_damage_dealt(champion, total_damage)

            target.current_hp -= total_damage
            total_damage_dealt += total_damage
            attack_count += 1

            # 평타당 1회 챔피언 훅(나보리 스킬 쿨감 등). 구인수 proc_count 에 안 곱해지도록 여기서 1회만.
            champion.on_basic_attack(current_time)

            if verbose:
                rune_stacks = champion.rune.stacks if champion.rune and hasattr(champion.rune, "stacks") else 0
                rune_bonus_as = champion.rune.get_bonus_as() if champion.rune else 0.0
                print(
                    f"[{current_time:.3f}s] Attack #{attack_count}: "
                    f"AS {champion.current_attack_speed:.2f} (Rune +{rune_bonus_as*100:.1f}%, Stacks {rune_stacks}) | "
                    f"Dmg {total_damage:.1f} (Phys:{actual_phys:.1f}, Mag:{actual_magic:.1f}, True:{phys_true_base+phys_true_onhit:.1f}) -> "
                    f"HP: {max(0, target.current_hp):.1f}"
                )

            history.append((round(current_time, 2), max(0.0, target.current_hp)))
            if target.current_hp <= 0:
                kills_done += 1
                if kills_done >= respawn_to_full_kills:
                    break
                target.current_hp += target.max_hp  # 오버킬 이월 + 풀피 리필

            next_attack_in = champion.get_attack_interval()

        # 같은 시각 이벤트 고착 방지
        if current_time <= prev_time + eps:
            nudge = eps
            champion.advance_combat_time(nudge, current_time + nudge, target)
            current_time = prev_time + nudge
            next_attack_in = max(0.0, next_attack_in - nudge)

    kill_time = current_time
    if kill_time > 0:
        dps = total_damage_dealt / kill_time
    else:
        dps = total_damage_dealt

    if verbose:
        print(f"--- Killed in {kill_time:.3f}s | DPS: {dps:.2f} ---")

    return history, dps, kill_time
