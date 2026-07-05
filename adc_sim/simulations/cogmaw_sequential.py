"""코그모 순차 최적 빌드 탐색 — 미래 할인 DP (γ=0.9).

기존 랭킹(완성 경로 일괄 가중)과 달리, j코어 상태에서 "다음 아이템"을
j+1~5코어 파워의 γ-할인합 최대화로 선택한다(사용자 제안 방법론).
spec: docs/superpowers/specs/2026-07-06-cogmaw-sequential-ranking-design.md
실행: .venv/bin/python -m adc_sim.simulations.cogmaw_sequential  (표만 출력, 헤드리스 안전)
"""
from adc_sim.simulations.cogmaw import (
    COGMAW_CORE_CANDIDATES, CONTROL_PATH, CONTROL2_PATH, simulate_cogmaw_core_path,
)
from adc_sim.data.items_data import ADC_PACKAGES
from adc_sim.runes import LethalTempo, PressTheAttack

GAMMA = 0.9
HORIZON = 5
PEN_EXCLUSIVE = {"terminus", "ldr", "mortal"}
# 슬롯5 전용 후보 리스트가 없어 1~4티어 합집합 사용(스펙 승인, 추후 조정 지점).
SLOT5_CANDIDATES = sorted(set().union(*COGMAW_CORE_CANDIDATES.values()))


def default_candidates_map():
    m = {slot: list(COGMAW_CORE_CANDIDATES[slot]) for slot in (1, 2, 3, 4)}
    m[5] = list(SLOT5_CANDIDATES)
    return m


def legal_next_items(owned, slot, candidates_map):
    pen_owned = sum(1 for k in owned if k in PEN_EXCLUSIVE)
    out = []
    for k in candidates_map[slot]:
        if k in owned:
            continue
        if k in PEN_EXCLUSIVE and pen_owned >= 1:
            continue
        out.append(k)
    return out


def solve_sequential(power, gamma=GAMMA, horizon=HORIZON, candidates_map=None):
    """W(S) = max_x γ·(power(S∪x) + W(S∪x)); |S|=horizon 에서 W=0.

    power: frozenset -> float (해당 집합 완성 시점 = |집합| 코어의 파워).
    반환 (W, best): 상태별 할인합 가치와 최적 다음 아이템(터미널은 None).
    """
    if candidates_map is None:
        candidates_map = default_candidates_map()
    W, best = {}, {}

    def w(state):
        if state in W:
            return W[state]
        j = len(state)
        if j >= horizon:
            W[state], best[state] = 0.0, None
            return 0.0
        best_val, best_item = None, None
        for x in legal_next_items(state, j + 1, candidates_map):
            nxt = state | {x}
            val = gamma * (power(nxt) + w(nxt))
            if best_val is None or val > best_val:
                best_val, best_item = val, x
        if best_val is None:  # 후보 소진(방관 배타 등) — 조기 종단
            best_val = 0.0
        W[state], best[state] = best_val, best_item
        return best_val

    w(frozenset())
    return W, best


def extract_trajectory(best):
    state, path = frozenset(), []
    while best.get(state):
        x = best[state]
        path.append(x)
        state = state | {x}
    return path


def node_alternatives(state, W, power, gamma, candidates_map, top_n=3):
    """분기점 대안: 후보 x별 γ·(power+W) 값 상위 top_n. (W dict 재사용, 재시뮬 없음)"""
    vals = []
    for x in legal_next_items(state, len(state) + 1, candidates_map):
        nxt = state | {x}
        vals.append((x, gamma * (power(nxt) + W[nxt])))
    vals.sort(key=lambda t: t[1], reverse=True)
    return vals[:top_n]
