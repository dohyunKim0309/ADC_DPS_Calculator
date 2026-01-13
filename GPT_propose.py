# yunara_min_step.py
# 목적: 유나라 평타 기반 '정확(이산)' 계산의 가장 작은 뼈대
# - 첫타부터 N타까지 순서대로 계산
# - 치속 스택(LT)은 매 히트 +1 (최대 6), 만료/감소 없음(단순화)
# - Q는 4타 후부터 활성(True)로 전환(단순화); 지속시간/해제 없음
# - 관통/이벤트/클램프 없음

from dataclasses import dataclass

# -----------------------
# 1) 기본 데이터 구조
# -----------------------
# 레벨로 q 레벨 계산
def q_level_for_level(L: int) -> int:
    # 1~3:1, 4:2, 5~6:3, 7~8:4, 9~18:5
    if L <= 3:  return 1
    if L == 4:  return 2
    if L <= 6:  return 3
    if L <= 8:  return 4
    return 5  # L >= 9


@dataclass
class Champion:
    # 상태
    level: int = 1
    q_level: int = 1

    # 고정 파라미터(챔피언 별 고유)
    base_ad: float = 55.0
    ad_growth: float = 2.5          # AD = base_ad + ad_growth * L
    base_as: float = 0.65
    as_ratio: float = 0.65          # AS = base_as + as_ratio * (bonusAS%), bonusAS%는 소수
    as_per_level: float = 0.02      # 레벨업당 +2%

    # 전투 중 상태
    time: float = 0.0
    hit_index: int = 0
    lt_stacks: int = 0              # 치속 스택(0..6)
    q_active: bool = False          # 4타 이후 True로 전환(간단화)

    # --- 레벨 조작 ---
    def set_level(self, L: int):
        self.level = L
        self.q_level = q_level_for_level(L)


@dataclass
class Build:
    # 아이템/룬의 “합계 스탯”만 사용 (특수 효과는 일단 무시)
    item_ad: float = 0.0
    item_ap: float = 0.0
    item_as_pct: float = 0.0        # 추가 공속 %, 소수(예: 0.30=30%)
    rune_ad: float = 0.0
    rune_ap: float = 0.0
    crit_chance: float = 0.0        # 0..1
    crit_mult: float = 1.75         # 1.75면 추가 0.75배


@dataclass
class Enemy:
    hp_now: float
    armor: float
    mr: float

# -----------------------
# 2) 유틸/공식(최소)
# -----------------------
def total_ad(ch: Champion, b: Build, L: int) -> float:
    return (ch.base_ad + ch.ad_growth * (L**2)) + b.item_ad + b.rune_ad

def total_ap(b: Build) -> float:
    return b.item_ap + b.rune_ap

def bonus_as_pct(ch: Champion, b: Build, L: int, lt_stacks: int, q_active: bool, qlvl: int) -> float:
    lvl = ch.as_per_level * (L - 1)
    lt  = 0.048 * lt_stacks                  # 치속 스택당 +4.8% (소수)
    q   = [0,0.20,0.30,0.40,0.50,0.60][qlvl] if q_active else 0.0
    return lvl + b.item_as_pct + lt + q

def current_as(ch: Champion, b: Build, L: int, lt_stacks: int, q_active: bool, qlvl: int) -> float:
    return ch.base_as + ch.as_ratio * bonus_as_pct(ch, b, L, lt_stacks, q_active, qlvl)

def ecrit(b: Build) -> float:
    return 1.0 + b.crit_chance * (b.crit_mult - 1.0)

def apply_armor(dmg: float, armor: float) -> float:
    return dmg * (100.0 / (100.0 + max(0.0, armor)))

def apply_mr(dmg: float, mr: float) -> float:
    return dmg * (100.0 / (100.0 + max(0.0, mr)))

def q_onhit_mag(qlvl: int, AP: float, active: bool) -> float:
    base = [0,5,10,15,20,25][qlvl] + 0.20 * AP
    return base + (base if active else 0.0)  # 패시브 + (액티브 중이면 추가로 한 번 더)

def vow_oncrit_E(AD: float, AP: float, crit_chance: float) -> float:
    # 유나라 패시브: 크리 시 추가 마법피해 — 기대값으로 계산 (간단화 버전)
    return crit_chance * ((10.0 + 0.10 * AP) * AD)

# -----------------------
# 3) 한 번의 히트 처리
# -----------------------
def do_one_hit(ch: Champion, b: Build, e: Enemy, L: int, qlvl: int, st: State):
    st.hit_index += 1

    # (A) 4타 이후 Q 활성(간단화)
    if (not st.q_active) and st.hit_index >= 5:
        st.q_active = True

    # (B) 현재 공격속도와 타격 간격
    AS = current_as(ch, b, L, st.lt_stacks, st.q_active, qlvl)
    dt = 1.0 / max(AS, 1e-9)   # 0분모 방지만

    # (C) 스탯 집계
    AD = total_ad(ch, b, L)
    AP = total_ap(b)

    # (D) 원천 피해(기댓값)
    phys_raw = ecrit(b) * AD
    mag_raw  = q_onhit_mag(qlvl, AP, st.q_active) + vow_oncrit_E(AD, AP, b.crit_chance)

    # (E) 저항 적용
    phys_eff = apply_armor(phys_raw, e.armor)
    mag_eff  = apply_mr(mag_raw, e.mr)
    total    = phys_eff + mag_eff

    # (F) HP 갱신
    e.hp_now = max(0.0, e.hp_now - total)

    # (G) 스택 갱신(치속 +1, 최대 6)
    if st.lt_stacks < 6:
        st.lt_stacks += 1

    # (H) 시간 전진
    st.time += dt

    # (I) (선택) 한 줄 로그 — 주석 해제하면 확인 가능
    # print(f"t={st.time:.2f}s, hit#{st.hit_index}, AS={AS:.3f}, LT={st.lt_stacks}, Q={st.q_active}, "
    #       f"phys={phys_eff:.1f}, mag={mag_eff:.1f}, total={total:.1f}, hp={e.hp_now:.1f}")

# -----------------------
# 4) 미니 루프
# -----------------------
def run(L=1, qlvl=1, hits=8):
    ch = Champion()
    b  = Build(item_ad=100.0, item_ap=0.0, item_as_pct=0.0, crit_chance=0.0, crit_mult=1.75)
    e  = Enemy(hp_now=2000.0, armor=100.0, mr=50.0)
    st = State(time=0.0, hit_index=0, lt_stacks=0, q_active=False)

    for _ in range(hits):
        if e.hp_now <= 0: break
        do_one_hit(ch, b, e, L, qlvl, st)

    # 필요 시 결과 확인:
    print(f"done: t={st.time:.2f}s, hits={st.hit_index}, hp_left={e.hp_now:.1f}")

if __name__ == "__main__":
    run(L=1, qlvl=1, hits=8)
