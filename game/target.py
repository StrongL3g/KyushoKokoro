# game/target.py
class Target:
    def __init__(self):
        self.health_pct = 100.0
        self.active_enemies = 0

    def update_from_vision(self, screen, wow_rect, profile_zones, active_enemies=None):
        self.health_pct = 100.0

        # Проверяем, настроил ли пользователь зону здоровья цели в калибраторе
        if "target_health_pct" in profile_zones:
            from vision.detectors import ResourceDetector
            try:
                detector = ResourceDetector(profile_zones["target_health_pct"], screen, wow_rect)
                self.health_pct = detector.read()
            except Exception as e:
                print(f"⚠️ Target health error: {e}")

        self.active_enemies = active_enemies if active_enemies is not None else 1

    def get_state_for_evaluation(self):
        return {
            "target_health_pct": self.health_pct,
            "active_enemies": self.active_enemies
        }