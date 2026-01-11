# game/target.py

class Target:
    def __init__(self):
        self.health_pct = 100.0
        self.active_enemies = 0
        self.debuffs = {}

    def update_from_vision(self, screen, wow_rect, resource_configs, active_enemies=None):
        """
        Обновляет состояние цели на основе визуальных данных.
        :param screen: PIL.Image
        :param wow_rect: (x0, y0, x1, y1)
        :param resource_configs: list[dict] — конфиги ресурсов, относящихся к цели
        """
        self.health_pct = 100.0
        from vision.detectors import ResourceDetector
        for cfg in resource_configs:
            if cfg.get("variable_name") == "target_health_pct":
                try:
                    detector = ResourceDetector(cfg, screen, wow_rect)
                    self.health_pct = detector.read()
                except Exception as e:
                    print(f"⚠️ Target health error: {e}")
                break

        # Количество целей — теперь извне
        if active_enemies is not None:
            self.active_enemies = active_enemies
        else:
            self.active_enemies = 1

    def get_state_for_evaluation(self):
        return {
            "target_health_pct": self.health_pct,
            "active_enemies": self.active_enemies
        }