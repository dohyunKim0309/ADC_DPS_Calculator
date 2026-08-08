"""Jinx — 베이스 스탯(패치16.13 검증) + 미니건 공속램프 + W(Zap!) 순수 물리 넛지.
[검증: CDragon raw + Wiki V26.04 + Meraki 3중교차]
Run: .venv/bin/python -m tests.test_jinx
"""
from unittest.mock import patch

from adc_sim.champion import Jinx, Target
from adc_sim.engine import run_simulation, calculate_mitigation
from adc_sim.runes import LethalTempo, CutDown
from adc_sim.data.items_registry import create_item_from_key


def test_jinx_base_stats():
    """검증값(패치16.13): AD 59(+3.25), AS 0.625(ratio 0.625, +1%/lvl), 마나 260(+50), mp5 6.7(+1.0)."""
    j = Jinx(level=1)
    assert j.base_ad == 59 and abs(j.ad_growth - 3.25) < 1e-9   # 3.15(스테일) → 3.25
    assert abs(j.base_as - 0.625) < 1e-9 and abs(j.as_ratio - 0.625) < 1e-9
    assert abs(j.as_growth - 1.0) < 1e-9                         # V26.01 너프(1.4→1.0)
    assert j.base_mana == 260.0 and j.mana_growth == 50.0
    assert abs(j.base_mp5 - 6.7) < 1e-9 and abs(j.mp5_growth - 1.0) < 1e-9
    # 레벨 11 기본 AD = 59 + 3.25*10 = 91.5
    assert abs(Jinx(level=11).base_attack_ad - 91.5) < 1e-9


def test_jinx_w_data():
    """W(Zap!) 상수: base [10,60,110,160,210], 140% 추가AD, 쿨 8→4, 마나 40→60(랭크별)."""
    assert Jinx.W_BASE == [10.0, 60.0, 110.0, 160.0, 210.0]
    assert abs(Jinx.W_BONUS_AD_RATIO - 1.40) < 1e-9
    assert Jinx.W_CD == [8.0, 7.0, 6.0, 5.0, 4.0]
    assert Jinx.W_MANA == [40.0, 45.0, 50.0, 55.0, 60.0]
    # w_level 랭크별 마나 게이트가 mana_cost 로 세팅
    assert Jinx(w_level=1).mana_cost["w"] == 40.0
    assert Jinx(w_level=5).mana_cost["w"] == 60.0


def test_jinx_w_damage_is_bonus_ad_physical():
    """W = base + 1.40*(추가AD). 물리(방어 경감·방관 적용), 마법 성분 0."""
    j = Jinx(level=11, w_level=3)
    j.init_combat_state()
    j.add_item(create_item_from_key("kraken"))     # +45 AD → 추가AD 45
    bonus_ad = j.total_ad - j.base_attack_ad
    assert abs(bonus_ad - 45.0) < 1e-9
    p, m = j._cast_w(0.0)
    assert abs(p - (110.0 + 1.40 * 45.0)) < 1e-9   # 110 + 63 = 173
    assert m == 0.0                                 # 순수 물리(마법 0)
    # 물리라서 방어력엔 경감되고 마저엔 무영향
    ap, am = calculate_mitigation(p, 0.0, Target(hp=1, armor=100, magic_resist=100), j)
    assert abs(ap - 173.0 * 100.0 / 200.0) < 1e-6 and am == 0.0


def test_jinx_w_is_pure_no_crit_no_onhit():
    """핵심: W는 크리·평타온힛 미적용. 크리+온힛 아이템을 껴도 W raw = base + 1.40*추가AD 그대로."""
    j = Jinx(level=13, w_level=5)
    j.init_combat_state()
    for k in ("ie", "guinsoo", "pd"):              # ie/pd=크리, guinsoo=온힛
        j.add_item(create_item_from_key(k))
    j.crit_chance = 1.0                             # 치명타 100% 강제
    bonus_ad = j.total_ad - j.base_attack_ad
    p, m = j._cast_w(0.0)
    assert abs(p - (210.0 + 1.40 * bonus_ad)) < 1e-9  # 크리 배수·구인수 온힛 안 섞임
    assert m == 0.0                                    # 구인수 온힛 마법 미포함


