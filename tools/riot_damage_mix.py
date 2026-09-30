# -*- coding: utf-8 -*-
"""원딜이 받는 피해의 물리 : 마법 : 고정 비중을 매치 데이터에서 뽑는다.

목적: 생존성(EHP) 세 축을 섞는 가중치 `DMG_MIX` 의 근거. 지금 리포트는 균등 1:1:1 이
기본이고 나머지 프리셋은 임시치다 — 이 스크립트 출력으로 갈아끼운다.

실행 (라이엇 API 키 필요, 로컬에서):
    export RIOT_API_KEY=RGAPI-xxxx
    python -m tools.riot_damage_mix --region kr --tier CHALLENGER --count 300
    python -m tools.riot_damage_mix --region kr --tier EMERALD --division I --count 500
    python -m tools.riot_damage_mix --report            # 모아둔 캐시로 집계만 다시

⚠️ 세 관점을 **동시에** 뽑는다. 하나만 보면 틀린 결론이 나오기 때문이다.

  A. 내가 받은 전체 피해 (`*DamageTaken`)
     미니언·포탑·몬스터 포함. 라인전 체력 소모까지 들어간 "한 판 전체" 그림.
  B. 적 팀이 챔피언에게 가한 피해 (`*DamageDealtToChampions` 합)
     챔피언 출처만. 단 내가 아니라 **우리 팀 전체**가 받은 몫이라 포지션 편향이 있다.
  C. 내가 죽을 때 실제로 맞은 피해 (타임라인 `victimDamageReceived`)
     챔피언 출처 + 나 개인. 대신 **죽은 순간의 표본만** 잡히는 치명 편향이 있다.

⚠️ A·B·C 전부 **경감 후(post-mitigation)** 수치다. 내가 방어력을 올리면 물리 비중이
   낮아 보이는 역인과가 섞인다. 그래서 이 값은 "기본 프리셋·대조용"이고, 편향 없는
   근거는 챔피언별 피해 타입 프로파일(2단계, `champion_damage_profile`)이다.

수집 규약
  · 큐 420(솔로 랭크) 기본. `--queue` 로 변경.
  · 대상 참가자 = `teamPosition == "BOTTOM"` (원딜). `--champion` 으로 특정 챔프만.
  · 매치 JSON 은 `scratch/riot_cache/` 에 캐시 — 재실행은 API 를 다시 안 친다.
  · 개발용 키 레이트리밋(20 req/s · 100 req/2min)에 맞춰 스스로 쉰다.
"""
import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

CACHE = Path(__file__).resolve().parent.parent / "scratch" / "riot_cache"
PLATFORM = {"kr": "kr", "na": "na1", "euw": "euw1", "eun": "eun1", "jp": "jp1"}
ROUTE = {"kr": "asia", "na": "americas", "euw": "europe", "eun": "europe", "jp": "asia"}
AXES = ("physical", "magic", "true")


class RiotAuthError(RuntimeError):
    """401/403 — 재시도로 안 풀린다. 진단 메시지를 그대로 들고 다닌다."""


