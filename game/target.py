# game/target.py

class Target:
    def __init__(self):
        self.health_pct = 100.0
        self.debuffs = {}  # {"rupture": 18.7, "garrote": 22.1}

    def update_from_vision(self, screen, wow_rect, resource_configs):
        """
        Обновляет состояние цели на основе визуальных данных.
        :param screen: PIL.Image
        :param wow_rect: (x0, y0, x1, y1)
        :param resource_configs: list[dict] — конфиги ресурсов, относящихся к цели
        """
        self.health_pct = 100.0  # значение по умолчанию

        from vision.detectors import ResourceDetector
        for cfg in resource_configs:
            if cfg.get("variable_name") == "target_health_pct":
                try:
                    detector = ResourceDetector(cfg, screen, wow_rect)
                    self.health_pct = detector.read()
                except Exception as e:
                    print(f"⚠️ Target health error: {e}")
                break  # достаточно одного

    def get_state_for_evaluation(self):
        """Возвращает словарь для условий ротации."""
        return {
            "target_health_pct": self.health_pct,
            # Позже добавим debuff_rupture и т.д.
        }