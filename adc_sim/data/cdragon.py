"""Community Dragon(CDragon) 데이터 소스 연동 — 받아오기(fetch) 계층까지만.

이 모듈은 패치별 LoL 정적 데이터를 CDragon에서 *받아오는* 역할만 한다.
받아온 값을 `adc_sim/items.py`·`adc_sim/champion.py` 의 계수로 매핑하는 작업은
아직 하지 않는다(의도적 범위 제한). 매핑/검증은 추후 별도 작업.

데이터 위치 (patch 16.11 기준 직접 확인):
- ``champion-summary.json``      : 챔피언 name<->id 목록. 전 챔피언 포함(유나라 id=804). 깔끔함.
- ``champions/<id>.json``        : 클라이언트 데이터(스킬 이름/설명 + 부분 수치
                                   ``coefficients``/``effectAmounts``).
                                   ⚠️ 크립틱·불완전: 궁(ult) 수치가 0인 경우 잦고,
                                   ``maxLevel`` 필드도 신뢰하기 어렵다. 실제 데미지 공식은
                                   원본 bin 의 spell calculation 에 흩어져 있다.
- ``game/data/characters/<c>/<c>.bin.json`` : 원본 게임 bin. base 스탯과 전체 스킬
                                   계산식이 모두 들어있으나 해시 키 기반이라 매우 난해(파싱은 추후).

참고: 정확한 *base 스탯*(AD/AS/성장치)만 급하면 DDragon
``cdn/<ver>/data/en-US/champion/<C>.json`` 의 ``stats`` 가 더 깔끔하다(교차검증용).

실행: ``python -m adc_sim.data.cdragon``  → 프로젝트 챔피언 연결 점검 리포트.
"""
import json
import urllib.request
from pathlib import Path

from adc_sim.settings import PROJECT_ROOT

CDRAGON_HOST = "https://raw.communitydragon.org"
GAME_DATA_PATH = "plugins/rcp-be-lol-game-data/global/default/v1"
_HEADERS = {"User-Agent": "adc-dps-sim/0.1 (Community Dragon static data fetch)"}

# 이 프로젝트가 다루는 챔피언 (CDragon `name` 표기 기준)
PROJECT_CHAMPIONS = ("Ashe", "Yunara", "Kai'Sa", "Corki", "Jinx")

# 스냅샷 저장 위치 (생성물 → .gitignore 의 patch_data/)
SNAPSHOT_DIR = PROJECT_ROOT / "patch_data"


def _get_json(url, timeout=25):
    """CDragon JSON GET. 반환: 파싱된 dict/list."""
    request = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _data_base(patch="latest"):
    """patch='latest' 또는 '16.11' 같은 버전 → game-data 베이스 URL."""
    return f"{CDRAGON_HOST}/{patch}/{GAME_DATA_PATH}"


def champion_summary(patch="latest"):
    """전체 챔피언 요약 리스트(각 항목에 id/name/alias 등)."""
    return _get_json(f"{_data_base(patch)}/champion-summary.json")


def champion_id_map(patch="latest"):
    """{name: id} 매핑 (id<0 placeholder 제외)."""
    return {c["name"]: c["id"] for c in champion_summary(patch) if c.get("id", -1) >= 0}


def champion_data(champion, patch="latest", id_map=None):
    """클라이언트 챔피언 데이터(스킬/패시브/툴팁/부분 수치).

    champion: 챔피언 name(str) 또는 정수 id.
    id_map: name->id 캐시(여러 챔피언 조회 시 재사용해 요청 절약).
    """
    if isinstance(champion, int):
        champion_id = champion
    else:
        id_map = id_map if id_map is not None else champion_id_map(patch)
        if champion not in id_map:
            raise KeyError(f"Unknown champion name on CDragon: {champion!r}")
        champion_id = id_map[champion]
    return _get_json(f"{_data_base(patch)}/champions/{champion_id}.json")


def champion_bin(alias, patch="latest"):
    """원본 게임 bin(base 스탯·전체 계산식 포함, 단 해시키라 난해).

    alias: 소문자 내부명(예: 'ashe', 'yunara'). champion-summary 의 `alias` 를 소문자화한 값.
    """
    name = alias.lower()
    return _get_json(f"{CDRAGON_HOST}/{patch}/game/data/characters/{name}/{name}.bin.json")


def items(patch="latest"):
    """아이템 목록(id/name/priceTotal 등)."""
    return _get_json(f"{_data_base(patch)}/items.json")


def _spell_has_numbers(spell):
    """스킬 dict 에 0 이 아닌 coefficient/effectAmount 가 하나라도 있으면 True."""
    if any(spell.get("coefficients", {}).values()):
        return True
    return any(
        value
        for amounts in spell.get("effectAmounts", {}).values()
        for value in (amounts or [])
    )


def snapshot(patch="latest", champions=PROJECT_CHAMPIONS, out_dir=None):
    """프로젝트 챔피언 클라이언트 데이터 + 요약 + 아이템을 raw JSON 으로 저장(검토/diff 용).

    반환: 저장한 파일 경로 리스트. 기본 저장 위치: patch_data/<patch>/ (gitignore).
    """
    target_dir = Path(out_dir) if out_dir else (SNAPSHOT_DIR / patch)
    target_dir.mkdir(parents=True, exist_ok=True)

    summary = champion_summary(patch)
    id_map = {c["name"]: c["id"] for c in summary if c.get("id", -1) >= 0}
    written = []

    def _dump(name, payload):
        path = target_dir / f"{name}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(path)

    _dump("champion-summary", summary)
    _dump("items", items(patch))
    for champion in champions:
        if champion in id_map:
            safe_name = champion.replace("'", "")
            _dump(f"champion-{id_map[champion]}-{safe_name}", champion_data(id_map[champion], patch, id_map=id_map))
    return written


def connectivity_report(patch="latest"):
    """프로젝트 챔피언이 CDragon 에서 잡히는지 점검 리포트를 출력한다."""
    print(f"=== Community Dragon 연결 점검 (patch={patch}) ===")
    id_map = champion_id_map(patch)
    print(f"전체 챔피언: {len(id_map)} | 아이템: {len(items(patch))}")
    for champion in PROJECT_CHAMPIONS:
        champion_id = id_map.get(champion)
        if champion_id is None:
            print(f"  [MISS] {champion}: CDragon 요약에 없음")
            continue
        data = champion_data(champion_id, patch, id_map=id_map)
        spells = data.get("spells", [])
        with_numbers = sum(1 for spell in spells if _spell_has_numbers(spell))
        print(f"  [ OK ] {champion:7} id={champion_id:<4} spells={len(spells)} 수치있는스킬={with_numbers}/{len(spells)}")
    print(
        "\n주의: 스킬 coefficients/effectAmounts 는 크립틱·불완전(궁 0 잦음), "
        "base 스탯은 원본 bin 에만 존재."
    )
    print("→ 지금은 '소스 연동'까지만. 계수 → champion.py 매핑은 추후 작업.")


if __name__ == "__main__":
    connectivity_report()
