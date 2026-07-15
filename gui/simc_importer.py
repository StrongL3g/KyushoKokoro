import os
import json
import re
import customtkinter as ctk


class SimcImportWindow(ctk.CTkToplevel):
    def __init__(self, parent, spec_id=260, on_success_callback=None):
        super().__init__(parent)
        self.spec_id = spec_id
        self.on_success = on_success_callback

        self.title(f"Импорт профиля SimulationCraft (Спек: {self.spec_id})")
        self.geometry("700x550")
        self.minsize(500, 400)

        # Делаем окно модальным
        self.transient(parent)
        self.grab_set()

        # Заголовок и инструкции
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.pack(side="top", fill="x", padx=15, pady=(15, 5))

        lbl_title = ctk.CTkLabel(
            top_frame,
            text="Генератор базы спеллов из SimulationCraft / Raidbots",
            font=("Arial", 16, "bold")
        )
        lbl_title.pack(anchor="w")

        lbl_hint = ctk.CTkLabel(
            top_frame,
            text="Скопируй текст профиля (APL) и вставь его в поле ниже. Существующие хоткеи не удалятся!",
            text_color="gray",
            font=("Arial", 12)
        )
        lbl_hint.pack(anchor="w", pady=(2, 0))

        # Текстовое поле
        self.textbox = ctk.CTkTextbox(self, wrap="word", font=("Consolas", 11))
        self.textbox.pack(side="top", fill="both", expand=True, padx=15, pady=10)

        # Нижняя панель
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", padx=15, pady=(0, 15))

        self.lbl_status = ctk.CTkLabel(bottom_frame, text="", font=("Arial", 12))
        self.lbl_status.pack(side="left", anchor="w")

        btn_cancel = ctk.CTkButton(
            bottom_frame, text="Отмена", command=self.destroy,
            width=100, fg_color="gray", hover_color="darkgray"
        )
        btn_cancel.pack(side="right", padx=(10, 0))

        btn_generate = ctk.CTkButton(
            bottom_frame, text="✨ Сгенерировать базу", command=self.process_import,
            width=160, fg_color="green", hover_color="darkgreen"
        )
        btn_generate.pack(side="right")

    def _extract_spec_id(self, simc_text):
        """
        Извлекает spec_id из профиля SimC.
        Возвращает числовой ID или None.
        """
        # Маппинг названий спеков в ID (добавь нужные)
        spec_map = {
            "outlaw": 260,
            "assassination": 259,
            "subtlety": 261,
            "havoc": 577,
            "vengeance": 581,
            # Добавь другие спеки по необходимости
        }

        # Ищем строку spec=...
        spec_match = re.search(r'^spec=(\w+)', simc_text, re.MULTILINE | re.IGNORECASE)
        if spec_match:
            spec_name = spec_match.group(1).lower()
            return spec_map.get(spec_name, self.spec_id)

        # Если не нашли spec, пробуем определить по классу и специализации
        class_match = re.search(r'^class=(\w+)', simc_text, re.MULTILINE | re.IGNORECASE)
        if class_match:
            class_name = class_match.group(1).lower()
            # Можно добавить более сложную логику определения спека

        return self.spec_id

    def process_import(self):
        raw_text = self.textbox.get("0.0", "end").strip()
        if not raw_text:
            self.lbl_status.configure(text="⚠️ Текстовое поле пустое!", text_color="orange")
            return

        # Извлекаем spec_id из профиля
        detected_spec_id = self._extract_spec_id(raw_text)
        if detected_spec_id != self.spec_id:
            self.spec_id = detected_spec_id
            self.title(f"Импорт профиля SimulationCraft (Спек: {self.spec_id})")
            print(f"🔍 Определён спек: {self.spec_id}")

        # Парсим текст
        parsed_spells = self._parse_simc(raw_text)
        if not parsed_spells:
            self.lbl_status.configure(text="❌ Не удалось найти спеллы. Проверь текст!", text_color="red")
            return

        # Путь к файлу базы спеллов
        spec_dir = os.path.join("class_data", str(self.spec_id))
        os.makedirs(spec_dir, exist_ok=True)
        spells_file = os.path.join(spec_dir, "spells.json")

        # Загружаем существующие спеллы
        existing_spells = {}
        if os.path.exists(spells_file):
            try:
                with open(spells_file, "r", encoding="utf-8") as f:
                    existing_spells = json.load(f)
            except Exception as e:
                print(f"⚠️ Ошибка чтения старого файла {spells_file}: {e}")

        new_count = 0
        updated_count = 0

        for spell_id, data in parsed_spells.items():
            if spell_id in existing_spells:
                old_hotkey = existing_spells[spell_id].get("hotkey", "")
                existing_spells[spell_id].update(data)
                existing_spells[spell_id]["hotkey"] = old_hotkey
                updated_count += 1
            else:
                existing_spells[spell_id] = data
                new_count += 1

        # Сохраняем
        try:
            with open(spells_file, "w", encoding="utf-8") as f:
                json.dump(existing_spells, f, indent=4, ensure_ascii=False)

            msg = f"✅ Успешно! Спек: {self.spec_id}, Новых: {new_count}, Обновлено: {updated_count}"
            self.lbl_status.configure(text=msg, text_color="green")
            print(f"💾 База спеллов сохранена в: {spells_file}")

            if self.on_success:
                self.on_success()

            self.after(1500, self.destroy)

        except Exception as e:
            self.lbl_status.configure(text=f"❌ Ошибка сохранения: {e}", text_color="red")

    def _parse_simc(self, simc_text):
        """
        Улучшенный парсер SimulationCraft.
        Корректно обрабатывает условия и извлекает чистые названия способностей.
        """
        spells_db = {}

        # Системные команды, которые нужно игнорировать
        ignored_keywords = {
            "variable", "call_action_list", "run_action_list", "pool_resource",
            "use_items", "snapshot_stats", "potion", "blood_fury", "berserking",
            "fireblood", "ancestral_call", "arcane_torrent", "arcane_pulse",
            "lights_judgment", "bag_of_tricks", "stealth", "kick", "apply_poison",
            "auto_attack", "vanish", "shadowmeld", "precombat", "default"
        }

        # Маппинг секций в типы способностей
        list_to_type_map = {
            "build": "builder",
            "finish": "finisher",
            "cds": "cooldown",
            "precombat": "buff"
        }

        # Приоритет типов (чем выше, тем важнее)
        type_priority = {
            "finisher": 4,
            "builder": 4,
            "cooldown": 3,
            "buff": 1,
            "general": 0
        }

        # Шаг 1: Поиск всех строк с действиями
        # Ищем строки вида: actions.build+=/spell_name,if=condition
        action_pattern = r'actions(?:\.(\w+))?(?:\+)?=/?([a-z_][a-z_0-9]*)'

        for line in simc_text.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Ищем действия в строке
            matches = re.findall(action_pattern, line, re.IGNORECASE)

            for list_name, spell_name in matches:
                spell_name = spell_name.lower().strip()

                # Пропускаем системные команды
                if spell_name in ignored_keywords or len(spell_name) <= 1:
                    continue

                # Определяем тип способности
                new_type = list_to_type_map.get(list_name.lower() if list_name else "", "general")

                if spell_name not in spells_db:
                    readable_name = spell_name.replace('_', ' ').title()
                    spells_db[spell_name] = {
                        "name": readable_name,
                        "type": new_type,
                        "hotkey": ""
                    }
                else:
                    # Обновляем тип если новый приоритет выше
                    old_type = spells_db[spell_name]["type"]
                    if type_priority.get(new_type, 0) > type_priority.get(old_type, 0):
                        spells_db[spell_name]["type"] = new_type

        # Шаг 2: Поиск баффов и дебаффов
        buff_pattern = r'(buff|debuff)\.([a-z_][a-z_0-9]*)\.'
        for match in re.finditer(buff_pattern, simc_text, re.IGNORECASE):
            buff_type, buff_name = match.groups()
            buff_name = buff_name.lower().strip()

            if buff_name in ignored_keywords or len(buff_name) <= 1:
                continue

            buff_key = f"buff_{buff_name}" if buff_type.lower() == "buff" else f"debuff_{buff_name}"
            if buff_key not in spells_db:
                readable_name = buff_name.replace('_', ' ').title()
                spells_db[buff_key] = {
                    "name": f"{'Buff' if buff_type.lower() == 'buff' else 'Debuff'}: {readable_name}",
                    "type": "buff" if buff_type.lower() == "buff" else "debuff",
                    "hotkey": None
                }

        # Отладка
        builders = [k for k, v in spells_db.items() if v["type"] == "builder"]
        finishers = [k for k, v in spells_db.items() if v["type"] == "finisher"]
        cds = [k for k, v in spells_db.items() if v["type"] == "cooldown"]
        buffs = [k for k, v in spells_db.items() if v["type"] in ("buff", "debuff")]

        print(f"🔍 [SimC Parser] Успешно разобран профиль!")
        print(f"   ⚔️ Builders ({len(builders)}): {', '.join(builders)}")
        print(f"   💥 Finishers ({len(finishers)}): {', '.join(finishers)}")
        print(f"   🔥 Cooldowns ({len(cds)}): {', '.join(cds)}")
        print(f"   🛡️ Buffs/Debuffs ({len(buffs)}): {', '.join(buffs)}")

        return spells_db