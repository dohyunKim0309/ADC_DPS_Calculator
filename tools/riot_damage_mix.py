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

# Riot API 는 Cloudflare 뒤에 있고, `Python-urllib/3.x` 기본 User-Agent 는
# "error code: 1010" 으로 차단당한다(키와 무관 — curl 은 통과). Riot 개발자 포털
# 예시가 쓰는 헤더 세트를 그대로 보낸다.
BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Charset": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://developer.riotgames.com",
}


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
        req = Request(url, headers={**BROWSER_HEADERS, "X-Riot-Token": self.key})
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
            if "1010" in raw:
                # 키와 무관한 Cloudflare 차단 — 키 만료 안내를 띄우면 오진으로 이끈다.
                return (f"\n[{tag}] Cloudflare 가 요청을 차단했다 (error code: 1010) — 키 문제 아니다.\n"
                        f"  호출: {url}\n{body}"
                        "  원인: User-Agent 등 클라이언트 헤더가 막힌 것. 같은 키로 curl 은 200 이 나온다.\n"
                        "  확인: BROWSER_HEADERS 가 요청에 실리는지 — 이 스크립트 최신 버전인지 `git pull`.\n")
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


def collect_match(match, timeline=None, champion=None, min_minutes=15,
                  assume_lethality=0.0):
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
            raw, eff = _unmitigate_death_damage(timeline, p["participantId"],
                                                assume_lethality)               # D
            row["death_damage_raw"] = raw
            row["eff_resist"] = eff
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



# ── 경감 역산 (view D) ────────────────────────────────────────────────────
# 엔진 calculate_mitigation 의 역: eff = resist*(1-%pen) - flat_pen (음수 클램프),
# post = raw * 100/(100+eff)  →  raw = post * (100+eff)/100.
# 고정 피해는 경감을 받지 않으므로 그대로 둔다.
# [Hypothesis H-RIOT-PEN-1] 타임라인 championStats 의 %관통 필드가 0~1 분수인지
# 0~100 퍼센트인지 문서에 명시가 없다 — `--dump-stats` 로 실측해 판별한다(아래 _pct).

def _pct(value):
    """%관통 필드 → 0~1 분수. 1 보다 크면 퍼센트 표기로 본다."""
    try:
        v = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return v / 100.0 if v > 1.0 else max(0.0, v)


def _effective_resist(resist, flat_pen, pct_pen):
    return max(0.0, float(resist or 0) * (1.0 - _pct(pct_pen)) - float(flat_pen or 0))


def _frames(timeline):
    return timeline["info"].get("frames", []) or []


def _stats_at(timeline, participant_id, timestamp):
    """해당 시각에 가장 가까운 프레임의 championStats(없으면 None)."""
    best, best_gap = None, None
    for frame in _frames(timeline):
        pf = (frame.get("participantFrames") or {}).get(str(participant_id))
        if not pf:
            continue
        gap = abs(frame.get("timestamp", 0) - timestamp)
        if best_gap is None or gap < best_gap:
            best, best_gap = pf.get("championStats") or {}, gap
    return best


def _unmitigate_death_damage(timeline, participant_id, assume_lethality=0.0):
    """C 와 같은 표본을 가해자 관통까지 반영해 경감 전 값으로 되돌린다."""
    out = {a: 0.0 for a in AXES}
    eff_used = {"armor": [], "mr": []}
    for frame in _frames(timeline):
        for ev in frame.get("events", []):
            if ev.get("type") != "CHAMPION_KILL" or ev.get("victimId") != participant_id:
                continue
            ts = ev.get("timestamp", frame.get("timestamp", 0))
            victim = _stats_at(timeline, participant_id, ts) or {}
            for d in ev.get("victimDamageReceived", []) or []:
                phys = d.get("physicalDamage", 0) or 0
                magic = d.get("magicDamage", 0) or 0
                out["true"] += d.get("trueDamage", 0) or 0
                # 가해자가 챔피언이면 그 시점 관통을, 미니언·포탑·몬스터면 관통 0.
                src = d.get("participantId") or 0
                atk = _stats_at(timeline, src, ts) if src else None
                atk = atk or {}
                if phys:
                    # armorPen 은 실측상 항상 0 — 리썰리티가 안 실린다. 챔피언 출처면
                    # 가정값으로 보정할 수 있게 한다(고정 관통으로 취급).
                    flat = atk.get("armorPen") or (assume_lethality if src else 0.0)
                    eff = _effective_resist(victim.get("armor"), flat,
                                            atk.get("armorPenPercent"))
                    out["physical"] += phys * (100.0 + eff) / 100.0
                    eff_used["armor"].append(eff)
                if magic:
                    eff = _effective_resist(victim.get("magicResist"),
                                            atk.get("magicPen"), atk.get("magicPenPercent"))
                    out["magic"] += magic * (100.0 + eff) / 100.0
                    eff_used["mr"].append(eff)
    return out, eff_used