class Riot:
    """레이트리밋을 스스로 지키는 얇은 API 래퍼(캐시 우선)."""

    def __init__(self, key, region, sleep=1.25):
        self.key = key
        self.region = region
        self.sleep = sleep          # 2분 100회 = 1.2초/회 — 개발 키 기준 보수적으로
        self.last = 0.0
        self.calls = 0

    def _get(self, host, path):
        url = f"https://{host}/{path}"
        wait = self.sleep - (time.time() - self.last)
        if wait > 0:
            time.sleep(wait)
        req = Request(url, headers={"X-Riot-Token": self.key})
        for attempt in range(5):
            try:
                with urlopen(req, timeout=20) as resp:
                    self.last = time.time()
                    self.calls += 1
                    return json.loads(resp.read().decode("utf-8"))
            except HTTPError as err:
                if err.code == 429:                      # 레이트리밋 — 헤더가 시키는 만큼 쉰다
                    retry = int(err.headers.get("Retry-After", "10"))
                    print(f"  [429] {retry}s 대기", file=sys.stderr)
                    time.sleep(retry + 1)
                    continue
                if err.code in (500, 502, 503, 504):
                    time.sleep(2 ** attempt)
                    continue
                if err.code in (401, 403):
                    raise RiotAuthError(
                        _auth_error_message(url, err.code, self.key, err)) from None
                raise
        raise RuntimeError(f"요청 실패: {url}")

    def league_entries(self, tier, division, page=1):
        host = f"{PLATFORM[self.region]}.api.riotgames.com"
        if tier in ("CHALLENGER", "GRANDMASTER", "MASTER"):
            path = f"lol/league/v4/{tier.lower()}leagues/by-queue/RANKED_SOLO_5x5"
            return self._get(host, path)["entries"]
        path = (f"lol/league/v4/entries/RANKED_SOLO_5x5/{tier}/{division}?page={page}")
        return self._get(host, path)

    def puuid_by_summoner(self, summoner_id):
        host = f"{PLATFORM[self.region]}.api.riotgames.com"
        return self._get(host, f"lol/summoner/v4/summoners/{summoner_id}")["puuid"]

    def match_ids(self, puuid, queue, count=20):
        host = f"{ROUTE[self.region]}.api.riotgames.com"
        return self._get(host, f"lol/match/v5/matches/by-puuid/{puuid}/ids"
                               f"?queue={queue}&count={count}")

    def match(self, match_id):
        cached = CACHE / f"{match_id}.json"
        if cached.exists():
            return json.loads(cached.read_text(encoding="utf-8"))
        host = f"{ROUTE[self.region]}.api.riotgames.com"
        data = self._get(host, f"lol/match/v5/matches/{match_id}")
        CACHE.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(data), encoding="utf-8")
        return data

    def timeline(self, match_id):
        cached = CACHE / f"{match_id}_tl.json"
        if cached.exists():
            return json.loads(cached.read_text(encoding="utf-8"))
        host = f"{ROUTE[self.region]}.api.riotgames.com"
        data = self._get(host, f"lol/match/v5/matches/{match_id}/timeline")
        CACHE.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(data), encoding="utf-8")
        return data



def _mask(key):
    """키를 로그에 남겨도 되는 형태로 — 앞 9자 + 길이만."""
    if not key:
        return "(빈 값)"
    return f"{key[:9]}…({len(key)}자)"


def _auth_error_message(url, code, key, err=None):
    """401/403 은 재시도해도 안 풀린다 — 원인과 확인 방법을 바로 알려준다."""
    tag = "401 Unauthorized" if code == 401 else "403 Forbidden"
    body = ""
    if err is not None:
        try:
            raw = err.read().decode("utf-8", "replace").strip()
        except Exception:
            raw = ""
        if raw:
            body = f"  응답 본문: {raw[:300]}\n"
    return (
        f"\n[{tag}] Riot API 가 키를 거부했다.\n"
        f"  호출: {url}\n"
        f"  RIOT_API_KEY: {_mask(key)}\n"
        + body +
        "  가장 흔한 원인 순서:\n"
        "   1) 개발 키 만료 — 발급 후 24시간이면 죽는다. "
        "https://developer.riotgames.com 에서 REGENERATE API KEY 후 다시 export.\n"
        "   2) 셸에 export 가 안 됐거나 옛 값이 남아 있음 — "
        "`echo $RIOT_API_KEY` 로 위 마스크와 같은지 확인.\n"
        "   3) 키 종류가 이 엔드포인트/리전에 권한 없음(개발 키는 league-v4·match-v5 전부 허용).\n"
        "  한 줄 확인:\n"
        f"   curl -s -o /dev/null -w '%{{http_code}}\\n' -H \"X-Riot-Token: $RIOT_API_KEY\" '{url}'\n"
    )


def _share(counts):
    """{물리, 마법, 고정} 절대값 → 비중(합 1). 합이 0이면 None."""
    total = sum(counts[a] for a in AXES)
    if total <= 0:
        return None
    return {a: counts[a] / total for a in AXES}


