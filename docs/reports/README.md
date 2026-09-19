# 유나라 코어 결정 탐색기 — 리포트 빌드

`yunara_report.html` 은 **혼자 도는 파일 하나**다. 브라우저로 열기만 하면 되고
설치·서버·인터넷 연결이 필요 없다(글꼴만 온라인이면 예쁘게 뜨고, 없으면 시스템
글꼴로 떨어진다). 비개발자에게는 이 파일을 그대로 보내면 된다.

## 구성
| 파일 | 뭐냐 | git |
|---|---|---|
| `yunara_report.template.html` | 편집하는 원본(레이아웃·문구·JS). 데이터 자리는 `__CURVES_JSON__`·`__EXPLORER_JSON__` | 추적 |
| `yunara_curves.json` | 고정 비교 트리들의 구간별 DPS/DPG | 추적 |
| `yunara_explorer.json` | 탐색기 노드(상황 12종 × 후보별 score·mDPG·하프) | 추적 |
| `yunara_report.html` | 위 셋을 합친 **배포용 결과물** | 제외(생성물) |

## 다시 만들기
```bash
# 1) 데이터 (시뮬 재실행 — 각각 수 분)
python -m tools.yunara_report_data      docs/reports/yunara_curves.json
python -m tools.yunara_explorer_data    docs/reports/yunara_explorer.json
python -m tools.yunara_explorer_data --verify   # DP 점수 == 기존 greedy 인지 검사

# 2) 템플릿 + 데이터 → 배포 파일
python -m tools.build_yunara_report
```
문구·레이아웃만 고칠 때는 2번만 다시 돌리면 된다(데이터 재생성 불필요).

## 파일을 남에게 줄 때
- 그대로 첨부하거나, 드라이브·메신저에 올려 링크로 보낸다. 3MB 안쪽이다.
- 상대 타깃(딜러·브루저·탱커)과 교전 적 수(1·2·3·혼합) 스위치는 파일 안에 다 들어 있어
  받는 쪽에서 바로 바꿔 볼 수 있다.