def _item_names():
    """DDragon 아이템 id→이름 (한 번 받아 캐시; 실패하면 빈 표 → id 그대로 출력)."""
    cached = CACHE / "_items.json"
    if cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))
    try:
        def fetch(url):
            req = Request(url, headers=BROWSER_HEADERS)
            with urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        ver = fetch("https://ddragon.leagueoflegends.com/api/versions.json")[0]
        data = fetch(f"https://ddragon.leagueoflegends.com/cdn/{ver}/data/en_US/item.json")
        names = {k: v["name"] for k, v in data["data"].items()}
    except Exception as err:
        print(f"  (아이템 이름표 없음: {err} — id 로 출력)", file=sys.stderr)
        return {}
    CACHE.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(names), encoding="utf-8")
    return names


def _items_held(timeline, participant_id, until_ts):
    """해당 시각까지의 ITEM_PURCHASED/DESTROYED/UNDO 를 따라간 보유 아이템 id 목록."""
    held = []
    for frame in _frames(timeline):
        for ev in frame.get("events", []):
            if ev.get("timestamp", 0) > until_ts:
                return held
            if ev.get("participantId") != participant_id:
                continue
            kind, item = ev.get("type"), ev.get("itemId")
            if kind == "ITEM_PURCHASED":
                held.append(item)
            elif kind in ("ITEM_DESTROYED", "ITEM_SOLD") and item in held:
                held.remove(item)
            elif kind == "ITEM_UNDO":
                before = ev.get("beforeId")
                if before in held:
                    held.remove(before)
    return held


PEN_KEYS = ("armor", "magicResist", "armorPen", "armorPenPercent",
            "bonusArmorPenPercent", "magicPen", "magicPenPercent",
            "bonusMagicPenPercent")


def dump_stats(cache_files, limit=3, correlate=("armorPenPercent", "magicPen",
                                                "magicPenPercent")):
    """championStats 관통·저항 필드 실측 + 0 아닌 관통값이 어떤 아이템과 함께 나오는지.

    %표기 판별(값>1 이면 퍼센트)과, 리썰리티가 %필드에 잘못 실렸는지 판별이 목적이다.
    """
    seen = {k: [] for k in PEN_KEYS}
    witness = {k: {} for k in correlate}      # 값 → {(챔프, 아이템들): 횟수}
    shown = 0
    for f in cache_files:
        tl = json.loads(f.read_text(encoding="utf-8"))
        match_file = CACHE / f.name.replace("_tl.json", ".json")
        champs = {}
        if match_file.exists():
            m = json.loads(match_file.read_text(encoding="utf-8"))
            champs = {p["participantId"]: p.get("championName")
                      for p in m["info"]["participants"]}
        for frame in _frames(tl):
            for pid, pf in (frame.get("participantFrames") or {}).items():
                cs = pf.get("championStats") or {}
                for k in PEN_KEYS:
                    if k in cs:
                        seen[k].append(cs[k])
                for k in correlate:
                    val = cs.get(k) or 0
                    if not val:
                        continue
                    items = _items_held(tl, int(pid), frame.get("timestamp", 0))
                    key = (champs.get(int(pid), f"pid{pid}"), tuple(sorted(items)))
                    witness[k].setdefault(val, {}).setdefault(key, 0)
                    witness[k][val][key] += 1
        shown += 1
        if shown >= limit:
            break
    if not shown:
        print(f"타임라인 캐시가 없다 — `--timeline` 으로 수집해야 한다. ({CACHE})")
        return
    print(f"\nchampionStats 실측 ({shown} 판 타임라인)")
    for k in PEN_KEYS:
        vals = seen[k]
        if not vals:
            print(f"  {k:24s} (필드 없음)")
            continue
        nz = [v for v in vals if v]
        print(f"  {k:24s} n={len(vals):6d}  0 아닌 값 {len(nz):6d}  "
              f"min={min(vals)}  max={max(vals)}  값 종류={sorted(set(nz))[:12]}")
    names = _item_names()
    for k in correlate:
        if not witness[k]:
            continue
        print(f"\n  {k} = 0 아닌 프레임의 보유 아이템 (값별 최빈 1건)")
        for val in sorted(witness[k]):
            (champ, items), cnt = max(witness[k][val].items(), key=lambda kv: kv[1])
            shown_items = ", ".join(names.get(str(i), str(i)) for i in items) or "(없음)"
            print(f"    {k}={val:<4g} {champ:12s} n={cnt:<4d} {shown_items[:150]}")
    print("\n  → %필드 값이 리썰리티 수치(10/18 등)와 아이템이 일치하면 표기가 섞인 것이다.")
    print("     방관 %아이템(도미닉 35% 등)과 일치하면 진짜 퍼센트다.\n")


