import pytest

from adc_sim.champion import Champion, Target
from adc_sim.core_items import BladeOfRuinedKing
from adc_sim.data.items_data import BLOODLINE_LIFESTEAL
from adc_sim.engine import run_simulation
from adc_sim.item_base import Item
from adc_sim.simulations.kaisa import simulate_kaisa_core_path


class _FlatOnHitWithSustain(Item):
    """Provide deterministic non-BotRK on-hit damage and both sustain stats for classification tests."""

    def __init__(self):
        super().__init__("Flat On-Hit", lifesteal=0.10, omnivamp=0.05)

    def on_hit(self, target, champion):
        """Return 100 physical on-hit damage; parameters are unused by this deterministic fixture."""
        return 100.0, 0.0, 0.0, 0.0


def _plain_champion():
    """Return a deterministic 100-AD champion with no growth, crit, runes, or skill damage."""
    return Champion(
        name="Sustain Test",
        base_ad=100,
        base_as=1.0,
        as_ratio=1.0,
        as_growth=0.0,
        base_range=550,
    )


def test_non_botrk_onhit_is_omnivamp_only():
    """Generic on-hit damage feeds omnivamp but must not enter the lifesteal damage pool."""
    champion = _plain_champion()
    champion.add_item(_FlatOnHitWithSustain())
    run_simulation(
        champion,
        Target(hp=150, armor=0, magic_resist=0),
        verbose=False,
        respawn_to_full_kills=1,
    )

    metrics = champion.sustain_metrics
    assert metrics["lifesteal_eligible_damage"] == pytest.approx(100.0)
    assert metrics["omnivamp_eligible_damage"] == pytest.approx(200.0)
    assert metrics["lifesteal_healing"] == pytest.approx(10.0)
    assert metrics["omnivamp_healing"] == pytest.approx(10.0)


def test_botrk_onhit_is_included_in_lifesteal_pool():
    """BotRK current-health damage is the explicit on-hit exception included in lifesteal."""
    champion = _plain_champion()
    champion.add_item(BladeOfRuinedKing())
    run_simulation(
        champion,
        Target(hp=1000, armor=0, magic_resist=0),
        verbose=False,
        respawn_to_full_kills=1,
    )

    metrics = champion.sustain_metrics
    assert metrics["botrk_lifesteal_damage"] > 0
    assert metrics["lifesteal_eligible_damage"] == pytest.approx(
        metrics["omnivamp_eligible_damage"]
    )
    assert metrics["lifesteal_healing"] == pytest.approx(
        metrics["lifesteal_eligible_damage"] * 0.10
    )


@pytest.mark.parametrize(
    ("boots_key", "bloodline", "expected_tier"),
    (
        ("berserker", 0.0, 0),
        ("berserker", BLOODLINE_LIFESTEAL, 1),
        ("glutton", 0.0, 1),
        ("glutton", BLOODLINE_LIFESTEAL, 2),
    ),
)
def test_kaisa_sustain_tier_counts_boots_and_bloodline(boots_key, bloodline, expected_tier):
    """Kai'Sa sustain tier is exactly the number of Glutton/Bloodline primary sources."""
    _, _, _, sustain = simulate_kaisa_core_path(
        ("kraken", "guinsoo", "ie", "ldr"),
        1,
        doran_key="doranblade",
        boots_key=boots_key,
        bloodline_lifesteal=bloodline,
        return_sustain=True,
    )

    assert sustain["tier"] == expected_tier
    assert sustain["lifesteal_rate"] >= bloodline
    assert sustain["total_healing"] == pytest.approx(
        sustain["lifesteal_healing"] + sustain["omnivamp_healing"]
    )
