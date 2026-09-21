# -*- coding: utf-8 -*-
"""탐색기 리포트 빌드 — 공용 템플릿 + 챔피언 데이터 → 배포용 단일 HTML.

실행: `python -m tools.build_explorer_report [yunara|kaisa|all] [출력경로]`  (repo 루트)

왜 나눠 두는가: 탐색기 데이터가 3MB 다. 템플릿에 박아 둔 채로 커밋하면 CSS 한 줄만
고쳐도 diff 가 수백만 자로 뜨고 리뷰가 불가능해진다. 그래서 **편집 대상(템플릿)과 생성
데이터(JSON)를 갈라 두고**, 배포 직전에만 합친다. 빌드 산출물은 .gitignore 대상이다.

템플릿(`docs/reports/explorer.template.html`)은 **챔피언 중립**이다. 챔피언마다 다른 것은
전부 탐색기 JSON 의 `copy` 블록에서 온다(제목·리드·시나리오 라벨·측정 방식·캐비엇).
곡선 JSON(`*_curves.json`)은 **선택 사항** — 없으면 완성 트리 비교 섹션(파워 곡선·5코어
막대·수치 표)이 숨고 탐색기·규칙·KPI 만 나온다.

새 챔피언을 붙이려면:
  1) `tools/<champ>_explorer_data.py` 로 노드 JSON 을 만든다(유나라/카이사 도구 미러).
     그 안 `build()` 의 `copy` 블록에 챔피언별 문구를 넣는다.
  2) 아래 REPORTS 에 한 줄 추가한다. 템플릿은 건드릴 일이 없다.

데이터를 다시 뽑으려면 `python -m tools.yunara_report_data`(곡선),
`python -m tools.yunara_explorer_data` / `python -m tools.kaisa_explorer_data`(탐색기).

배포: 산출된 HTML 을 Artifact 도구로 기존 URL 에 publish 한다(새로 만들지 말 것).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "docs" / "reports"
TEMPLATE = REPORTS_DIR / "explorer.template.html"

# 챔피언 → (탐색기 JSON, 곡선 JSON 또는 None, 출력 파일)
REPORTS = {
    "yunara": ("yunara_explorer.json", "yunara_curves.json", "yunara_report.html"),
    "kaisa": ("kaisa_explorer.json", None, "kaisa_report.html"),
}

CURVES_PLACEHOLDER = "__CURVES_JSON__"
EXPLORER_PLACEHOLDER = "__EXPLORER_JSON__"
TITLE_PLACEHOLDER = "__TITLE__"

# 템플릿은 Artifact publish 기준으로 쓴 **조각**이라 doctype·charset 이 없다
# (Artifact 호스트가 감싸 준다). 파일로 받아 file:// 로 열면 브라우저가 인코딩을 지역
# 기본값으로 찍어 한글이 깨지고 쿼크 모드로 떨어진다 → 빌드가 문서 껍데기를 씌운다.
DOC_HEAD = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
"""
DOC_TAIL = "\n</body>\n</html>\n"
BODY_ANCHOR = '<div class="wrap">'      # 여기부터가 본문 — 앞은 head 로 들어간다


def _wrap_document(html):
    """조각이면 완전한 HTML 문서로 감싼다(이미 doctype 이 있으면 그대로).

    브라우저가 알아서 head/body 를 갈라 주긴 하지만, 나중에 본문 앞에 <script> 나
    주석이 붙으면 소리 없이 head 로 빨려 들어간다. 경계를 명시해 둔다.
    """
    if html.lstrip()[:15].lower().startswith("<!doctype"):
        return html
    if BODY_ANCHOR in html:
        head, body = html.split(BODY_ANCHOR, 1)
        html = head + "</head>\n<body>\n" + BODY_ANCHOR + body
    return DOC_HEAD + html + DOC_TAIL


def _compact(path):
    return json.dumps(json.loads(path.read_text(encoding="utf-8")),
                      ensure_ascii=False, separators=(",", ":"))


def build(champion, out_path=None):
    """챔피언 하나의 리포트를 만든다 — 반환은 산출 경로."""
    if champion not in REPORTS:
        raise SystemExit(f"모르는 챔피언: {champion} (가능: {', '.join(REPORTS)})")
    explorer_name, curves_name, default_out = REPORTS[champion]
    template = TEMPLATE.read_text(encoding="utf-8")
    for marker in (CURVES_PLACEHOLDER, EXPLORER_PLACEHOLDER, TITLE_PLACEHOLDER):
        if marker not in template:
            raise SystemExit(f"템플릿에 {marker} 자리가 없다: {TEMPLATE}")

    explorer_path = REPORTS_DIR / explorer_name
    explorer = json.loads(explorer_path.read_text(encoding="utf-8"))
    title = (explorer.get("copy") or {}).get("title") or f"{champion} 코어 결정 탐색기"

    curves = _compact(REPORTS_DIR / curves_name) if curves_name else "null"
    html = template.replace(CURVES_PLACEHOLDER, curves)
    html = html.replace(EXPLORER_PLACEHOLDER, _compact(explorer_path))
    html = html.replace(TITLE_PLACEHOLDER, title)
    html = _wrap_document(html)

    out = Path(out_path) if out_path else REPORTS_DIR / default_out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    who = args[0] if args else "all"
    dest = args[1] if len(args) > 1 else None
    targets = list(REPORTS) if who == "all" else [who]
    if dest and len(targets) > 1:
        raise SystemExit("출력 경로를 지정하려면 챔피언 하나만 빌드할 것")
    for champ in targets:
        built = build(champ, dest)
        print(f"built {champ} -> {built}  ({built.stat().st_size / 1024:.0f}KB)")