def summarize(rows):
    """관점별 평균 비중 — 판마다 비중을 내고 평균(대형 판이 표본을 지배하지 않게)."""
    out = {}
    for view, key in (("A 받은 피해 전체(미니언·포탑 포함)", "taken_all"),
                      ("B 적 팀이 챔피언에 가한 피해", "enemy_dealt_champ"),
                      ("C 내가 죽을 때 맞은 피해", "death_damage"),
                      ("D C를 경감 역산(관통 반영)", "death_damage_raw")):
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
    arm = [v for r in rows for v in r.get("eff_resist", {}).get("armor", [])]
    mr = [v for r in rows for v in r.get("eff_resist", {}).get("mr", [])]
    if arm or mr:
        print(f"  역산에 쓴 평균 유효저항: 방어력 {sum(arm)/len(arm):.1f} (n={len(arm)}) · "
              f"마저 {sum(mr)/len(mr):.1f} (n={len(mr)})" if arm and mr else "")
    print("\n  → 리포트 DMG_MIX 프리셋에 넣을 값은 위 '고정=1 기준' 비율이다.")
    print("  ⚠️ A·B·C 는 경감 후 수치다 — 내 방어 아이템이 비중을 이미 왜곡한다.")
    print("     D 는 그 왜곡을 되돌린 추정이다(가해자 관통 반영). 남는 오차:")
    print("       · 방어력 감소(검은도끼 등)는 프레임 armor 에 이미 반영됐다고 가정")
    print("       · armorPen(고정 방관) 필드가 실측상 항상 0 — 리썰리티가 안 잡힌다.")
    print("         → D 의 물리는 과대 추정이다. `--lethality 18` 등으로 민감도를 봐라.")
    print("       · bonusArmorPenPercent(추가방어력 한정)는 미반영")
    print("       · 프레임은 분 단위 — 교전 중 스탯 변화는 최근접 프레임으로 근사")
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
    ap.add_argument("--lethality", type=float, default=0.0,
                    help="D 역산에서 가정할 적 고정 방어구 관통 "
                         "(armorPen 필드가 실측상 항상 0 — 기본 0 은 물리 과대 추정)")
    ap.add_argument("--dump-stats", action="store_true",
                    help="championStats 관통·저항 필드 실측(%표기 판별)")
    args = ap.parse_args()

    if args.dump_stats:
        dump_stats(sorted(CACHE.glob("*_tl.json")) if CACHE.exists() else [])
        return

    if args.report:
        rows = []
        for f in sorted(CACHE.glob("*.json")):
            if f.name.endswith("_tl.json"):
                continue
            match = json.loads(f.read_text(encoding="utf-8"))
            tl = CACHE / f"{match['metadata']['matchId']}_tl.json"
            rows += collect_match(match,
                                  json.loads(tl.read_text(encoding="utf-8")) if tl.exists() else None,
                                  champion=args.champion,
                                  assume_lethality=args.lethality)
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
            rows += collect_match(match, tl, champion=args.champion,
                                  assume_lethality=args.lethality)
            if len(seen) % 25 == 0:
                print(f"  {len(seen)}/{args.count} 판 · 원딜 표본 {len(rows)}")
    print(f"[3/3] API 호출 {api.calls}회 · 캐시 {CACHE}")
    print_summary(rows)


if __name__ == "__main__":
    try:
        main()
    except RiotAuthError as err:
        raise SystemExit(str(err))
