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
