# 코어 결정 탐색기 리포트 — 빌드

`*_report.html` 은 **혼자 도는 파일 하나**다. 브라우저로 열기만 하면 되고 설치·서버·인터넷
연결이 필요 없다(글꼴만 온라인이면 예쁘게 뜨고, 없으면 시스템 글꼴로 떨어진다).
비개발자에게는 이 파일을 그대로 보내면 된다.

## 구성
| 파일 | 뭐냐 | git |
|---|---|---|
| `explorer.template.html` | **챔피언 중립** 템플릿(레이아웃·문구 틀·JS). 자리표시자 `__TITLE__`·`__CURVES_JSON__`·`__EXPLORER_JSON__` | 추적 |
| `<champ>_explorer.json` | 탐색기 노드 + **챔피언별 문구(`copy`)** — 제목·리드·시나리오 라벨·측정 방식·캐비엇 | 제외(생성물, 유나라 50MB) |
| `<champ>_curves.json` | 고정 비교 트리들의 구간별 DPS/DPG — **선택 사항**(없으면 곡선·막대·수치 표 섹션이 숨는다) | 추적 |
| `<champ>_report.html` | 위를 합친 **배포용 결과물** | 제외(생성물) |

현재: 유나라(탐색기 + 곡선), 카이사(탐색기만 — 단일 대상이라 시나리오 축도 없다).

## 지표 세 축
| 지표 | 뜻 | 비고 |
|---|---|---|
| **mDPG** | 이 칸 1000골드당 늘어난 DPS | 공격 효율 |
| **score** | 이 칸부터 5코어까지의 γ-할인 마지널 DPG 합 | 미래까지 본 값(γ=0.8) |
| **m생존** | 이 칸 1000골드당 늘어난 생존성 | 생존성 = (물리 EHP + 마법 EHP + 체력)/3, 피흡은 축별 (100+저항)/100 배로 환산해 가산 |

순위는 리포트의 **정렬 기준 스위치**가 고른 지표 1차, 0.5% 동률이면 다음 지표.
**적 딜 구성 스위치**(균등 / AD 위주 / 혼합 / AP 위주)는 생존성 세 축(물리·마법·고정)을 섞는
비율을 바꾼다 — 세 축이 데이터에 다 들어 있어 **화면에서 계산**하므로 프리셋을 늘려도 파일이
커지지 않는다(전개 가지는 생성 시점의 균등 가중 기준으로 고정). 균등 외 프리셋은 실측 전
임시치이며 `tools/riot_damage_mix.py` 출력으로 교체한다.
전개는 **세 지표 각 상위 3의 합집합 ∪ 고정 항목**(1코어 C44 · 3~5코어 루난·경계·도미닉).

## 다시 만들기
```bash
# 1) 데이터 (시뮬 재실행 — 각각 수 분)
python -m tools.yunara_report_data     docs/reports/yunara_curves.json
python -m tools.yunara_explorer_data   docs/reports/yunara_explorer.json
python -m tools.kaisa_explorer_data    docs/reports/kaisa_explorer.json
python -m tools.yunara_explorer_data --verify    # DP 점수 == 원본 greedy 인지 검사
python -m tools.kaisa_explorer_data  --verify

# 2) 템플릿 + 데이터 → 배포 파일
python -m tools.build_explorer_report all        # 또는 yunara / kaisa
```
문구·레이아웃만 고칠 때는 2번만 다시 돌리면 된다(데이터 재생성 불필요).

## 챔피언 추가
1. `tools/<champ>_explorer_data.py` 를 유나라/카이사 도구를 미러링해 만든다.
   모듈 상수 `COPY` 에 그 챔피언 문구를 넣으면 템플릿이 그대로 쓴다.
2. `tools/build_explorer_report.py` 의 `REPORTS` 에 한 줄 추가한다.
**템플릿에는 챔피언 이름을 넣지 말 것** — 넣는 순간 공용이 아니게 된다.

## 파일을 남에게 줄 때
- 그대로 첨부하거나, 드라이브·메신저에 올려 링크로 보낸다(유나라 3MB · 카이사 0.5MB).
- 상대 타깃(딜러·브루저·탱커) 스위치는 파일 안에 다 들어 있어 받는 쪽에서 바로 바꿔 볼 수 있다.
