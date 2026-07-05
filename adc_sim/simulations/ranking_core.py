"""챔피언 공통 랭킹 파이프라인 — 경로×패키지 시뮬 → sorted-combo dedup → 컨트롤/고정행
canonical 고정 → 가중 DPG/DPS → 컨트롤 baseline 상대 점수(rel_dpg_score).

가중은 settings.CORE_WEIGHTS_RAW(RANKING_SCORING 파생)가 기본, weights_raw 인자로 오버라이드
(사용자 요구: 통일 러너 + 인자로 점수 방식 결정). Phase 1: vayne 이관.
spec: docs/superpowers/specs/2026-07-06-ranking-core-design.md
"""
from adc_sim import settings
from adc_sim.data.items_data import ADC_PACKAGES


def rank_builds(simulate_fn, all_paths, control_path, weights_raw=None,
                packages=None, n_cores=4, pinned_paths=()):
    """공통 랭킹. 반환 (rows_dedup, best_control) — 행 스키마는 기존 챔피언 시뮬과 동일.

    simulate_fn(path, tier, doran_key=, boots_key=, rune_as_bonus=) -> (dps, gold).
    pinned_paths: ((태그, 경로), ...) — 컨트롤처럼 지정 순서로 고정·항상 잔존(표시 전용).
    """
    if weights_raw is None:
        weights_raw = list(settings.CORE_WEIGHTS_RAW[:n_cores])
    if packages is None:
        packages = ADC_PACKAGES
    dedupe_weight_raw = list(weights_raw)
    weight_sum = sum(weights_raw)
    core_weights = [w / weight_sum for w in weights_raw]
    ctrl_combo = tuple(sorted(control_path))
    # 컨트롤과 같은 집합의 pinned 는 무시 — 이미 [CTRL]로 canonical 고정되므로 중복 방지
    pinned_paths = tuple((tag, tuple(p)) for tag, p in pinned_paths
                         if tuple(sorted(p)) != ctrl_combo)
    pinned_combos = {tuple(sorted(p)): (tag, tuple(p)) for tag, p in pinned_paths}

    rows = []
    for path in all_paths:
        for pkg in packages:
            kw = dict(doran_key=pkg["doran"], boots_key=pkg["boots"],
                      rune_as_bonus=pkg["rune_as"])
            dps_list, cost_list = [], []
            for tier in range(1, n_cores + 1):
                d, c = simulate_fn(path, tier, **kw)
                dps_list.append(d)
                cost_list.append(c)
            dpg = [dps_list[i] / (cost_list[i] / 1000.0) if cost_list[i] > 0 else 0.0
                   for i in range(n_cores)]
            combo = tuple(sorted(path))
            rows.append({
                "path": tuple(path), "doran": pkg["doran"], "boots": pkg["boots"],
                "rune_as": pkg["rune_as"], "pkg_label": pkg["label"],
                "x": cost_list, "y": dps_list, "dpg": dpg,
                "is_control": combo == ctrl_combo,
                "pinned_tag": pinned_combos[combo][0] if combo in pinned_combos else None,
                "dedupe_eff": sum(dedupe_weight_raw[i] * dpg[i] for i in range(n_cores)),
            })

    dedupe_best = {}
    for r in rows:
        key = tuple(sorted(r["path"]))
        if key not in dedupe_best or r["dedupe_eff"] > dedupe_best[key]["dedupe_eff"]:
            dedupe_best[key] = r
    rows_dedup = list(dedupe_best.values())

    # 컨트롤·pinned 는 지정 순서(canonical)로 고정
    rows_dedup = [r for r in rows_dedup
                  if not r["is_control"] and r["pinned_tag"] is None]
    ctrl_cands = [r for r in rows if tuple(r["path"]) == tuple(control_path)]
    if ctrl_cands:
        rows_dedup.append(max(ctrl_cands, key=lambda r: r["dedupe_eff"]))
    for _tag, p in pinned_paths:
        cands = [r for r in rows if tuple(r["path"]) == tuple(p)]
        if cands:
            rows_dedup.append(max(cands, key=lambda r: r["dedupe_eff"]))

    for r in rows_dedup:
        r["weighted_dpg"] = sum(core_weights[i] * r["dpg"][i] for i in range(n_cores))
        r["weighted_dps"] = sum(core_weights[i] * r["y"][i] for i in range(n_cores))

    control_rows = [r for r in rows_dedup if r["is_control"]]
    if not control_rows:
        raise RuntimeError(
            f"Control build {control_path} not found in search space. "
            "Check candidate pools contain the control items."
        )
    best_control = max(control_rows, key=lambda r: r["weighted_dpg"])
    baseline = best_control["dpg"][:n_cores]

    for r in rows_dedup:
        core_rel_pct = [
            (r["dpg"][i] / baseline[i] * 100.0 if baseline[i] > 0 else 0.0)
            for i in range(n_cores)
        ]
        r["core_rel_delta_pct_4"] = [p - 100.0 for p in core_rel_pct]
        r["rel_dpg_score"] = sum(core_weights[i] * core_rel_pct[i] for i in range(n_cores))

    return rows_dedup, best_control
