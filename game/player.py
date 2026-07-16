# game/player.py
from vision.cooldown_detector import is_ability_ready


class Player:
    def __init__(self, spec_id=None):
        self.spec_id = spec_id
        self.in_combat = False
        self.resources = {}
        self.buffs = {}
        self.cooldowns = {}
        self.spells = {}
        self._cooldown_etalons = {}

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
                    detector = BuffDetector(zone_name, zone_data, screen, wow_rect)
                    self.buffs[zone_name] = detector.read().to_dict()

                elif zone_name.startswith("cd_") or zone_name.startswith("spell_"):
                    x, y, w, h = zone_data
                    spell_name = zone_name.replace("cd_", "").replace("spell_", "")
                    etalon = self._cooldown_etalons.get(spell_name)

                    # 💡 Убрали wow_rect[0] + x — координаты уже корректные!
                    ready = is_ability_ready(screen, x, y, w, h, etalon_image=etalon)

                    if zone_name.startswith("cd_"):
                        self.cooldowns[spell_name] = {"ready": ready}
                    else:
                        self.spells[spell_name] = {"ready": ready}

            except Exception as e:
                pass

    def get_state_for_evaluation(self):
        state = {"in_combat": self.in_combat, **self.resources}
        for buff_name, data in self.buffs.items(): state[f"{buff_name.replace('.', '_')}_up"] = data["up"]
        for name, data in self.cooldowns.items(): state[f"cooldown_{name.replace('.', '_')}_ready"] = data["ready"]
        for name, data in self.spells.items(): state[f"spell_{name.replace('.', '_')}_ready"] = data["ready"]
        return state