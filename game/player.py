# game/player.py
import time
from vision.cooldown_detector import is_ability_ready


# 👑 Умный трекер для расчета реальных секунд баффа без API игры
class BuffTimerTracker:
    def __init__(self):
        self.last_progress = 0.0
        self.last_time = 0.0
        self.estimated_max_duration = 30.0  # Базовая оценка длительности по умолчанию (30 сек)
        self.active = False

    def update(self, is_up: bool, progress: float) -> float:
        now = time.perf_counter()
        if not is_up or progress <= 0.0:
            self.active = False
            self.last_progress = 0.0
            return 0.0

        # Если бафф только появился или был обновлен (механика Пандемии: скачок полоски вверх)
        if not self.active or progress > self.last_progress + 0.05:
            self.active = True
            self.last_time = now
            self.last_progress = progress
            return round(self.estimated_max_duration * progress, 1)

        dt = now - self.last_time
        d_prog = self.last_progress - progress

        # Если полоска заметно сдвинулась вниз (прошло хотя бы 0.3 сек и 2% полоски)
        if d_prog > 0.02 and dt > 0.3:
            calc_max = dt / d_prog
            # Защита от выбросов: реальные баффы в WoW длятся от 3 до 600 секунд
            if 3.0 <= calc_max <= 600.0:
                # Плавное сглаживание (экспоненциальное скользящее среднее), чтобы таймер не дергался
                self.estimated_max_duration = 0.7 * self.estimated_max_duration + 0.3 * calc_max
            self.last_time = now
            self.last_progress = progress

        # Возвращаем оставшееся время в секундах!
        return round(self.estimated_max_duration * progress, 1)


class Player:
    def __init__(self, spec_id=None):
        self.spec_id = spec_id
        self.in_combat = False
        self.resources = {}
        self.buffs = {}
        self.cooldowns = {}
        self.spells = {}
        self._cooldown_etalons = {}

        # Словарь трекеров времени для каждого отдельного баффа
        self._buff_trackers = {}

    def update_from_vision(self, screen, wow_rect, profile_zones):
        self.resources = {}
        self.buffs = {}
        self.cooldowns = {}
        self.spells = {}

        from vision.detectors import ResourceDetector, BuffDetector

        for zone_name, zone_data in profile_zones.items():
            try:
                if zone_name in ("energy", "mana", "rage", "focus", "runic_power", "combo_points", "player_health_pct"):
                    detector = ResourceDetector(zone_data, screen, wow_rect)
                    self.resources[zone_name] = detector.read()

                elif zone_name.startswith("buff_") or zone_name.startswith("debuff_"):
                    # Передаем self.spec_id, чтобы детектор знал откуда брать эталоны уровней!
                    detector = BuffDetector(zone_name, zone_data, screen, wow_rect, spec_id=self.spec_id or 260)
                    res = detector.read()

                    # 👑 Подключаем расчет реальных секунд для этого баффа
                    if zone_name not in self._buff_trackers:
                        self._buff_trackers[zone_name] = BuffTimerTracker()

                    real_seconds = self._buff_trackers[zone_name].update(res.up, res.remains)

                    # Сохраняем в память и проценты, и реальные секунды, и уровень!
                    self.buffs[zone_name] = {
                        "up": res.up,
                        "remains_pct": res.remains,  # Процент (0.0 - 1.0)
                        "remains": real_seconds,  # 👑 Реальные секунды (например: 24.5)
                        "level": res.level  # Уровень стадий (1, 2, 3, 4)
                    }

                elif zone_name.startswith("cd_") or zone_name.startswith("spell_"):
                    x, y, w, h = zone_data
                    spell_name = zone_name.replace("cd_", "").replace("spell_", "")
                    etalon = self._cooldown_etalons.get(spell_name)

                    ready = is_ability_ready(screen, x, y, w, h, etalon_image=etalon)

                    if zone_name.startswith("cd_"):
                        self.cooldowns[spell_name] = {"ready": ready}
                    else:
                        self.spells[spell_name] = {"ready": ready}

            except Exception as e:
                pass

    def get_state_for_evaluation(self):
        state = {"in_combat": self.in_combat, **self.resources}

        # 👑 ЭКСПОРТ ДЛЯ РОТАЦИИ:
        # Теперь тебе доступны переменные: _up (True/False), _remains (секунды!), _remains_pct (%) и _level (1-4)
        for buff_name, data in self.buffs.items():
            safe_name = buff_name.replace('.', '_')
            state[f"{safe_name}_up"] = data["up"]
            state[f"{safe_name}_remains"] = data["remains"]  # Оставшиеся СЕКУНДЫ
            state[f"{safe_name}_remains_pct"] = data["remains_pct"]  # Оставшийся процент
            state[f"{safe_name}_level"] = data["level"]  # Распознанный уровень (1-4)

        for name, data in self.cooldowns.items():
            state[f"cooldown_{name.replace('.', '_')}_ready"] = data["ready"]

        for name, data in self.spells.items():
            state[f"spell_{name.replace('.', '_')}_ready"] = data["ready"]

        return state