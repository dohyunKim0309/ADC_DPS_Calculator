# -*- coding: utf-8 -*-
"""유나라 리포트 HTML 빌드 — 템플릿 + 곡선 JSON → 배포용 단일 HTML.

실행: `python -m tools.build_yunara_report [출력경로]`  (repo 루트에서, 1초)

왜 나눠 두는가: 곡선 데이터가 150KB 넘는다. 템플릿에 박아 둔 채로 커밋하면 CSS 한 줄만
고쳐도 diff 가 십수만 자로 뜨고 리뷰가 불가능해진다. 그래서 **편집 대상(템플릿)과 생성
데이터(JSON)를 갈라 두고**, 배포 직전에만 합친다. 빌드 산출물은 .gitignore 대상이다.

데이터를 다시 뽑으려면 `python -m tools.yunara_report_data`(곡선) 와
`python -m tools.yunara_explorer_data`(탐색기 노드 표) 를 각각 돌린다.

배포: 산출된 HTML 을 Artifact 도구로 기존 URL 에 publish 한다(새로 만들지 말 것).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "docs" / "reports" / "yunara_report.template.html"
DATA = ROOT / "docs" / "reports" / "yunara_curves.json"
EXPLORER = ROOT / "docs" / "reports" / "yunara_explorer.json"
DEFAULT_OUT = ROOT / "docs" / "reports" / "yunara_report.html"
PLACEHOLDER = "__CURVES_JSON__"
EXPLORER_PLACEHOLDER = "__EXPLORER_JSON__"

# 템플릿은 Artifact 로 publish 할 때를 기준으로 쓴 **조각**이라 doctype·charset 이 없다
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


def build(template_path=TEMPLATE, data_path=DATA, out_path=DEFAULT_OUT,
          explorer_path=EXPLORER):
    """템플릿의 데이터 자리 두 곳에 JSON 을 압축 형태로 주입한다.

    `__CURVES_JSON__`   — 접이식 섹션(곡선·막대·표)이 쓰는 완성 트리 곡선
    `__EXPLORER_JSON__` — 탐색기가 쓰는 노드별 후보 표
    """
    template = template_path.read_text(encoding="utf-8")
    for marker in (PLACEHOLDER, EXPLORER_PLACEHOLDER):
        if marker not in template:
            raise SystemExit(f"템플릿에 {marker} 자리가 없다: {template_path}")
    html = template.replace(PLACEHOLDER, _compact(data_path))
    html = html.replace(EXPLORER_PLACEHOLDER, _compact(explorer_path))
    html = _wrap_document(html)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    built = build(out_path=dest)
    print(f"built -> {built}  ({built.stat().st_size / 1024:.0f}KB)")
