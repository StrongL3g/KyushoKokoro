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

        self.profiles_dir = os.path.join(CLASS_DATA_DIR, self.spec_id, "ui_profiles")
        os.makedirs(self.profiles_dir, exist_ok=True)

        self.profile_path = os.path.join(self.profiles_dir, self.profile_name)
        self.profile_data = {"profile_name": self.profile_name, "zones": {}}

        self.title(f"🗺️ Интерактивный Калибратор зон (Спек ID: {self.spec_id})")
        self.geometry("1150x820")
        self.minsize(850, 600)

        self.transient(parent)
        self.grab_set()

        # Переменные для рисования РАМОК
        self.start_x = None
        self.start_y = None
        self.current_rect = None
        self.scale_factor = 1.0

        # Переменные для рисования ТОЧЕК (для комбо-поинтов / рун)
        self.current_points = []  # Хранит список кликнутых точек [(x1, y1), (x2, y2)...]
        self.mode_var = ctk.StringVar(value="box")  # "box" (Рамка) или "points" (Точки)

        # --- ВЕРХНЯЯ ПАНЕЛЬ 1: Управление профилями ---
        top_profile_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_profile_frame.pack(side="top", fill="x", padx=15, pady=(10, 5))

        lbl_prof = ctk.CTkLabel(top_profile_frame, text="🖥️ Профиль экрана:", font=("Arial", 13, "bold"))
        lbl_prof.pack(side="left", padx=(0, 5))

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

        # --- ВЕРХНЯЯ ПАНЕЛЬ 2: Режимы и сохранение ---
        top_action_frame = ctk.CTkFrame(self)
        top_action_frame.pack(side="top", fill="x", padx=15, pady=5)

        btn_capture = ctk.CTkButton(
            top_action_frame, text="📸 1. Снимок WoW", command=self.capture_wow,
            width=130, height=32, fg_color="#8B5CF6", hover_color="#7C3AED", font=("Arial", 12, "bold")
        )
        btn_capture.pack(side="left", padx=10, pady=10)

        # 👑 ПЕРЕКЛЮЧАТЕЛЬ РЕЖИМА ВЫДЕЛЕНИЯ
        mode_frame = ctk.CTkFrame(top_action_frame, fg_color="#1E293B", corner_radius=6)
        mode_frame.pack(side="left", padx=10, pady=6)

        rb_box = ctk.CTkRadioButton(
            mode_frame, text="🔲 Рамка (Полоски/КД)", variable=self.mode_var, value="box",
            command=self.on_mode_changed, font=("Arial", 11, "bold")
        )
        rb_box.pack(side="left", padx=8, pady=4)

        rb_points = ctk.CTkRadioButton(
            mode_frame, text="🔴 Точки (Комбо/Руны)", variable=self.mode_var, value="points",
            command=self.on_mode_changed, font=("Arial", 11, "bold")
        )
        rb_points.pack(side="left", padx=8, pady=4)

        # Кнопка сброса кликнутых точек
        self.btn_clear_points = ctk.CTkButton(
            mode_frame, text="🔄 Сброс точек", command=self.clear_current_points,
            width=90, height=22, fg_color="gray", hover_color="darkgray"
        )
        # По умолчанию скрыта (пока включен режим рамок)

        lbl_zone = ctk.CTkLabel(top_action_frame, text="Имя зоны:", font=("Arial", 12))
        lbl_zone.pack(side="left", padx=(10, 5))

        available_names = self.get_available_zone_names()
        self.combo_name = ctk.CTkComboBox(top_action_frame, values=available_names, width=240)
        self.combo_name.pack(side="left", padx=5)
        if available_names:
            self.combo_name.set(available_names[0])

        btn_save = ctk.CTkButton(
            top_action_frame, text="💾 2. Сохранить", command=self.save_zone,
            fg_color="#10B981", hover_color="#059669", width=120, height=32, font=("Arial", 12, "bold")
        )
        btn_save.pack(side="left", padx=10)

        btn_delete = ctk.CTkButton(
            top_action_frame, text="🗑️ Удалить", command=self.delete_zone,
            fg_color="#EF4444", hover_color="#DC2626", width=90, height=32
        )
        btn_delete.pack(side="right", padx=10)

        # --- ХОЛСТ ДЛЯ ИЗОБРАЖЕНИЯ ---
        self.canvas = tk.Canvas(self, cursor="cross", bg="#1E293B")
        self.canvas.pack(side="bottom", fill="both", expand=True, padx=15, pady=(5, 15))

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

        self.wow_offset_x = 0
        self.wow_offset_y = 0

        self.load_profile()

    # =========================================================================
    # ЛОГИКА РЕЖИМОВ И ПРОФИЛЕЙ
    # =========================================================================
    def on_mode_changed(self):
        """Срабатывает при переключении между Рамкой и Точками"""
        self.clear_current_points()
        if self.mode_var.get() == "points":
            self.btn_clear_points.pack(side="left", padx=5)
            self.canvas.configure(cursor="dotbox")
            # Автоматически подставляем комбо-поинты в выпадающий список, если они есть
            for name in self.combo_name._values:
                if "points" in name or "runes" in name or "holy" in name or "chi" in name:
                    self.combo_name.set(name)
                    break
        else:
            self.btn_clear_points.pack_forget()
            self.canvas.configure(cursor="cross")

    def clear_current_points(self):
        """Сбрасывает временно кликнутые точки"""
        self.current_points.clear()
        self.start_x = None
        self.start_y = None
        if self.current_rect:
            self.canvas.delete(self.current_rect)
            self.current_rect = None
        self.redraw_all()

    def get_existing_profiles(self):
        if not os.path.exists(self.profiles_dir):
            return [self.profile_name]
        files = [f for f in os.listdir(self.profiles_dir) if f.endswith(".json")]
        return files if files else [self.profile_name]

    def on_profile_changed(self, selected_profile):
        self.profile_name = selected_profile
        self.profile_path = os.path.join(self.profiles_dir, self.profile_name)
        self.load_profile()
        self.redraw_all()

    def create_new_profile_dialog(self):
        dialog = ctk.CTkInputDialog(text="Введите имя файла (напр: laptop_1080p.json):", title="Новый профиль экрана")
        new_name = dialog.get_input()
        if new_name:
            new_name = new_name.strip()
            if not new_name.endswith(".json"):
                new_name += ".json"
            self.profile_name = new_name
            self.profile_path = os.path.join(self.profiles_dir, self.profile_name)
            self.profile_data = {"profile_name": self.profile_name, "zones": {}}
            with open(self.profile_path, "w", encoding="utf-8") as f:
                json.dump(self.profile_data, f, indent=4, ensure_ascii=False)
            profiles = self.get_existing_profiles()
            self.combo_profile.configure(values=profiles)
            self.combo_profile.set(self.profile_name)
            self.redraw_all()

    def load_profile(self):
        if os.path.exists(self.profile_path):
            try:
                with open(self.profile_path, "r", encoding="utf-8") as f:
                    self.profile_data = json.load(f)
                if "zones" not in self.profile_data:
                    self.profile_data["zones"] = {}
                count = len(self.profile_data["zones"])
                self.lbl_prof_status.configure(text=f"📂 Зон: {count}", text_color="#3B82F6")
            except Exception as e:
                self.profile_data = {"profile_name": self.profile_name, "zones": {}}
        else:
            self.profile_data = {"profile_name": self.profile_name, "zones": {}}
            self.lbl_prof_status.configure(text="Новый профиль (пустой)", text_color="orange")

    def get_available_zone_names(self):
        names_set = set()
        if os.path.exists(SPEC_RESOURCES_PATH):
            try:
                with open(SPEC_RESOURCES_PATH, "r", encoding="utf-8") as f:
                    spec_res_map = json.load(f)
                for res_file_name in spec_res_map.get(self.spec_id, []):
                    res_path = os.path.join(CLASS_DATA_DIR, "resources", f"{res_file_name}.json")
                    if os.path.exists(res_path):
                        with open(res_path, "r", encoding="utf-8") as rf:
                            rcfg = json.load(rf)
                            if "variable_name" in rcfg:
                                names_set.add(rcfg["variable_name"])
            except Exception:
                pass
        names_set.update(["player_health_pct", "target_health_pct", "energy", "combo_points", "mana", "rage", "focus"])

        spells_file = os.path.join(CLASS_DATA_DIR, self.spec_id, "spells.json")
        if os.path.exists(spells_file):
            try:
                with open(spells_file, "r", encoding="utf-8") as f:
                    spells = json.load(f)
                    for key, data in spells.items():
                        stype = data.get("type", "")
                        if stype in ("buff", "debuff") or key.startswith("buff_") or key.startswith("debuff_"):
                            names_set.add(key)
                        else:
                            names_set.add(f"cd_{key}")
            except Exception:
                pass
        return sorted(list(names_set))

    # =========================================================================
    # ЗАХВАТ И ОТРИСОВКА
    # =========================================================================
    def capture_wow(self):
        target_windows = [w for w in gw.getWindowsWithTitle("World of Warcraft") if w.visible]
        if not target_windows:
            print("❌ Окно WoW не найдено!")
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

    def redraw_all(self):
        self.canvas.delete("all")
        if hasattr(self, "tk_image"):
            self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)

        # 1. Отрисовка СОХРАНЕННЫХ зон (Из профиля)
        for name, data in self.profile_data.get("zones", {}).items():
            if isinstance(data, dict) and data.get("type") == "icon_counter":
                # Это сохраненный счетчик иконок (массив точек)
                color = "#FF00FF"  # Ярко-розовый для счетчиков
                for idx, pt in enumerate(data.get("positions", [])):
                    sx, sy = pt[0] * self.scale_factor, pt[1] * self.scale_factor
                    # Рисуем прицел
                    self.canvas.create_oval(sx - 7, sy - 7, sx + 7, sy + 7, outline=color, width=2, tags="saved_zone")
                    self.canvas.create_line(sx - 10, sy, sx + 10, sy, fill=color, width=1, tags="saved_zone")
                    self.canvas.create_line(sx, sy - 10, sx, sy + 10, fill=color, width=1, tags="saved_zone")
                    self.canvas.create_text(sx + 10, sy - 10, text=f"{name}[{idx + 1}]", fill=color,
                                            font=("Consolas", 9, "bold"), tags="saved_zone")
            else:
                # Это обычная рамка [x, y, w, h]
                x0, y0, w, h = data if isinstance(data, list) else data.get("coords", [0, 0, 0, 0])
                sx0, sy0 = x0 * self.scale_factor, y0 * self.scale_factor
                sx1, sy1 = (x0 + w) * self.scale_factor, (y0 + h) * self.scale_factor

                color = "#10B981" if name.startswith("buff_") else "#00FFFF" if name.startswith("cd_") else "#F59E0B"
                self.canvas.create_rectangle(sx0, sy0, sx1, sy1, outline=color, width=2, tags="saved_zone")
                self.canvas.create_rectangle(sx0, sy0 - 18, sx0 + len(name) * 7.5, sy0, fill="#000000", outline="",
                                             tags="saved_zone")
                self.canvas.create_text(sx0 + 4, sy0 - 9, text=name, fill=color, anchor="w",
                                        font=("Consolas", 10, "bold"), tags="saved_zone")

        # 2. Отрисовка ВРЕМЕННЫХ кликнутых точек (в процессе калибровки)
        if self.current_points:
            for idx, pt in enumerate(self.current_points):
                sx, sy = pt[0] * self.scale_factor, pt[1] * self.scale_factor
                self.canvas.create_oval(sx - 8, sy - 8, sx + 8, sy + 8, outline="red", width=2, tags="temp_point")
                self.canvas.create_text(sx, sy, text=str(idx + 1), fill="yellow", font=("Arial", 10, "bold"),
                                        tags="temp_point")

    # =========================================================================
    # СОБЫТИЯ МЫШИ (РАЗДЕЛЕНИЕ НА РАМКУ И ТОЧКИ)
    # =========================================================================
    def on_button_press(self, event):
        if self.mode_var.get() == "points":
            # Режим ТОЧЕК: просто добавляем координату клика в список!
            real_x = int(event.x / self.scale_factor)
            real_y = int(event.y / self.scale_factor)
            self.current_points.append([real_x, real_y])
            print(f"🔴 Добавлена точка иконки #{len(self.current_points)}: [X:{real_x}, Y:{real_y}]")
            self.redraw_all()
        else:
            # Режим РАМКИ: запоминаем начало прямоугольника
            self.start_x, self.start_y = event.x, event.y
            if self.current_rect:
                self.canvas.delete(self.current_rect)
            self.current_rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x + 1,
                                                             self.start_y + 1, outline="#FF00FF", width=2)

    def on_move_press(self, event):
        if self.mode_var.get() == "box" and self.start_x is not None:
            self.canvas.coords(self.current_rect, self.start_x, self.start_y, event.x, event.y)

    def on_button_release(self, event):
        if self.mode_var.get() == "box":
            self.end_x, self.end_y = event.x, event.y

    def save_zone(self):
        zone_name = self.combo_name.get().strip()
        if not zone_name:
            print("⚠️ Выберите имя зоны!")
            return

        if self.mode_var.get() == "points":
            # СОХРАНЕНИЕ СЧЕТЧИКА ИКОНОК
            if not self.current_points:
                print("⚠️ Кликните мышкой по центрам иконок на скриншоте перед сохранением!")
                return

            # Записываем в формате объекта с массивом позиций
            self.profile_data["zones"][zone_name] = {
                "type": "icon_counter",
                "positions": list(self.current_points)
            }
            print(f"💾 Счетчик '{zone_name}' сохранен! Точек: {len(self.current_points)} -> {self.current_points}")
            self.clear_current_points()
        else:
            # СОХРАНЕНИЕ ОБЫЧНОЙ РАМКИ
            if self.start_x is None:
                print("⚠️ Выделите прямоугольник на экране!")
                return
            x0 = int(min(self.start_x, self.end_x) / self.scale_factor)
            y0 = int(min(self.start_y, self.end_y) / self.scale_factor)
            w = int(abs(self.start_x - self.end_x) / self.scale_factor)
            h = int(abs(self.start_y - self.end_y) / self.scale_factor)

            self.profile_data["zones"][zone_name] = [x0, y0, w, h]
            print(f"💾 Рамка '{zone_name}' [X:{x0}, Y:{y0}, W:{w}, H:{h}] сохранена!")
            self.start_x = None

        # Пишем на диск
        try:
            with open(self.profile_path, "w", encoding="utf-8") as f:
                json.dump(self.profile_data, f, indent=4, ensure_ascii=False)
            self.load_profile()
            self.redraw_all()
        except Exception as e:
            print(f"❌ Ошибка сохранения: {e}")

    def delete_zone(self):
        zone_name = self.combo_name.get().strip()
        if zone_name in self.profile_data.get("zones", {}):
            del self.profile_data["zones"][zone_name]
            with open(self.profile_path, "w", encoding="utf-8") as f:
                json.dump(self.profile_data, f, indent=4, ensure_ascii=False)
            print(f"🗑️ Зона '{zone_name}' удалена!")
            self.load_profile()
            self.redraw_all()