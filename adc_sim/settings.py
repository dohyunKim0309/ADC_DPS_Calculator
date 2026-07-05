# settings.py
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent  # repo root (adc_sim/settings.py 기준 두 단계 상위)

# 시뮬레이션 설정
SIMULATION_SETTINGS = {
    # 그래프 스타일 설정
    # 'linear': 대각선 (기본값)
    # 'step': 계단식
    'graph_style': 'step',
    # 결과 리포트 저장 설정
    'result_export_enabled': False,
    'result_export_format': 'both',
    'result_export_dir': 'reports',
    # 사용자가 수동으로 보관본을 정리할 수 있는 예약 폴더
    'result_archive_dir': 'Archive',
}


def get_result_export_settings():
    """Return normalized export settings with project-local absolute paths."""
    export_dir = PROJECT_ROOT / SIMULATION_SETTINGS['result_export_dir']
    archive_dir = PROJECT_ROOT / SIMULATION_SETTINGS['result_archive_dir']
    return {
        'enabled': SIMULATION_SETTINGS.get('result_export_enabled', False),
        'format': SIMULATION_SETTINGS.get('result_export_format', 'both'),
        'export_dir': export_dir,
        'archive_dir': archive_dir,
    }


# ──────────────────────────────────────────────────────────────────────────
# 코어(1~4) 가중치 — 챔피언 sim 의 top1 빌드 선정·rel-DPG 랭킹 가중평균.
# 전 챔프 sim(ashe/yunara/kaisa/corki/ezreal/cogmaw)이 이 하나를 import → 여기 한 줄로 전 챔프 적용.
# [1,1,1,1]=전 코어 동일, [5,4,3,3]=초반(1코어) 편중. 3코어 변형은 CORE_WEIGHTS_RAW[:3].
# (case_ranking 은 별도 sim_settings.WEIGHT_PROFILES — 여기와 무관.)
# ──────────────────────────────────────────────────────────────────────────
# 점수 방식 선택 [사용자 확정 2026-07-06]: "weighted"=고정 가중합 / "discounted"=γ-할인합.
# 할인합은 코어별 가중 [γ^1..γ^n] 과 동치라 기존 rel-DPG 파이프라인을 그대로 쓴다.
RANKING_SCORING = {
    "mode": "discounted",
    "fixed_raw": [4.0, 4.0, 3.0, 3.0],
    "gamma": 0.9,
}


def derive_core_weights(scoring, n=4):
    """RANKING_SCORING → 코어별 raw 가중 벡터(길이 n)."""
    if scoring["mode"] == "discounted":
        g = scoring["gamma"]
        return [g ** k for k in range(1, n + 1)]
    return list(scoring["fixed_raw"][:n])


CORE_WEIGHTS_RAW = derive_core_weights(RANKING_SCORING)
_mode_tag = "" if RANKING_SCORING["mode"] == "weighted" else f" (disc γ={RANKING_SCORING['gamma']:g})"
CORE_WEIGHTS_LABEL = ":".join(f"{w:g}" for w in CORE_WEIGHTS_RAW) + _mode_tag


# ──────────────────────────────────────────────────────────────────────────
# 케이스 기반 코어 빌드 랭킹 — 출력 설정 (Phase B)
# 케이스/축/가중/제약 등 '모델' 설정은 adc_sim/simulations/sim_settings.py 에 있다.
# 여기서는 '출력' 정책만 둔다(표시 개수 / 대상 케이스 등). 엔진은 case_ranking.py.
# ──────────────────────────────────────────────────────────────────────────
CASE_RANKING_OUTPUT = {
    "top_n": 10,               # 케이스별 상위 N개 빌드 출력
    "cases": "all",            # "all" 또는 출력할 케이스 name 리스트 (예: ["def@4/maw/nohc"])
    # 출력만 비활성화할 케이스(name 부분일치). 엔진/케이스 정의는 그대로, 표시만 생략.
    "exclude": ["alldps", "mercurial"],
    "show_control_row": True,  # 각 케이스 기준선(컨트롤) 행 함께 표시
    # 성능 안전판: 오프닝(1~3코어)을 1~3 부분점수로 정렬해 상위 K개만 연계 탐색.
    # None = 전수(프루닝 없음). 값 설정 시 잘린 개수를 로그로 남긴다(은밀한 절단 금지).
    "opening_prune_top_k": None,
}
