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
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    built = build(out_path=dest)
    print(f"built -> {built}  ({built.stat().st_size / 1024:.0f}KB)")
