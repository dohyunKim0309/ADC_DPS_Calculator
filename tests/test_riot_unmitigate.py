"""경감 역산(view D) 산술 검증 — 합성 매치/타임라인으로 왕복을 맞춘다.

엔진 규약과 같은 식을 쓴다: eff = resist*(1-%pen) - flat_pen (음수 클램프),
post = raw * 100/(100+eff). D 는 이 식을 뒤집어 raw 를 복원한다.
"""
import unittest

from tools.riot_damage_mix import (_effective_resist, _pct, _share, collect_match,
                                   _unmitigate_death_damage)

VICTIM, ATTACKER = 1, 6


def _match():
    def part(pid, team, pos):
        return {"participantId": pid, "teamId": team, "teamPosition": pos,
                "championName": "Kaisa" if pid == VICTIM else "Darius",
                "physicalDamageTaken": 1000, "magicDamageTaken": 500,
                "trueDamageTaken": 100, "totalDamageTaken": 1600,
                "physicalDamageDealtToChampions": 0,
                "magicDamageDealtToChampions": 0,
                "trueDamageDealtToChampions": 0, "deaths": 1, "win": False}
    return {"metadata": {"matchId": "KR_TEST"},
            "info": {"gameDuration": 1800,
                     "participants": [part(VICTIM, 100, "BOTTOM"),
                                      part(ATTACKER, 200, "TOP")]}}


def _timeline(pct_pen, flat_pen):
    stats = {str(VICTIM): {"championStats": {"armor": 60, "magicResist": 40}},
             str(ATTACKER): {"championStats": {"armor": 100, "magicResist": 60,
                                               "armorPen": flat_pen,
                                               "armorPenPercent": pct_pen,
                                               "magicPen": 0, "magicPenPercent": 0}}}
    kill = {"type": "CHAMPION_KILL", "victimId": VICTIM, "timestamp": 600_000,
            "victimDamageReceived": [{"participantId": ATTACKER, "physicalDamage": 1000,
                                      "magicDamage": 500, "trueDamage": 100}]}
    return {"info": {"frames": [{"timestamp": 600_000, "participantFrames": stats,
                                 "events": [kill]}]}}


class TestUnmitigate(unittest.TestCase):
    def test_pct_field_both_notations(self):
        self.assertAlmostEqual(_pct(0.35), 0.35)     # 분수 표기
        self.assertAlmostEqual(_pct(35), 0.35)       # 퍼센트 표기
        self.assertEqual(_pct(None), 0.0)

    def test_effective_resist_clamped_at_zero(self):
        self.assertAlmostEqual(_effective_resist(60, 18, 0.35), 21.0)
        self.assertEqual(_effective_resist(20, 40, 0.0), 0.0)

    def test_roundtrip_restores_pre_mitigation_damage(self):
        raw, eff = _unmitigate_death_damage(_timeline(0.35, 18), VICTIM)
        # eff 방어력 21 → 1000 × 1.21 ; eff 마저 40 → 500 × 1.40 ; 고정은 그대로
        self.assertAlmostEqual(raw["physical"], 1210.0)
        self.assertAlmostEqual(raw["magic"], 700.0)
        self.assertAlmostEqual(raw["true"], 100.0)
        self.assertAlmostEqual(eff["armor"][0], 21.0)
        self.assertAlmostEqual(eff["mr"][0], 40.0)

    def test_percent_notation_gives_same_answer(self):
        frac, _ = _unmitigate_death_damage(_timeline(0.35, 18), VICTIM)
        pct, _ = _unmitigate_death_damage(_timeline(35, 18), VICTIM)
        self.assertAlmostEqual(frac["physical"], pct["physical"])

    def test_minion_source_gets_no_penetration(self):
        tl = _timeline(0.35, 18)
        tl["info"]["frames"][0]["events"][0]["victimDamageReceived"][0]["participantId"] = 0
        raw, _ = _unmitigate_death_damage(tl, VICTIM)
        self.assertAlmostEqual(raw["physical"], 1000 * 1.60)   # 방어력 60 전부 적용
        self.assertAlmostEqual(raw["magic"], 500 * 1.40)

    def test_collect_match_exposes_view_d(self):
        rows = collect_match(_match(), _timeline(0.35, 18))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        post, pre = _share(row["death_damage"]), _share(row["death_damage_raw"])
        self.assertAlmostEqual(post["physical"], 1000 / 1600)
        self.assertAlmostEqual(sum(pre.values()), 1.0)
        # 역산은 유효저항이 큰 쪽 비중을 키운다. 이 케이스는 가해자가 방관만 있어
        # eff 방어력 21 < eff 마저 40 → 마법이 오르고 물리·고정이 내려간다.
        self.assertGreater(pre["magic"], post["magic"])
        self.assertLess(pre["physical"], post["physical"])
        self.assertLess(pre["true"], post["true"])

    def test_share_moves_to_physical_when_armor_is_the_bigger_wall(self):
        """저항이 큰 쪽이 물리면 물리 비중이 오른다 — 방향성이 저항에서 나옴을 고정."""
        rows = collect_match(_match(), _timeline(0.0, 0))   # 관통 0 → eff 방60 > 마40
        post, pre = _share(rows[0]["death_damage"]), _share(rows[0]["death_damage_raw"])
        self.assertGreater(pre["physical"], post["physical"])


if __name__ == "__main__":
    unittest.main()
