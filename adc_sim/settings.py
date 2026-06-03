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
