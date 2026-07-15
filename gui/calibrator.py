import os
import json
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk, ImageGrab
import pygetwindow as gw
from config.paths import CLASS_DATA_DIR, SPEC_RESOURCES_PATH


class ProfileCalibrator(ctk.CTkToplevel):
    def __init__(self, parent, spec_id=260, profile_name="default_pc.json"):
        super().__init__(parent)
        self.spec_id = str(spec_id)
        self.profile_name = profile_name

        # Путь к папке профилей интерфейса для конкретного спека: class_data/260/ui_profiles/
        self.profiles_dir = os.path.join(CLASS_DATA_DIR, self.spec_id, "ui_profiles")
        os.makedirs(self.profiles_dir, exist_ok=True)

        self.profile_path = os.path.join(self.profiles_dir, self.profile_name)
        self.profile_data = {"profile_name": self.profile_name, "zones": {}}

        self.title(f"🗺️ Интерактивный Калибратор зон (Спек ID: {self.spec_id})")
        self.geometry("1100x800")
        self.minsize(800, 600)

        # Делаем окно модальным
        self.transient(parent)
        self.grab_set()

        # Переменные для рисования
        self.start_x = None
        self.start_y = None
        self.current_rect = None
        self.scale_factor = 1.0

        # --- ВЕРХНЯЯ ПАНЕЛЬ 1: Управление профилями экрана ---
        top_profile_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_profile_frame.pack(side="top", fill="x", padx=15, pady=(10, 5))

        lbl_prof = ctk.CTkLabel(top_profile_frame, text="🖥️ Профиль экрана:", font=("Arial", 13, "bold"))
        lbl_prof.pack(side="left", padx=(0, 5))

        # Список существующих профилей в папке спека
        existing_profiles = self.get_existing_profiles()
        self.combo_profile = ctk.CTkComboBox(
            top_profile_frame, values=existing_profiles, width=200,
            command=self.on_profile_changed
        )
        self.combo_profile.pack(side="left", padx=5)
        self.combo_profile.set(self.profile_name)

        btn_new_prof = ctk.CTkButton(
            top_profile_frame, text="➕ Новый профиль", command=self.create_new_profile_dialog,
            width=130, height=26, fg_color="#3B82F6", hover_color="#2563EB"
        )
        btn_new_prof.pack(side="left", padx=10)

        self.lbl_prof_status = ctk.CTkLabel(top_profile_frame, text="", text_color="gray", font=("Arial", 12))
        self.lbl_prof_status.pack(side="right", padx=10)

        # --- ВЕРХНЯЯ ПАНЕЛЬ 2: Управление зонами и снимок WoW ---
        top_action_frame = ctk.CTkFrame(self)
        top_action_frame.pack(side="top", fill="x", padx=15, pady=5)

        btn_capture = ctk.CTkButton(
            top_action_frame, text="📸 1. Снимок WoW", command=self.capture_wow,
            width=130, height=32, fg_color="#8B5CF6", hover_color="#7C3AED", font=("Arial", 12, "bold")
        )
        btn_capture.pack(side="left", padx=10, pady=10)

        lbl_zone = ctk.CTkLabel(top_action_frame, text="Зона для настройки:", font=("Arial", 12))
        lbl_zone.pack(side="left", padx=(10, 5))

        # Динамический список имен (ресурсы + спеллы + баффы из нашей новой базы)
        available_names = self.get_available_zone_names()
        self.combo_name = ctk.CTkComboBox(top_action_frame, values=available_names, width=280)
        self.combo_name.pack(side="left", padx=5)
        if available_names:
            self.combo_name.set(available_names[0])

        btn_save = ctk.CTkButton(
            top_action_frame, text="💾 2. Сохранить зону", command=self.save_zone,
            fg_color="#10B981", hover_color="#059669", width=150, height=32, font=("Arial", 12, "bold")
        )
        btn_save.pack(side="left", padx=15)

        btn_delete = ctk.CTkButton(
            top_action_frame, text="🗑️ Удалить", command=self.delete_zone,
            fg_color="#EF4444", hover_color="#DC2626", width=100, height=32
        )
        btn_delete.pack(side="right", padx=10)

        # --- ХОЛСТ ДЛЯ ИЗОБРАЖЕНИЯ И РАМОК ---
        self.canvas = tk.Canvas(self, cursor="cross", bg="#1E293B")
        self.canvas.pack(side="bottom", fill="both", expand=True, padx=15, pady=(5, 15))

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

        self.wow_offset_x = 0
        self.wow_offset_y = 0

        # Загружаем выбранный профиль
        self.load_profile()

    # =========================================================================
    # БЛОК УПРАВЛЕНИЯ ПРОФИЛЯМИ ЭКРАНА (ВНУТРИ СПЕКА)
    # =========================================================================
    def get_existing_profiles(self):
        """Ищет все .json файлы в папке ui_profiles текущего спека"""
        if not os.path.exists(self.profiles_dir):
            return [self.profile_name]
        files = [f for f in os.listdir(self.profiles_dir) if f.endswith(".json")]
        return files if files else [self.profile_name]

    def on_profile_changed(self, selected_profile):
        """Переключение на другой файл настроек монитора"""
        self.profile_name = selected_profile
        self.profile_path = os.path.join(self.profiles_dir, self.profile_name)
        self.load_profile()
        self.redraw_all()
        print(f"🔄 Загружен профиль экрана: {self.profile_path}")

    def create_new_profile_dialog(self):
        """Простой диалог для создания нового файла профиля (напр. laptop_1080p.json)"""
        dialog = ctk.CTkInputDialog(text="Введите имя файла (напр: laptop_1080p.json):", title="Новый профиль экрана")
        new_name = dialog.get_input()
        if new_name:
            new_name = new_name.strip()
            if not new_name.endswith(".json"):
                new_name += ".json"

            self.profile_name = new_name
            self.profile_path = os.path.join(self.profiles_dir, self.profile_name)
            self.profile_data = {"profile_name": self.profile_name, "zones": {}}

            # Сохраняем пустой профиль
            with open(self.profile_path, "w", encoding="utf-8") as f:
                json.dump(self.profile_data, f, indent=4, ensure_ascii=False)

            # Обновляем Combobox
            profiles = self.get_existing_profiles()
            self.combo_profile.configure(values=profiles)
            self.combo_profile.set(self.profile_name)
            self.redraw_all()
            self.lbl_prof_status.configure(text=f"✨ Создан: {new_name}", text_color="#10B981")

    def load_profile(self):
        """Загружает координаты зон из текущего файла профиля"""
        if os.path.exists(self.profile_path):
            try:
                with open(self.profile_path, "r", encoding="utf-8") as f:
                    self.profile_data = json.load(f)
                if "zones" not in self.profile_data:
                    self.profile_data["zones"] = {}
                count = len(self.profile_data["zones"])
                self.lbl_prof_status.configure(text=f"📂 Зон в профиле: {count}", text_color="#3B82F6")
            except Exception as e:
                print(f"⚠️ Ошибка чтения {self.profile_path}: {e}")
                self.profile_data = {"profile_name": self.profile_name, "zones": {}}
        else:
            self.profile_data = {"profile_name": self.profile_name, "zones": {}}
            self.lbl_prof_status.configure(text="Новый профиль (пустой)", text_color="orange")

    # =========================================================================
    # БЛОК ФОРМИРОВАНИЯ ИМЕН (ИЗ СПЕКОВ, РЕСУРСОВ И БАЗЫ СПЕЛЛОВ)
    # =========================================================================
    def get_available_zone_names(self):
        """Собирает полный, красивый список всех возможных зон для настройки"""
        names_set = set()

        # 1. Добавляем глобальные ресурсы игрока и цели из spec_resources.json
        if os.path.exists(SPEC_RESOURCES_PATH):
            try:
                with open(SPEC_RESOURCES_PATH, "r", encoding="utf-8") as f:
                    spec_res_map = json.load(f)
                res_list = spec_res_map.get(self.spec_id, [])
                for res_file_name in res_list:
                    res_path = os.path.join(CLASS_DATA_DIR, "resources", f"{res_file_name}.json")
                    if os.path.exists(res_path):
                        with open(res_path, "r", encoding="utf-8") as rf:
                            rcfg = json.load(rf)
                            if "variable_name" in rcfg:
                                names_set.add(rcfg["variable_name"])
            except Exception as e:
                print(f"⚠️ Ошибка чтения ресурсов спека: {e}")

        # Стандартный fallback ресурсов, если файлов нет
        names_set.update(["player_health_pct", "target_health_pct", "energy", "combo_points", "mana", "rage", "focus"])

        # 2. Подтягиваем спеллы из нашей новой базы class_data/<spec_id>/spells.json
        spells_file = os.path.join(CLASS_DATA_DIR, self.spec_id, "spells.json")
        if os.path.exists(spells_file):
            try:
                with open(spells_file, "r", encoding="utf-8") as f:
                    spells = json.load(f)
                    for key, data in spells.items():
                        stype = data.get("type", "")
                        # Если это бафф или дебафф — имя зоны совпадает с ключом (buff_..., debuff_...)
                        if stype in ("buff", "debuff") or key.startswith("buff_") or key.startswith("debuff_"):
                            names_set.add(key)
                        else:
                            # Для активных кнопок (builders, cooldowns, finishers) создаем зону под иконку КД: cd_NAME
                            names_set.add(f"cd_{key}")
            except Exception as e:
                print(f"⚠️ Ошибка чтения {spells_file}: {e}")

        # Сортируем: сначала ресурсы, потом баффы, потом кулдауны
        sorted_names = sorted(list(names_set), key=lambda x: (
            0 if "health" in x or "energy" in x or "points" in x else
            1 if x.startswith("buff_") or x.startswith("debuff_") else 2, x
        ))
        return sorted_names

    # =========================================================================
    # БЛОК ЗАХВАТА И ОТРИСОВКИ (С НАЛОЖЕНИЕМ И ЦВЕТАМИ)
    # =========================================================================
    def capture_wow(self):
        """Ищет окно WoW, делает снимок и отображает на холсте"""
        target_windows = [w for w in gw.getWindowsWithTitle("World of Warcraft") if w.visible]
        if not target_windows:
            print("❌ Окно WoW не найдено! Запустите игру.")
            return

        win = target_windows[0]
        self.wow_offset_x, self.wow_offset_y = win.left, win.top

        screen = ImageGrab.grab(bbox=(win.left, win.top, win.left + win.width, win.top + win.height))

        self.update_idletasks()
        canvas_w = max(self.canvas.winfo_width(), 800)
        canvas_h = max(self.canvas.winfo_height(), 600)

        self.scale_factor = min(canvas_w / win.width, canvas_h / win.height)
        new_w = int(win.width * self.scale_factor)
        new_h = int(win.height * self.scale_factor)

        screen_resized = screen.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(screen_resized)

        self.redraw_all()
        print(f"📸 Снимок WoW загружен (Масштаб экрана: {self.scale_factor:.2f})")

    def redraw_all(self):
        """Перерисовывает скриншот и накладывает цветные рамки всех сохраненных зон"""
        self.canvas.delete("all")
        if hasattr(self, "tk_image"):
            self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)

        # Отрисовка сохраненных зон
        for name, coords in self.profile_data.get("zones", {}).items():
            x0, y0, w, h = coords
            sx0 = x0 * self.scale_factor
            sy0 = y0 * self.scale_factor
            sx1 = (x0 + w) * self.scale_factor
            sy1 = (y0 + h) * self.scale_factor

            # Цветовая дифференциация
            if name.startswith("buff_") or name.startswith("debuff_"):
                color = "#10B981"  # Зеленый (Баффы)
            elif name.startswith("cd_"):
                color = "#00FFFF"  # Голубой (Иконки кулдаунов)
            else:
                color = "#F59E0B"  # Желто-оранжевый (Ресурсы игрока и цели)

            # Рисуем рамку
            self.canvas.create_rectangle(sx0, sy0, sx1, sy1, outline=color, width=2, tags="saved_zone")

            # Подложка под текст для читаемости
            self.canvas.create_rectangle(sx0, sy0 - 18, sx0 + len(name) * 7.5, sy0, fill="#000000", outline="",
                                         tags="saved_zone")
            self.canvas.create_text(
                sx0 + 4, sy0 - 9, text=name, fill=color, anchor="w",
                font=("Consolas", 10, "bold"), tags="saved_zone"
            )

    # =========================================================================
    # БЛОК СОБЫТИЙ МЫШИ И СОХРАНЕНИЯ
    # =========================================================================
    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.current_rect:
            self.canvas.delete(self.current_rect)
        self.current_rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x + 1, self.start_y + 1,
            outline="#FF00FF", width=2
        )

    def on_move_press(self, event):
        cur_x, cur_y = event.x, event.y
        self.canvas.coords(self.current_rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        self.end_x, self.end_y = event.x, event.y

    def save_zone(self):
        """Сохраняет выделенные координаты в текущий профиль"""
        zone_name = self.combo_name.get().strip()
        if not zone_name or self.start_x is None:
            print("⚠️ Выберите имя зоны и выделите область мышкой на экране!")
            return

        x0 = int(min(self.start_x, self.end_x) / self.scale_factor)
        y0 = int(min(self.start_y, self.end_y) / self.scale_factor)
        w = int(abs(self.start_x - self.end_x) / self.scale_factor)
        h = int(abs(self.start_y - self.end_y) / self.scale_factor)

        self.profile_data["zones"][zone_name] = [x0, y0, w, h]

        try:
            with open(self.profile_path, "w", encoding="utf-8") as f:
                json.dump(self.profile_data, f, indent=4, ensure_ascii=False)

            print(f"💾 Зона '{zone_name}' [X:{x0}, Y:{y0}, W:{w}, H:{h}] сохранена в {self.profile_name}!")
            self.start_x = None
            self.load_profile()
            self.redraw_all()
        except Exception as e:
            print(f"❌ Ошибка сохранения профиля: {e}")

    def delete_zone(self):
        """Удаляет выбранную в Combobox зону из профиля"""
        zone_name = self.combo_name.get().strip()
        if zone_name in self.profile_data.get("zones", {}):
            del self.profile_data["zones"][zone_name]
            with open(self.profile_path, "w", encoding="utf-8") as f:
                json.dump(self.profile_data, f, indent=4, ensure_ascii=False)
            print(f"🗑️ Зона '{zone_name}' удалена из {self.profile_name}!")
            self.load_profile()
            self.redraw_all()
        else:
            print(f"⚠️ Зона '{zone_name}' не найдена в текущем профиле.")