def collect_match(match, timeline=None, champion=None, min_minutes=15):
    """매치 하나에서 A/B/C 세 관점의 (물리, 마법, 고정) 절대값을 뽑는다."""
    info = match["info"]
    if info.get("gameDuration", 0) < min_minutes * 60:
        return []                                   # 리메이크·초반 종료 제외
    rows = []
    for p in info["participants"]:
        if p.get("teamPosition") != "BOTTOM":
            continue
        if champion and p.get("championName") != champion:
            continue
        taken = {"physical": p.get("physicalDamageTaken", 0),
                 "magic": p.get("magicDamageTaken", 0),
                 "true": p.get("trueDamageTaken", 0)}
        # B: 상대 팀이 챔피언에게 가한 피해(챔피언 출처만, 우리 팀 전체가 받은 몫)
        dealt = {a: 0 for a in AXES}
        for q in info["participants"]:
            if q["teamId"] == p["teamId"]:
                continue
            dealt["physical"] += q.get("physicalDamageDealtToChampions", 0)
            dealt["magic"] += q.get("magicDamageDealtToChampions", 0)
            dealt["true"] += q.get("trueDamageDealtToChampions", 0)
        row = {
            "match": match["metadata"]["matchId"],
            "champion": p.get("championName"),
            "minutes": round(info["gameDuration"] / 60.0, 1),
            "win": bool(p.get("win")),
            "taken_all": taken,                     # A — 미니언·포탑·몬스터 포함
            "enemy_dealt_champ": dealt,             # B — 챔피언 출처
            "deaths": p.get("deaths", 0),
            "total_taken": p.get("totalDamageTaken", 0),
        }
        if timeline is not None:
            row["death_damage"] = _death_damage(timeline, p["participantId"])   # C
        rows.append(row)
    return rows


def _death_damage(timeline, participant_id):
    """C — 내가 죽은 순간들에 실제로 맞은 피해 타입 합(챔피언 출처만)."""
    out = {a: 0.0 for a in AXES}
    for frame in timeline["info"].get("frames", []):
        for ev in frame.get("events", []):
            if ev.get("type") != "CHAMPION_KILL" or ev.get("victimId") != participant_id:
                continue
            for d in ev.get("victimDamageReceived", []) or []:
                if d.get("type") != "OTHER" and d.get("spellName") is not None:
                    pass                            # 출처 무관하게 타입만 본다
                out["physical"] += d.get("physicalDamage", 0)
                out["magic"] += d.get("magicDamage", 0)
                out["true"] += d.get("trueDamage", 0)
    return out


def summarize(rows):
    """관점별 평균 비중 — 판마다 비중을 내고 평균(대형 판이 표본을 지배하지 않게)."""
    out = {}
    for view, key in (("A 받은 피해 전체(미니언·포탑 포함)", "taken_all"),
                      ("B 적 팀이 챔피언에 가한 피해", "enemy_dealt_champ"),
                      ("C 내가 죽을 때 맞은 피해", "death_damage")):
        shares = [_share(r[key]) for r in rows if key in r]
        shares = [s for s in shares if s]
        if not shares:
            continue
        out[view] = {
            "n": len(shares),
            **{a: sum(s[a] for s in shares) / len(shares) for a in AXES},
        }
    return out


def print_summary(rows):
    if not rows:
        print(f"\n표본 0 — 집계할 매치가 없다. 캐시: {CACHE} "
              f"({len(list(CACHE.glob('*.json'))) if CACHE.exists() else 0} 파일)\n"
              "  수집을 먼저 돌려야 한다(--report 없이). "
              "--champion 필터를 걸었다면 철자도 확인.")
        return
    print(f"\n표본 {len(rows)} 판 · 평균 {sum(r['minutes'] for r in rows)/max(1,len(rows)):.1f}분")
    for view, agg in summarize(rows).items():
        ratio = " : ".join(f"{agg[a]*100:.1f}" for a in AXES)
        rel = [agg[a] / agg["true"] if agg["true"] else 0 for a in AXES]
        print(f"  {view:34s} n={agg['n']:4d}  물리:마법:고정 = {ratio}"
              f"   (고정=1 기준 {rel[0]:.1f} : {rel[1]:.1f} : 1)")
    print("\n  → 리포트 DMG_MIX 프리셋에 넣을 값은 위 '고정=1 기준' 비율이다.")
    print("  ⚠️ 셋 다 경감 후 수치다 — 내 방어 아이템이 비중을 이미 왜곡한다.")
    print("     편향 없는 근거는 챔피언별 피해 타입 프로파일(2단계)이다.\n")


