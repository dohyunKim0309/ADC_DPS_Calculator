"""경감 역산(view D) 산술 검증 — 합성 매치/타임라인으로 왕복을 맞춘다.

엔진 규약과 같은 식을 쓴다: eff = resist*(1-%pen) - flat_pen (음수 클램프),
post = raw * 100/(100+eff). D 는 이 식을 뒤집어 raw 를 복원한다.
"""
import json
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


class TestLethalityAssumption(unittest.TestCase):
    """armorPen 필드가 실측상 항상 0 — 가정 리썰리티로 민감도를 볼 수 있어야 한다."""

    def test_assumed_lethality_lowers_physical_estimate(self):
        from tools.riot_damage_mix import _unmitigate_death_damage as un
        base, _ = un(_timeline(0.35, 0), VICTIM)
        with_pen, _ = un(_timeline(0.35, 0), VICTIM, assume_lethality=18)
        self.assertAlmostEqual(base["physical"], 1000 * 1.39)      # eff 방어력 39
        self.assertAlmostEqual(with_pen["physical"], 1000 * 1.21)  # 39 - 18 = 21
        self.assertLess(with_pen["physical"], base["physical"])

    def test_observed_flat_pen_wins_over_assumption(self):
        from tools.riot_damage_mix import _unmitigate_death_damage as un
        raw, _ = un(_timeline(0.35, 18), VICTIM, assume_lethality=40)
        self.assertAlmostEqual(raw["physical"], 1000 * 1.21)       # 관측 18 을 쓴다

    def test_assumption_does_not_apply_to_minion_damage(self):
        from tools.riot_damage_mix import _unmitigate_death_damage as un
        tl = _timeline(0.0, 0)
        tl["info"]["frames"][0]["events"][0]["victimDamageReceived"][0]["participantId"] = 0
        raw, _ = un(tl, VICTIM, assume_lethality=30)
        self.assertAlmostEqual(raw["physical"], 1000 * 1.60)       # 방어력 60 전부


class TestLethalityFromItems(unittest.TestCase):
    """리썰리티는 championStats 에 안 실린다 — DDragon 설명문에서 유도한다."""

    DDRAGON = {"data": {
        "3142": {"name": "Youmuu's Ghostblade",
                 "description": "<mainText><stats><attention>60</attention> Attack Damage"
                                "<br><attention>18</attention> Lethality</stats></mainText>"},
        "3179": {"name": "Umbral Glaive",
                 "description": "<stats><attention>50</attention> Attack Damage"
                                "<br><attention>15</attention> Lethality</stats>"},
        "3031": {"name": "Infinity Edge",
                 "description": "<stats><attention>70</attention> Attack Damage</stats>"},
    }}

    def setUp(self):
        import tempfile, pathlib, tools.riot_damage_mix as M
        self.M = M
        self._cache = M.CACHE
        M.CACHE = pathlib.Path(tempfile.mkdtemp())
        (M.CACHE / "_ddragon_items.json").write_text(json.dumps(self.DDRAGON),
                                                     encoding="utf-8")

    def tearDown(self):
        self.M.CACHE = self._cache

    def test_parses_lethality_and_skips_items_without_it(self):
        table = self.M._lethality_table()
        self.assertEqual(table, {"3142": 18, "3179": 15})

    def test_flat_pen_sums_items_and_scales_with_level(self):
        table = {"3142": 18, "3179": 15}                      # 합 33
        self.assertAlmostEqual(self.M._flat_armor_pen([3142, 3179], table, 18), 33.0)
        self.assertAlmostEqual(self.M._flat_armor_pen([3142, 3179], table, 9),
                               33.0 * (0.6 + 0.4 * 9 / 18))
        self.assertEqual(self.M._flat_armor_pen([3031], table, 18), 0.0)

    def test_derived_pen_lowers_physical_estimate(self):
        """가해자가 유뮤를 들고 있으면 역산이 그만큼 방어력을 깎아야 한다."""
        tl = _timeline(0.0, 0)          # 관측 armorPen 0, %관통 0
        frames = tl["info"]["frames"]
        frames[0]["participantFrames"][str(VICTIM)]["level"] = 18
        frames[0]["events"].insert(0, {"type": "ITEM_PURCHASED", "participantId": ATTACKER,
                                       "itemId": 3142, "timestamp": 0})
        base, _ = self.M._unmitigate_death_damage(tl, VICTIM)
        derived, _ = self.M._unmitigate_death_damage(tl, VICTIM,
                                                    lethality_table={"3142": 18})
        self.assertAlmostEqual(base["physical"], 1000 * 1.60)      # 방어력 60 전부
        self.assertAlmostEqual(derived["physical"], 1000 * 1.42)   # 60 - 18 = 42

    def test_explicit_assumption_overrides_derivation(self):
        tl = _timeline(0.0, 0)
        tl["info"]["frames"][0]["events"].insert(
            0, {"type": "ITEM_PURCHASED", "participantId": ATTACKER,
                "itemId": 3142, "timestamp": 0})
        raw, _ = self.M._unmitigate_death_damage(tl, VICTIM, assume_lethality=30,
                                                 lethality_table={"3142": 18})
        self.assertAlmostEqual(raw["physical"], 1000 * 1.30)       # 60 - 30