def test_jinx_minigun_as_ramp_and_cap():
    """미니건 3스택 = +130%(랭크5). fishbones 는 스택 미적용·보너스AS ×0.90. 엔진 공속캡=3.0."""
    # 미니건 최대 스택: super 보너스 + 1.30
    jm = Jinx(level=1, q_level=5, minigun_stacks=3, q_mode="minigun")
    jm.add_item(create_item_from_key("berserker"))     # +0.25 AS
    assert abs(jm.get_total_bonus_as_percent() - (0.25 + 1.30)) < 1e-9
    # fishbones: 스택 미적용, 보너스AS ×0.90
    jf = Jinx(level=1, q_level=5, minigun_stacks=3, q_mode="fishbones")
    jf.add_item(create_item_from_key("berserker"))
    assert abs(jf.get_total_bonus_as_percent() - (0.25 * 0.90)) < 1e-9
    # 공속 상한(현재 엔진 3.0): 과충전 시 3.0 로 클램프 [AS-CAP: 실제 롤 2.5 — 별도 결정사항]
    # Jinx 는 base/ratio 0.625 라 캡 도달에 ~380% 추가공속 필요 → 순수 공속 6코어로 과충전해 확인.
    jcap = Jinx(level=18, q_level=5, minigun_stacks=3, q_mode="minigun")
    for k in ("nashor", "pd", "runaan", "rfc", "terminus", "guinsoo"):
        jcap.add_item(create_item_from_key(k))
    assert jcap.current_attack_speed == 3.0


def test_jinx_w_mana_gated():
    """마나가 W 비용 미만이면 시전 불가(스킬 이벤트 inf), 충전되면 0dt 로 시전 가능."""
    j = Jinx(level=11, w_level=5)          # W 마나 60
    j.init_combat_state()
    j.current_mana = 10.0                  # 부족
    assert not j._can_cast("w")
    assert j.get_time_to_next_skill_event(0.0) == float("inf") or j.get_time_to_next_skill_event(0.0) > 0
    j.current_mana = j.total_mana          # 충전
    assert j._can_cast("w")
    assert j.get_time_to_next_skill_event(0.0) == 0.0


def test_jinx_sim_runs_and_w_fires():
    """엔진 통합: 미니건 지속딜 sim 이 양의 DPS 산출 + W 스킬 이벤트가 실제 발동."""
    j = Jinx(level=13, q_level=5, w_level=3, q_mode="minigun")
    j.set_rune(LethalTempo()); j.set_sub_rune(CutDown())
    for k in ("berserker", "kraken", "pd", "ie"):
        j.add_item(create_item_from_key(k))
    # W 발동 카운트 스파이
    fired = [0]
    orig = j._cast_w
    def spy(t):
        fired[0] += 1
        return orig(t)
    j._cast_w = spy
    _h, dps, kt = run_simulation(j, Target(hp=1700, armor=60, magic_resist=32),
                                 verbose=False, respawn_to_full_kills=2)
    assert dps > 0 and kt > 0
    assert fired[0] >= 1                    # W 최소 1회 시전


def test_jinx_dedicated_sim_defaults_to_long_range_fishbones():
    """전용 징크스 경로는 기본적으로 미니건이 아닌 장거리 Fishbones를 사용한다."""
    from adc_sim.simulations import jinx as jinx_sim

    captured = {}

    def fake_run(champion, target, **kwargs):
        captured["q_mode"] = champion.q_mode
        captured["minigun_stacks"] = champion.minigun_stacks
        return 0.0, 123.0, {}

    with patch.object(jinx_sim, "run_simulation", fake_run):
        dps, _ = jinx_sim.simulate_jinx_core_path(("kraken", "pd", "ie", "ldr"), 1)

    assert dps == 123.0
    assert captured == {"q_mode": "fishbones", "minigun_stacks": 0}


def test_jinx_dps_ranking_dedupes_by_dps_not_dpg():
    """DPS 랭킹은 고비용이어도 DPS가 더 높은 패키지를 DPG dedup 전에 보존한다."""
    from adc_sim.simulations import jinx as jinx_sim

    challenger = ("storm", "c44", "ldr", "ie")
    paths = [jinx_sim.CONTROL_PATH, challenger]
    seen_q_modes = []

    def fake_sim(full_path, core_tier, doran_key="doranblade", boots_key="berserker",
                 rune_as_bonus=0.0, q_mode="fishbones"):
        seen_q_modes.append(q_mode)
        if tuple(full_path) == challenger:
            # Berserker 패키지는 DPG가 높고, Glutton 패키지는 절대 DPS가 높다.
            return ((200.0, 1000.0) if boots_key == "berserker" else (300.0, 10000.0))
        return 100.0, 1000.0

    jinx_sim._JINX_TOP1_CACHE.clear()
    try:
        with patch.object(jinx_sim, "_build_all_paths", return_value=paths), \
                patch.object(jinx_sim, "simulate_jinx_core_path", side_effect=fake_sim):
            dps_top = jinx_sim.get_jinx_4core_top1_build(rank_by="dps")
            dpg_top = jinx_sim.get_jinx_4core_top1_build(rank_by="dpg")
    finally:
        jinx_sim._JINX_TOP1_CACHE.clear()

    assert dps_top["path"] == challenger
    assert dps_top["boots"] == "glutton"
    assert dps_top["q_mode"] == "fishbones"
    assert dpg_top["boots"] == "berserker"
    assert set(seen_q_modes) == {"fishbones"}


if __name__ == "__main__":
    for nm, f in sorted(globals().items()):
        if nm.startswith("test_") and callable(f):
            f(); print(f"PASS {nm}")
    print("ALL PASS")
