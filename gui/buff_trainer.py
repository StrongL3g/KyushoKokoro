import os
import json
import customtkinter as ctk
from PIL import Image
from config.paths import CLASS_DATA_DIR


class BuffTrainerWindow(ctk.CTkToplevel):
    def __init__(self, parent, spec_id=260):
        super().__init__(parent)
        self.spec_id = str(spec_id)
        self.title(f"🧠 Трейнер баффов и классификатор иконок (Спек: {self.spec_id})")
        self.geometry("750x600")
        self.minsize(650, 450)

        self.transient(parent)
        self.grab_set()

        self.unknown_dir = os.path.join(CLASS_DATA_DIR, self.spec_id, "unknown_buffs")
        self.etalons_dir = os.path.join(CLASS_DATA_DIR, self.spec_id, "buff_etalons")
        os.makedirs(self.unknown_dir, exist_ok=True)
        os.makedirs(self.etalons_dir, exist_ok=True)

        # 1. Читаем доступные баффы из spells.json (Защита от опечаток!)
        self.available_buffs = self._load_buffs_from_spells()
        self.current_sample_path = None
        self.samples = []

        # --- ВЕРХНЯЯ ПАНЕЛЬ ---
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.pack(side="top", fill="x", padx=15, pady=15)

        self.lbl_status = ctk.CTkLabel(
            top_frame, text="Загрузка...", font=("Arial", 14, "bold"), text_color="#3B82F6"
        )
        self.lbl_status.pack(side="left")

        btn_refresh = ctk.CTkButton(
            top_frame, text="🔄 Обновить список", command=self.load_next_sample, width=130, height=30
        )
        btn_refresh.pack(side="right")

        # --- ЦЕНТРАЛЬНАЯ ПАНЕЛЬ ПРЕВЬЮ (РАЗРЕЗАННАЯ ЗОНА) ---
        preview_frame = ctk.CTkFrame(self, fg_color="#1E293B", corner_radius=10)
        preview_frame.pack(side="top", fill="both", expand=True, padx=15, pady=5)

        # Подсказка
        ctk.CTkLabel(preview_frame, text="Визуальный контроль (Как программа видит зону):",
                     font=("Arial", 12, "italic"), text_color="gray").pack(pady=(10, 5))

        images_box = ctk.CTkFrame(preview_frame, fg_color="transparent")
        images_box.pack(expand=True)

        # Блок Иконки (Слева)
        icon_box = ctk.CTkFrame(images_box, fg_color="#0F172A", corner_radius=6)
        icon_box.pack(side="left", padx=15, pady=10)
        ctk.CTkLabel(icon_box, text="🖼️ Иконка (MSE):", font=("Arial", 11, "bold"), text_color="#10B981").pack(pady=2)
        self.lbl_icon_preview = ctk.CTkLabel(icon_box, text="Нет фото", width=100, height=100)
        self.lbl_icon_preview.pack(padx=10, pady=10)

        # Блок Полоски (Справа)
        bar_box = ctk.CTkFrame(images_box, fg_color="#0F172A", corner_radius=6)
        bar_box.pack(side="left", padx=15, pady=10)
        ctk.CTkLabel(bar_box, text="📊 Полоска таймера (%):", font=("Arial", 11, "bold"), text_color="#00FFFF").pack(
            pady=2)
        self.lbl_bar_preview = ctk.CTkLabel(bar_box, text="Нет фото", width=250, height=100)
        self.lbl_bar_preview.pack(padx=10, pady=10)

        # --- НИЖНЯЯ ПАНЕЛЬ УПРАВЛЕНИЯ И СОХРАНЕНИЯ ---
        ctrl_frame = ctk.CTkFrame(self)
        ctrl_frame.pack(side="bottom", fill="x", padx=15, pady=15)

        ctk.CTkLabel(ctrl_frame, text="1. Выбери бафф:", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=10,
                                                                                          pady=10, sticky="e")

        # Выпадающий список, привязанный к spells.json!
        self.combo_names = ctk.CTkComboBox(ctrl_frame, values=self.available_buffs, width=220, font=("Arial", 12))
        self.combo_names.grid(row=0, column=1, padx=5, pady=10, sticky="w")
        if self.available_buffs:
            self.combo_names.set(self.available_buffs[0])

        ctk.CTkLabel(ctrl_frame, text="2. Уровень / Стадия:", font=("Arial", 12, "bold")).grid(row=0, column=2, padx=10,
                                                                                               pady=10, sticky="e")
        self.combo_level = ctk.CTkComboBox(ctrl_frame,
                                           values=["Уровень 1 (Default)", "Уровень 2", "Уровень 3", "Уровень 4"],
                                           width=150)
        self.combo_level.grid(row=0, column=3, padx=5, pady=10, sticky="w")
        self.combo_level.set("Уровень 1 (Default)")

        btn_save = ctk.CTkButton(
            ctrl_frame, text="💾 Сохранить эталон", command=self.save_etalon,
            fg_color="#10B981", hover_color="#059669", height=36, font=("Arial", 12, "bold")
        )
        btn_save.grid(row=1, column=1, columnspan=2, pady=(5, 10), sticky="ew")

        btn_delete = ctk.CTkButton(
            ctrl_frame, text="🗑️ Удалить / Мусор", command=self.delete_sample,
            fg_color="#EF4444", hover_color="#DC2626", width=120, height=36
        )
        btn_delete.grid(row=1, column=3, pady=(5, 10), padx=5, sticky="e")

        ctrl_frame.grid_columnconfigure(1, weight=1)

        # Загружаем первый скриншот
        self.load_next_sample()

    def _load_buffs_from_spells(self):
        """Подтягивает имена всех баффов из spells.json (Исключает ошибки в именах)"""
        spells_path = os.path.join(CLASS_DATA_DIR, self.spec_id, "spells.json")
        buff_list = []
        if os.path.exists(spells_path):
            try:
                with open(spells_path, "r", encoding="utf-8") as f:
                    spells = json.load(f)
                    for key, data in spells.items():
                        stype = data.get("type", "")
                        # Берем всё, что помечено как buff или debuff, либо имеет такой префикс
                        if stype in ("buff", "debuff") or key.startswith("buff_") or key.startswith("debuff_"):
                            name = data.get("name", key)
                            buff_list.append(f"{key} | {name}")
            except Exception as e:
                print(f"⚠️ Ошибка чтения {spells_path}: {e}")

        return sorted(buff_list) if buff_list else ["buff_roll_the_bones | Бросок костей",
                                                    "buff_slice_and_dice | Мясорубка"]

    def load_next_sample(self):
        """Загружает следующий неизвестный скриншот и разрезает его на превью"""
        self.samples = [f for f in os.listdir(self.unknown_dir) if f.endswith(".png")]

        if not self.samples:
            self.lbl_status.configure(text="✅ Нет неизвестных баффов! Все иконки обучены.", text_color="#10B981")
            self.lbl_icon_preview.configure(image="", text="Пусто")
            self.lbl_bar_preview.configure(image="", text="Пусто")
            self.current_sample_path = None
            return

        self.current_sample_path = os.path.join(self.unknown_dir, self.samples[0])
        self.lbl_status.configure(text=f"Неизвестных семплов: {len(self.samples)}", text_color="orange")

        try:
            full_img = Image.open(self.current_sample_path).convert("RGB")
            w, h = full_img.size

            # 👑 РЕЗКА ГЕОМЕТРИИ: Иконка слева (h x h), Полоска справа (остальное)
            icon_w = min(w, h)
            icon_img = full_img.crop((0, 0, icon_w, h))
            bar_img = full_img.crop((icon_w, 0, w, h)) if w > icon_w else Image.new("RGB", (100, h), (30, 30, 30))

            # Масштабируем для удобного просмотра в GUI (высота 80px)
            scale = 80 / h if h > 0 else 1
            icon_disp = icon_img.resize((int(icon_w * scale), 80), Image.Resampling.NEAREST)
            bar_disp = bar_img.resize((max(10, int((w - icon_w) * scale)), 80), Image.Resampling.NEAREST)

            self.tk_icon = ctk.CTkImage(light_image=icon_disp, dark_image=icon_disp, size=icon_disp.size)
            self.tk_bar = ctk.CTkImage(light_image=bar_disp, dark_image=bar_disp, size=bar_disp.size)

            self.lbl_icon_preview.configure(image=self.tk_icon, text="")
            self.lbl_bar_preview.configure(image=self.tk_bar, text="")
        except Exception as e:
            print(f"⚠️ Ошибка превью: {e}")
            self.delete_sample()

    def save_etalon(self):
        """Сохраняет вырезанную иконку как эталон нужного уровня"""
        if not self.current_sample_path or not os.path.exists(self.current_sample_path):
            return

        # Извлекаем системный ключ из строки вида "slice_and_dice | Мясорубка"
        raw_selection = self.combo_names.get()
        spell_key = raw_selection.split(" | ")[0].strip()
        clean_key = spell_key.replace("buff_", "").replace("debuff_", "")

        # Определяем номер уровня из комбобокса (1, 2, 3 или 4)
        level_str = self.combo_level.get()
        level_num = 1
        for num in range(1, 10):
            if f"Уровень {num}" in level_str:
                level_num = num
                break

        # Создаем папку под этот бафф: class_data/260/buff_etalons/roll_the_bones/
        target_dir = os.path.join(self.etalons_dir, clean_key)
        os.makedirs(target_dir, exist_ok=True)
        target_file = os.path.join(target_dir, f"level_{level_num}.png")

        try:
            # Открываем весь семпл, ВЫРЕЗАЕМ ТОЛЬКО ИКОНКУ (квадрат слева) и сохраняем!
            full_img = Image.open(self.current_sample_path).convert("RGB")
            icon_w = min(full_img.size[0], full_img.size[1])
            icon_crop = full_img.crop((0, 0, icon_w, full_img.size[1]))

            icon_crop.save(target_file)
            print(f"✨ Эталон сохранен: {target_file}")

            # Удаляем обработанный семпл из неизвестных и грузим следующий
            self.delete_sample()
        except Exception as e:
            print(f"❌ Ошибка сохранения эталона: {e}")

    def delete_sample(self):
        """Удаляет текущий неизвестный файл (если это мусор или ошибка выделения)"""
        if self.current_sample_path and os.path.exists(self.current_sample_path):
            try:
                os.remove(self.current_sample_path)
            except Exception:
                pass
        self.load_next_sample()