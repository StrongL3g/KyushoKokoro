# game/player.py
from vision.cooldown_detector import is_ability_ready

class Player:
    def __init__(self, spec_id=None):
        self.spec_id = spec_id
        self.in_combat = False
        self.resources = {}
        self.buffs = {}
        self.cooldowns = {}
        self._cooldown_etalons = {}

    def update_from_vision(self, screen, wow_rect, resource_configs, buff_configs=None):
        """
        Обновляет состояние игрока на основе визуальных данных.
        :param screen: PIL.Image — скриншот окна WoW
        :param wow_rect: (x0, y0, x1, y1) — координаты окна
        :param resource_configs: list[dict] — конфиги из spec_resources.json
        :param buff_configs: list[dict] — конфиги баффов
        """
        # Очищаем предыдущие значения
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
        print(f"📊 Загружено баффов: {len(buff_configs) if buff_configs else 0}")

        if buff_configs:
            # Гарантируем, что все ожидаемые бафы присутствуют
            for buff_name in buff_configs.keys():
                self.buffs[buff_name] = {"up": False, "remains": None}

            # Теперь обновляем только те, что реально активны
            from vision.detectors import BuffDetector
            for buff_name, cfg in buff_configs.items():
                try:
                    detector = BuffDetector(cfg, screen, wow_rect)
                    result = detector.read()

                    # Используем to_dict() для конвертации BuffResult в словарь
                    self.buffs[buff_name] = result.to_dict()

                    # Отладочный вывод
                    print(f"🔍 Бафф '{buff_name}': up={result.up}, remains={result.remains}")

                except Exception as e:
                    print(f"⚠️ Buff '{buff_name}' error: {e}")
                    # Оставляем как False (уже инициализировано выше)

            # В конце update_from_vision:
            print(f"📈 Состояние баффов после обновления:")
            for buff_name, data in self.buffs.items():
                print(f"  {buff_name}: up={data.get('up')}, remains={data.get('remains')}")

    def get_state_for_evaluation(self):
        """
        Возвращает словарь для использования в условиях ротации.
        Бафы экспортируются как плоские переменные: buff_NAME_up, buff_NAME_remains
        """
        state = {
            "in_combat": self.in_combat,
            **self.resources
        }

        # Экспорт баффов в плоском виде: buff_adrenaline_rush_up, buff_blade_flurry_remains и т.д.
        for buff_name, data in self.buffs.items():
            safe_name = buff_name.replace('.', '_')  # на случай, если в имени есть точки
            state[f"buff_{safe_name}_up"] = data["up"]
            if data.get("remains") is not None:
                state[f"buff_{safe_name}_remains"] = data["remains"]
            # progress не используем — убран

        # Кулдауны → cooldown_NAME_ready
        for name, data in self.cooldowns.items():
            safe_name = name.replace('.', '_')
            state[f"cooldown_{safe_name}_ready"] = data["ready"]

        return state

    def update_cooldowns_from_vision(self, screen, wow_rect, cooldown_configs):
        """
        Обновляет состояние кулдаунов способностей.
        :param cooldown_configs: dict из ability_cooldowns.json
        """
        self.cooldowns = {}
        x0, y0, x1, y1 = wow_rect
        for name, cfg in cooldown_configs.items():
            icon_x = x0 + cfg["x"]
            icon_y = y0 + cfg["y"]
            etalon = self._cooldown_etalons.get(name)
            ready = is_ability_ready(
                screen, icon_x, icon_y, cfg["width"], cfg["height"],
                etalon_image=etalon, debug_name=name if cfg.get("debug") else ""
            )
            self.cooldowns[name] = {"ready": ready}