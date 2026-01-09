# game/player.py

class Player:
    def __init__(self, spec_id=None):
        self.spec_id = spec_id
        self.in_combat = False
        # Ресурсы: energy, combo_points, health и т.д.
        self.resources = {}
        # Бафы: {"ruthless_precision": True, "adrenaline_rush": 12.3}
        self.buffs = {}
        # Кулдауны (в будущем): {"vanish": 45.2}
        self.cooldowns = {}

    def update_from_vision(self, screen, wow_rect, resource_configs, buff_configs=None):
        """
        Обновляет состояние игрока на основе визуальных данных.
        :param screen: PIL.Image — скриншот окна WoW
        :param wow_rect: (x0, y0, x1, y1) — координаты окна
        :param resource_configs: list[dict] — конфиги из spec_resources.json
        :param buff_configs: list[dict] — конфиги баффов (пока не используется)
        """
        # Очищаем предыдущие значения (или оставляем, если нужно накапливать)
        self.resources = {}
        self.buffs = {}

        # Обновляем ресурсы
        from vision.detectors import ResourceDetector
        for cfg in resource_configs:
            try:
                detector = ResourceDetector(cfg, screen, wow_rect)
                value = detector.read()
                var_name = cfg["variable_name"]
                self.resources[var_name] = value
            except Exception as e:
                print(f"⚠️ Player resource error: {e}")

        # Обновление баффов
            if buff_configs:
                from vision.detectors import BuffDetector
                for buff_name, cfg in buff_configs.items():
                    try:
                        detector = BuffDetector(cfg, screen, wow_rect)
                        is_active = detector.read()  # возвращает True/False
                        self.buffs[buff_name] = {"up": is_active, "remains": None}

                    except Exception as e:
                        print(f"⚠️ Buff '{buff_name}' error: {e}")

    def get_state_for_evaluation(self):
        """
        Возвращает словарь для использования в условиях ротации.
        Пример: {"energy": 142, "combo_points": 3, "in_combat": True}
        """
        state = {
            "in_combat": self.in_combat,
            **self.resources
        }
        # Добавляем бафы в формате buff_X_up
        for buff_name, data in self.buffs.items():
            state[f"buff_{buff_name}_up"] = data["up"]
            # Позже: state[f"buff_{buff_name}_remains"] = data["remains"]
        return state