"""K=2 리스폰 시 첫 처치 오버킬을 다음 체력바에 이월하지 않는지 검증한다."""

import pytest

from adc_sim.champion import Champion, Target
from adc_sim.engine import run_simulation


class BasicOverkillChampion(Champion):
    """매 평타로 고정 피해를 주며 공격 직전 타깃 HP를 기록하는 테스트 챔피언."""

    def __init__(self, damage):
        """평타 고정 피해량을 설정하고 관측 목록을 초기화한다."""
        super().__init__("BasicOverkill", 0, 1.0, 1.0, 0, 500)
        self.damage = damage
        self.seen_hp = []

    def get_one_hit_damage(self, target, time=0):
        """공격 직전 HP를 기록하고 방어 무시 고정 피해 한 번을 반환한다."""
        self.seen_hp.append(target.current_hp)
        return 0.0, 0.0, 0.0, 0.0, self.damage, 0.0


class SkillOverkillChampion(Champion):
    """1초 간격 스킬로 고정 피해를 주며 시전 직전 타깃 HP를 기록하는 테스트 챔피언."""

    def __init__(self, damage):
        """스킬 고정 피해량과 시전 횟수 및 관측 목록을 초기화한다."""
        super().__init__("SkillOverkill", 0, 1.0, 1.0, 0, 500)
        self.damage = damage
        self.cast_count = 0
        self.seen_hp = []

    def init_combat_state(self, skill_plan=None):
        """스킬 두 번만 사용하고 평타는 발생하지 않도록 전투 상태를 초기화한다."""
        super().init_combat_state(skill_plan)
        self.cast_count = 0
        self.cast_lockout_until = float("inf")

    def get_time_to_next_skill_event(self, current_time):
        """첫 스킬은 0초, 두 번째 스킬은 1초에 예약한다."""
        if self.cast_count >= 2:
            return float("inf")
        return max(0.0, float(self.cast_count) - current_time)

    def pop_due_skill_events(self, current_time, target):
        """예약 시각마다 실제 적중하는 테스트 스킬 이벤트 하나를 반환한다."""
        self.cast_count += 1
        return [("q", 0.0, 0.0, True)]

    def get_on_skill_hit_damage(self, target, time=0.0):
        """스킬 적중 직전 HP를 기록하고 방어 무시 고정 피해를 반환한다."""
        self.seen_hp.append(target.current_hp)
        return 0.0, 0.0, self.damage


@pytest.mark.parametrize("champion_cls", [BasicOverkillChampion, SkillOverkillChampion])
def test_k2_respawn_starts_second_health_bar_at_full_hp(champion_cls):
    """첫 처치가 20 오버킬이어도 두 번째 체력바는 80이 아닌 100에서 시작한다."""
    champion = champion_cls(damage=120.0)
    target = Target(hp=100.0, armor=0.0, magic_resist=0.0)

    _, dps, kill_time = run_simulation(
        champion,
        target,
        verbose=False,
        respawn_to_full_kills=2,
    )

    assert champion.seen_hp == [100.0, 100.0]
    assert kill_time == pytest.approx(1.0)
    assert dps == pytest.approx(240.0)
