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


class PowerCache:
    """(집합) → (dps, gold) 메모 — 패키지·룬 고정. DPS/DPG DP 가 같은 캐시 공유."""

    def __init__(self, pkg, keystone_cls, sim_fn=simulate_cogmaw_core_path):
        self.pkg = pkg
        self.keystone_cls = keystone_cls
        self.sim_fn = sim_fn
        self.cache = {}
        self.sim_calls = 0

    def dps_gold(self, state):
        if state not in self.cache:
            self.sim_calls += 1
            kw = dict(doran_key=self.pkg["doran"], boots_key=self.pkg["boots"],
                      rune_as_bonus=self.pkg["rune_as"])
            if self.keystone_cls is not None:
                kw["keystone_cls"] = self.keystone_cls
            self.cache[state] = self.sim_fn(tuple(sorted(state)), len(state), **kw)
        return self.cache[state]

    def dps(self, state):
        return self.dps_gold(state)[0]

    def dpg(self, state):
        d, g = self.dps_gold(state)
        return d / (g / 1000.0) if g > 0 else 0.0


def run_scenario(keystone_cls, pkg, metric, candidates_map=None, gamma=GAMMA,
                 horizon=HORIZON, cache=None):
    """룬×패키지×지표 1조합의 최적 궤적 계산. cache 를 넘기면 시뮬 캐시 공유(지표 간)."""
    if candidates_map is None:
        candidates_map = default_candidates_map()
    if cache is None:
        cache = PowerCache(pkg, keystone_cls)
    metric_fn = cache.dpg if metric == "dpg" else cache.dps
    W, best = solve_sequential(metric_fn, gamma=gamma, horizon=horizon,
                               candidates_map=candidates_map)
    traj = extract_trajectory(best)
    steps, alts, state = [], [], frozenset()
    for x in traj:
        alts.append(node_alternatives(state, W, metric_fn, gamma, candidates_map))
        state = state | {x}
        dps, gold = cache.dps_gold(state)
        steps.append({"item": x, "core": len(state), "dps": dps,
                      "dpg": dps / (gold / 1000.0) if gold > 0 else 0.0,
                      "gold": gold, "W": W[state]})
    return {"trajectory": traj, "steps": steps, "alternatives": alts,
            "W0": W[frozenset()], "W": W, "cache": cache}


def evaluate_fixed_path(path, cache, metric, W, gamma=GAMMA, candidates_map=None):
    """고정 구매 순서(4~5아이템)의 0코어 기준 할인합. 4아이템이면 잔여 슬롯은 W로 최적 연속."""
    if candidates_map is None:
        candidates_map = default_candidates_map()
    metric_fn = cache.dpg if metric == "dpg" else cache.dps
    total, state = 0.0, frozenset()
    for k, x in enumerate(path, start=1):
        state = state | {x}
        total += (gamma ** k) * metric_fn(state)
    if len(path) < HORIZON and state in W:
        total += (gamma ** len(path)) * W[state]
    return total


def print_scenario(title, out, ctrl_rows):
    print(f"\n=== {title} (γ={GAMMA}, horizon {HORIZON}core) ===")
    print(f"W(0core 할인합) = {out['W0']:.2f}")
    for i, step in enumerate(out["steps"]):
        alt_txt = " / ".join(f"{a}:{v:.1f}" for a, v in out["alternatives"][i])
        print(f"  {step['core']}core → {step['item']:<12} | DPS {step['dps']:>7.1f} | "
              f"DPG {step['dpg']:>7.2f} | Gold {step['gold']:>5.0f} | 대안: {alt_txt}")
    for name, val in ctrl_rows:
        print(f"  [{name}] 동일 척도 할인합 = {val:.2f}")


def main(with_top1=False):
    # with_top1: 파일럿 단계에서는 인자 파싱만 하고 동작은 미구현(후속 작업).
    for keystone_cls, ks_label in ((LethalTempo, "치속"), (PressTheAttack, "집공")):
        for pkg in ADC_PACKAGES:
            cache = PowerCache(pkg, keystone_cls)
            for metric in ("dpg", "dps"):
                out = run_scenario(keystone_cls, pkg, metric, cache=cache)
                ctrl_rows = []
                for name, path in (("CTRL", CONTROL_PATH), ("CTRL2", CONTROL2_PATH)):
                    ctrl_rows.append((name, evaluate_fixed_path(
                        list(path), cache, metric, out["W"])))
                print_scenario(f"{ks_label} · {pkg['label']} · {metric.upper()}",
                               out, ctrl_rows)
            print(f"[{ks_label}·{pkg['label']}] sim_calls={cache.sim_calls}")


if __name__ == "__main__":
    import sys
    main(with_top1="--with-top1" in sys.argv)