def main():
    ap = argparse.ArgumentParser(description="원딜 피해 타입 비중 수집")
    ap.add_argument("--region", default="kr", choices=sorted(PLATFORM))
    ap.add_argument("--tier", default="CHALLENGER")
    ap.add_argument("--division", default="I")
    ap.add_argument("--queue", type=int, default=420)
    ap.add_argument("--count", type=int, default=200, help="목표 매치 수")
    ap.add_argument("--per-player", type=int, default=5, help="플레이어당 매치 수")
    ap.add_argument("--champion", default=None, help="특정 챔프만(예: Kaisa)")
    ap.add_argument("--timeline", action="store_true", help="C 관점(죽을 때 피해)도 수집 — 호출 2배")
    ap.add_argument("--report", action="store_true", help="캐시만 집계")
    args = ap.parse_args()

    if args.report:
        rows = []
        for f in sorted(CACHE.glob("*.json")):
            if f.name.endswith("_tl.json"):
                continue
            match = json.loads(f.read_text(encoding="utf-8"))
            tl = CACHE / f"{match['metadata']['matchId']}_tl.json"
            rows += collect_match(match,
                                  json.loads(tl.read_text(encoding="utf-8")) if tl.exists() else None,
                                  champion=args.champion)
        print_summary(rows)
        return

    key = (os.environ.get("RIOT_API_KEY") or "").strip()
    if not key:
        raise SystemExit("RIOT_API_KEY 환경변수가 없다 — https://developer.riotgames.com 에서 발급")
    if not key.startswith("RGAPI-"):
        print(f"  ⚠️ RIOT_API_KEY 가 'RGAPI-' 로 시작하지 않는다({_mask(key)}) — "
              "값이 잘못 들어갔을 수 있다.", file=sys.stderr)

    api = Riot(key, args.region)
    # 수집 루프 전에 값싼 호출로 키를 먼저 검증 — 403 을 300판 돌기 직전이 아니라 지금 잡는다.
    api._get(f"{PLATFORM[args.region]}.api.riotgames.com", "lol/status/v4/platform-data")
    print(f"[1/3] {args.region} {args.tier} {args.division} 플레이어 수집")
    entries = api.league_entries(args.tier, args.division)
    print(f"      {len(entries)} 명")

    seen, rows = set(), []
    for entry in entries:
        if len(seen) >= args.count:
            break
        try:
            puuid = entry.get("puuid") or api.puuid_by_summoner(entry["summonerId"])
            ids = api.match_ids(puuid, args.queue, args.per_player)
        except RiotAuthError:                        # 키 거부는 건너뛸 게 아니라 중단
            raise
        except Exception as err:                     # 탈퇴·비공개 계정 등은 건너뛴다
            print(f"  건너뜀: {err}", file=sys.stderr)
            continue
        for match_id in ids:
            if match_id in seen or len(seen) >= args.count:
                continue
            seen.add(match_id)
            match = api.match(match_id)
            tl = api.timeline(match_id) if args.timeline else None
            rows += collect_match(match, tl, champion=args.champion)
            if len(seen) % 25 == 0:
                print(f"  {len(seen)}/{args.count} 판 · 원딜 표본 {len(rows)}")
    print(f"[3/3] API 호출 {api.calls}회 · 캐시 {CACHE}")
    print_summary(rows)


if __name__ == "__main__":
    try:
        main()
    except RiotAuthError as err:
        raise SystemExit(str(err))
