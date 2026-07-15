import os
import json
import customtkinter as ctk
from config.paths import SPEC_NAMES_PATH, CLASS_DATA_DIR


class SpellEditorWindow(ctk.CTkToplevel):
    def __init__(self, parent, current_spec_id=260):
        super().__init__(parent)
        self.title("⌨️ Центр настройки хоткеев и способностей")
        self.geometry("800x650")
        self.minsize(600, 450)

        # Делаем окно модальным и поверх основного
        self.transient(parent)
        self.grab_set()

        self.spells_data = {}
        self.entry_widgets = {}

        # 1. Загружаем список всех известных специализаций
        self.spec_map = self._load_spec_names()
        self.current_spec_id = str(current_spec_id)

        # --- ВЕРХНЯЯ ПАНЕЛЬ: Выбор спека и управление ---
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(side="top", fill="x", padx=15, pady=(15, 10))

        lbl_spec = ctk.CTkLabel(top_bar, text="Спек:", font=("Arial", 14, "bold"))
        lbl_spec.pack(side="left", padx=(0, 5))

        # Формируем список строк для Combobox: "260 - Головорез (Outlaw)"
        combo_values = [f"{sid} - {name}" for sid, name in self.spec_map.items()]

        self.combo_specs = ctk.CTkComboBox(
            top_bar, values=combo_values, width=280,
            command=self.on_spec_changed, font=("Arial", 12)
        )
        self.combo_specs.pack(side="left", padx=5)

        # Устанавливаем текущий спек в Combobox
        self._select_combo_by_id(self.current_spec_id)

        # Кнопки сохранения и обновления
        btn_save = ctk.CTkButton(
            top_bar, text="💾 Сохранить хоткеи", command=self.save_hotkeys,
            width=150, height=30, fg_color="#10B981", hover_color="#059669", font=("Arial", 12, "bold")
        )
        btn_save.pack(side="right", padx=(10, 0))

        btn_reload = ctk.CTkButton(
            top_bar, text="🔄 Обновить", command=self.load_spells,
            width=90, height=30, fg_color="#3B82F6", hover_color="#2563EB"
        )
        btn_reload.pack(side="right")

        # --- ПРОКРУЧИВАЕМЫЙ СПИСОК ЗАКЛИНАНИЙ ---
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="Список способностей специализации")
        self.scroll_frame.pack(side="top", fill="both", expand=True, padx=15, pady=(0, 15))

        # --- НИЖНЯЯ ПАНЕЛЬ СТАТУСА ---
        self.lbl_status = ctk.CTkLabel(self, text="", font=("Arial", 12))
        self.lbl_status.pack(side="bottom", anchor="w", padx=15, pady=(0, 10))

        # Загружаем заклинания выбранного спека
        self.load_spells()

    def _load_spec_names(self):
        """Загружает названия спеков из spec_names.json или использует базовый fallback"""
        default_specs = {
            "260": "Разбойник - Головорез (Outlaw)",
            "259": "Разбойник - Ликвидация (Assassination)",
            "261": "Разбойник - Скрытность (Subtlety)",
            "577": "Охотник на демонов - Истребление (Havoc)",
            "581": "Охотник на демонов - Месть (Vengeance)"
        }
        if os.path.exists(SPEC_NAMES_PATH):
            try:
                with open(SPEC_NAMES_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return {str(k): str(v) for k, v in data.items()}
            except Exception as e:
                print(f"⚠️ Ошибка чтения {SPEC_NAMES_PATH}: {e}")
        return default_specs

    def _select_combo_by_id(self, spec_id):
        """Находит строку в Combobox по ID спека и выбирает её"""
        for val in self.combo_specs._values:
            if val.startswith(str(spec_id)):
                self.combo_specs.set(val)
                return
        if self.combo_specs._values:
            self.combo_specs.set(self.combo_specs._values[0])

    def on_spec_changed(self, selected_value):
        """Срабатывает при выборе новой специализации в Combobox"""
        # Извлекаем ID из строки "260 - Головорез..."
        new_id = selected_value.split(" - ")[0].strip()
        if new_id != self.current_spec_id:
            self.current_spec_id = new_id
            print(f"🔄 Переключение на спек ID: {self.current_spec_id}")
            self.load_spells()

    def load_spells(self):
        """Чтение spells.json для текущего спека и отрисовка списка"""
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self.entry_widgets.clear()

        spells_file = os.path.join(CLASS_DATA_DIR, self.current_spec_id, "spells.json")
        self.scroll_frame.configure(label_text=f"Способности (Спек ID: {self.current_spec_id})")

        if not os.path.exists(spells_file):
            self.lbl_status.configure(
                text=f"⚠️ Файл для спека {self.current_spec_id} не найден. Сначала импортируй профиль SimC!",
                text_color="orange"
            )
            return

        try:
            with open(spells_file, "r", encoding="utf-8") as f:
                self.spells_data = json.load(f)
        except Exception as e:
            self.lbl_status.configure(text=f"❌ Ошибка чтения JSON: {e}", text_color="red")
            return

        if not self.spells_data:
            self.lbl_status.configure(text="⚠️ База спеллов пуста.", text_color="orange")
            return

        type_colors = {
            "builder": "#3B82F6",  # Синий
            "finisher": "#EF4444",  # Красный
            "cooldown": "#F59E0B",  # Оранжевый
            "buff": "#10B981",  # Зеленый
            "debuff": "#8B5CF6",  # Фиолетовый
            "general": "#6B7280"  # Серый
        }

        row_idx = 0
        for spell_id, data in sorted(self.spells_data.items()):
            name = data.get("name", spell_id)
            stype = data.get("type", "general")
            hotkey = data.get("hotkey", "")

            row_frame = ctk.CTkFrame(self.scroll_frame, fg_color="#1E293B" if row_idx % 2 == 0 else "transparent")
            row_frame.pack(fill="x", pady=2, padx=5)

            lbl_name = ctk.CTkLabel(row_frame, text=name, font=("Arial", 13, "bold"), width=220, anchor="w")
            lbl_name.pack(side="left", padx=10, pady=6)

            badge_color = type_colors.get(stype, "#6B7280")
            lbl_type = ctk.CTkLabel(
                row_frame, text=stype.upper(), font=("Arial", 10, "bold"),
                fg_color=badge_color, text_color="white", width=85, corner_radius=6
            )
            lbl_type.pack(side="left", padx=10)

            if stype in ("buff", "debuff") and hotkey is None:
                lbl_passive = ctk.CTkLabel(row_frame, text="— (Визуальный отслеживатель) —", text_color="gray",
                                           font=("Arial", 11, "italic"))
                lbl_passive.pack(side="right", padx=20)
            else:
                entry_hk = ctk.CTkEntry(
                    row_frame, width=100, placeholder_text="Кнопка...",
                    font=("Consolas", 13, "bold"), justify="center"
                )
                if hotkey:
                    entry_hk.insert(0, str(hotkey))
                entry_hk.pack(side="right", padx=15, pady=4)
                self.entry_widgets[spell_id] = entry_hk

            row_idx += 1

        self.lbl_status.configure(text=f"✅ Загружено способностей: {len(self.spells_data)}", text_color="green")

    def save_hotkeys(self):
        """Сохранение изменений в spells.json выбранного спека"""
        if not self.spells_data:
            return

        spells_file = os.path.join(CLASS_DATA_DIR, self.current_spec_id, "spells.json")
        updated_count = 0

        for spell_id, entry_widget in self.entry_widgets.items():
            new_hotkey = entry_widget.get().strip()
            if spell_id in self.spells_data:
                if self.spells_data[spell_id].get("hotkey") != new_hotkey:
                    self.spells_data[spell_id]["hotkey"] = new_hotkey
                    updated_count += 1

        try:
            with open(spells_file, "w", encoding="utf-8") as f:
                json.dump(self.spells_data, f, indent=4, ensure_ascii=False)

            self.lbl_status.configure(
                text=f"💾 Хоткеи для спека {self.current_spec_id} сохранены! (Изменено: {updated_count})",
                text_color="#10B981"
            )
            print(f"💾 [SpellEditor] База {spells_file} успешно обновлена.")
        except Exception as e:
            self.lbl_status.configure(text=f"❌ Ошибка при сохранении: {e}", text_color="red")