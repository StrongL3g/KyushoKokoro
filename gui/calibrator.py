import os
import json
import time
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

        # Путь к папке профилей: class_data/260/ui_profiles/
        self.profiles_dir = os.path.join(CLASS_DATA_DIR, self.spec_id, "ui_profiles")
        os.makedirs(self.profiles_dir, exist_ok=True)

        self.profile_path = os.path.join(self.profiles_dir, self.profile_name)
        self.img_path = os.path.splitext(self.profile_path)[0] + ".png"  # Путь к картинке-эталону
        self.profile_data = {"profile_name": self.profile_name, "zones": {}}

        self.title(f"🗺️ Интерактивный Калибратор с Зумом (Спек ID: {self.spec_id})")
        self.geometry("1200x850")
        self.minsize(900, 650)

        self.transient(parent)
        self.grab_set()

        # Переменные изображения и масштабирования
        self.raw_screenshot = None  # Оригинальный PIL Image без масштаба
        self.base_scale = 1.0  # Масштаб, чтобы вписать в экран при 100%
        self.zoom_level = 1.0  # Множитель зума (0.5x - 3.0x)
        self.effective_scale = 1.0  # Итоговый масштаб (base_scale * zoom_level)

        # Переменные для рисования
        self.start_x = None
        self.start_y = None
        self.current_rect = None
        self.current_points = []
        self.mode_var = ctk.StringVar(value="box")

        # --- ВЕРХНЯЯ ПАНЕЛЬ 1: Профили и ЗУМ ---
        top_profile_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_profile_frame.pack(side="top", fill="x", padx=15, pady=(10, 5))

        lbl_prof = ctk.CTkLabel(top_profile_frame, text="🖥️ Профиль:", font=("Arial", 13, "bold"))
        lbl_prof.pack(side="left", padx=(0, 5))

        existing_profiles = self.get_existing_profiles()
        self.combo_profile = ctk.CTkComboBox(
            top_profile_frame, values=existing_profiles, width=180,
            command=self.on_profile_changed
        )
        self.combo_profile.pack(side="left", padx=5)
        self.combo_profile.set(self.profile_name)

        btn_new_prof = ctk.CTkButton(
            top_profile_frame, text="➕ Создать", command=self.create_new_profile_dialog,
            width=100, height=26, fg_color="#3B82F6", hover_color="#2563EB"
        )
        btn_new_prof.pack(side="left", padx=5)

        btn_del_prof = ctk.CTkButton(
            top_profile_frame, text="🗑️", command=self.delete_profile,
            width=40, height=26, fg_color="#EF4444", hover_color="#DC2626"
        )
        btn_del_prof.pack(side="left", padx=5)

        # 👑 ПАНЕЛЬ ЗУМА (ПРИБЛИЖЕНИЯ)
        zoom_frame = ctk.CTkFrame(top_profile_frame, fg_color="#1E293B", corner_radius=6)
        zoom_frame.pack(side="left", padx=20)

        ctk.CTkLabel(zoom_frame, text="🔍 Зум:", font=("Arial", 12, "bold")).pack(side="left", padx=(10, 5))

        ctk.CTkButton(zoom_frame, text="➖", width=30, height=24, command=lambda: self.change_zoom(-0.25)).pack(
            side="left", padx=2)
        self.lbl_zoom = ctk.CTkLabel(zoom_frame, text="100%", width=50, font=("Consolas", 12, "bold"))
        self.lbl_zoom.pack(side="left", padx=2)
        ctk.CTkButton(zoom_frame, text="➕", width=30, height=24, command=lambda: self.change_zoom(0.25)).pack(
            side="left", padx=2)
        ctk.CTkButton(zoom_frame, text="100%", width=50, height=24, fg_color="gray",
                      command=lambda: self.set_zoom(1.0)).pack(side="left", padx=(5, 8), pady=4)

        self.lbl_prof_status = ctk.CTkLabel(top_profile_frame, text="", text_color="gray", font=("Arial", 12))
        self.lbl_prof_status.pack(side="right", padx=10)

        # --- ВЕРХНЯЯ ПАНЕЛЬ 2: Действия и режимы ---
        top_action_frame = ctk.CTkFrame(self)
        top_action_frame.pack(side="top", fill="x", padx=15, pady=5)

        btn_capture = ctk.CTkButton(
            top_action_frame, text="📸 Снимок игры", command=self.capture_wow,
            width=120, height=32, fg_color="#8B5CF6", hover_color="#7C3AED", font=("Arial", 12, "bold")
        )
        btn_capture.pack(side="left", padx=10, pady=10)

        mode_frame = ctk.CTkFrame(top_action_frame, fg_color="#1E293B", corner_radius=6)
        mode_frame.pack(side="left", padx=10, pady=6)

        ctk.CTkRadioButton(
            mode_frame, text="🔲 Рамка", variable=self.mode_var, value="box",
            command=self.on_mode_changed, font=("Arial", 11, "bold")
        ).pack(side="left", padx=8, pady=4)

        ctk.CTkRadioButton(
            mode_frame, text="🔴 Точки", variable=self.mode_var, value="points",
            command=self.on_mode_changed, font=("Arial", 11, "bold")
        ).pack(side="left", padx=8, pady=4)

        self.btn_clear_points = ctk.CTkButton(
            mode_frame, text="🔄 Сброс", command=self.clear_current_points,
            width=70, height=22, fg_color="gray"
        )

        lbl_zone = ctk.CTkLabel(top_action_frame, text="Зона:", font=("Arial", 12))
        lbl_zone.pack(side="left", padx=(10, 5))

        available_names = self.get_available_zone_names()
        self.combo_name = ctk.CTkComboBox(
            top_action_frame,
            values=available_names,
            width=200,
            command=self.on_combo_name_changed,
        )  # ← добавили обработчик смены имени
        self.combo_name.pack(side="left", padx=5)
        if available_names:
            self.combo_name.set(available_names[0])

        # 👑 НОВОЕ: Поле ввода для максимального значения ресурса
        lbl_max = ctk.CTkLabel(
            top_action_frame, text="Макс:", font=("Arial", 12)
        )
        lbl_max.pack(side="left", padx=(5, 2))
        self.entry_max = ctk.CTkEntry(
            top_action_frame,
            width=55,
            placeholder_text="100",
            font=("Consolas", 12, "bold"),
            justify="center",
        )
        self.entry_max.insert(0, "100")
        self.entry_max.pack(side="left", padx=(0, 5))

        btn_save = ctk.CTkButton(
            top_action_frame, text="💾 Сохранить", command=self.save_zone,
            fg_color="#10B981", hover_color="#059669", width=110, height=32, font=("Arial", 12, "bold")
        )
        btn_save.pack(side="left", padx=10)

        btn_delete = ctk.CTkButton(
            top_action_frame, text="🗑️", command=self.delete_zone,
            fg_color="#EF4444", hover_color="#DC2626", width=40, height=32
        )
        btn_delete.pack(side="right", padx=10)

        # --- ХОЛСТ СО СКРОЛЛБАРАМИ (GRID LAYOUT) ---
        canvas_frame = ctk.CTkFrame(self, fg_color="transparent")
        canvas_frame.pack(side="bottom", fill="both", expand=True, padx=15, pady=(5, 15))
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(canvas_frame, cursor="cross", bg="#0F172A", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        # Полосы прокрутки для зума
        v_scroll = ctk.CTkScrollbar(canvas_frame, orientation="vertical", command=self.canvas.yview)
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll = ctk.CTkScrollbar(canvas_frame, orientation="horizontal", command=self.canvas.xview)
        h_scroll.grid(row=1, column=0, sticky="ew")

        self.canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)

        # Привязка событий мыши (с поддержкой скролла колесиком!)
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)  # Зум колесиком мыши на Windows

        self.wow_offset_x = 0
        self.wow_offset_y = 0

        # Загружаем профиль и сохраненную картинку при старте
        self.load_profile()

    def save_active_profile_choice(self):
        """Сохраняет имя выбранного профиля, чтобы бот (main_window) знал, какой загружать"""
        active_file = os.path.join(self.profiles_dir, "active_profile.txt")
        try:
            with open(active_file, "w", encoding="utf-8") as f:
                f.write(self.profile_name)
        except Exception:
            pass

    def on_profile_changed(self, selected_profile):
        self.profile_name = selected_profile
        self.profile_path = os.path.join(self.profiles_dir, self.profile_name)
        self.img_path = os.path.splitext(self.profile_path)[0] + ".png"
        self.load_profile()
        self.save_active_profile_choice()  # ← Запоминаем выбор!
        self.redraw_all()

    def delete_profile(self):
        if self.profile_name == "default_pc.json":
            print("Нельзя удалить профиль по умолчанию!")
            return

        if os.path.exists(self.profile_path): os.remove(self.profile_path)
        if os.path.exists(self.img_path): os.remove(self.img_path)

        profiles = self.get_existing_profiles()
        self.profile_name = profiles[0] if profiles else "default_pc.json"
        self.combo_profile.configure(values=profiles)
        self.combo_profile.set(self.profile_name)
        self.profile_path = os.path.join(self.profiles_dir, self.profile_name)
        self.load_profile()
        self.save_active_profile_choice()
        self.redraw_all()
        print("🗑️ Профиль удален!")

    def on_combo_name_changed(self, selected_name):
        """Автоматически подставляет типичные максимальные значения для удобства"""
        self.entry_max.delete(0, "end")
        if "energy" in selected_name or "mana" in selected_name:
            self.entry_max.insert(0, "200")
        elif "rage" in selected_name or "runic" in selected_name:
            self.entry_max.insert(0, "100")
        else:
            self.entry_max.insert(
                0, "100"
            )  # Для здоровья, баффов и КД оставляем 100

    # =========================================================================
    # БЛОК ЗУМА И ПРОКРУТКИ
    # =========================================================================
    def change_zoom(self, delta):
        self.set_zoom(self.zoom_level + delta)

    def set_zoom(self, new_level):
        self.zoom_level = max(0.5, min(3.0, round(new_level, 2)))
        self.lbl_zoom.configure(text=f"{int(self.zoom_level * 100)}%")
        self.redraw_all()

    def on_mouse_wheel(self, event):
        """Быстрый зум колесиком мыши при зажатом Ctrl или просто колесиком"""
        if event.delta > 0:
            self.change_zoom(0.15)
        else:
            self.change_zoom(-0.15)

    # =========================================================================
    # БЛОК ПРОФИЛЕЙ И ИМЕН
    # =========================================================================
    def get_existing_profiles(self):
        if not os.path.exists(self.profiles_dir):
            return [self.profile_name]
        files = [f for f in os.listdir(self.profiles_dir) if f.endswith(".json")]
        return files if files else [self.profile_name]

    def on_profile_changed(self, selected_profile):
        self.profile_name = selected_profile
        self.profile_path = os.path.join(self.profiles_dir, self.profile_name)
        self.img_path = os.path.splitext(self.profile_path)[0] + ".png"
        self.load_profile()
        print(f"🔄 Профиль переключен: {self.profile_name}")

    def create_new_profile_dialog(self):
        dialog = ctk.CTkInputDialog(text="Имя файла (напр: pc_2k.json):", title="Новый профиль")
        new_name = dialog.get_input()
        if new_name:
            new_name = new_name.strip()
            if not new_name.endswith(".json"):
                new_name += ".json"
            self.profile_name = new_name
            self.profile_path = os.path.join(self.profiles_dir, self.profile_name)
            self.img_path = os.path.splitext(self.profile_path)[0] + ".png"
            self.profile_data = {"profile_name": self.profile_name, "zones": {}}
            with open(self.profile_path, "w", encoding="utf-8") as f:
                json.dump(self.profile_data, f, indent=4, ensure_ascii=False)
            profiles = self.get_existing_profiles()
            self.combo_profile.configure(values=profiles)
            self.combo_profile.set(self.profile_name)
            self.load_profile()

    def load_profile(self):
        """Загружает JSON и автоматически ищет сохраненный скриншот-эталон (.png)"""
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
            self.lbl_prof_status.configure(text="Новый (пустой)", text_color="orange")

        # 👑 ОФФЛАЙН ЗАГРУЗКА: Если есть сохраненный скриншот этого профиля — загружаем его!
        if os.path.exists(self.img_path):
            try:
                self.raw_screenshot = Image.open(self.img_path).convert("RGB")
                print(f"🖼️ Загружен оффлайн-скриншот эталон: {self.img_path}")
                self.redraw_all()
            except Exception as e:
                print(f"⚠️ Ошибка загрузки картинки-эталона {self.img_path}: {e}")
        else:
            self.raw_screenshot = None
            self.canvas.delete("all")
            self.canvas.create_text(400, 300,
                                    text="Нажмите '📸 Снимок игры', чтобы сделать скриншот,\nили выберите профиль с сохраненным эталоном.",
                                    fill="gray", font=("Arial", 14))

    def get_available_zone_names(self):
        names_set = set()
        if os.path.exists(SPEC_RESOURCES_PATH):
            try:
                with open(SPEC_RESOURCES_PATH, "r", encoding="utf-8") as f:
                    spec_res_map = json.load(f)
                # Извлекаем имена из старых конфигов, если они еще остались
                for res_file_name in spec_res_map.get(self.spec_id, []):
                    res_path = os.path.join(CLASS_DATA_DIR, "resources", f"{res_file_name}.json")
                    if os.path.exists(res_path):
                        with open(res_path, "r", encoding="utf-8") as rf:
                            rcfg = json.load(rf)
                            if "variable_name" in rcfg:
                                names_set.add(rcfg["variable_name"])
            except Exception: pass

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
                        elif stype == "cooldown":
                            names_set.add(f"cd_{key}")
                        elif stype in ("builder", "finisher"):
                            names_set.add(f"spell_{key}") # Для обычных атак
                        else:
                            names_set.add(f"action_{key}")
            except Exception: pass
        return sorted(list(names_set))

    def on_mode_changed(self):
        self.clear_current_points()
        if self.mode_var.get() == "points":
            self.btn_clear_points.pack(side="left", padx=5)
            self.canvas.configure(cursor="dotbox")
            for name in self.combo_name._values:
                if "points" in name or "runes" in name or "chi" in name or "holy" in name:
                    self.combo_name.set(name)
                    break
        else:
            self.btn_clear_points.pack_forget()
            self.canvas.configure(cursor="cross")

    def clear_current_points(self):
        self.current_points.clear()
        self.start_x = None
        self.start_y = None
        if self.current_rect:
            self.canvas.delete(self.current_rect)
            self.current_rect = None
        self.redraw_all()

    # =========================================================================
    # ЗАХВАТ И ОТРИСОВКА С УЧЕТОМ ЗУМА
    # =========================================================================
    def capture_wow(self):
        """Делает снимок окна WoW и СОХРАНЯЕТ его как эталон рядом с JSON"""
        target_windows = [w for w in gw.getWindowsWithTitle("World of Warcraft") if w.visible]
        if not target_windows:
            print("❌ Окно WoW не найдено!")
            return
        win = target_windows[0]
        self.wow_offset_x, self.wow_offset_y = win.left, win.top

        # 👑 100% РАБОЧЕЕ РЕШЕНИЕ ДЛЯ ОДНОГО МОНИТОРА:
        self.withdraw()          # Прячем окно калибратора
        self.update_idletasks()  # Принудительно заставляем Windows очистить графический буфер
        self.update()            # Обновляем экран
        time.sleep(0.5)          # Даем ровно 500 мс игре, чтобы отрисоваться под нами

        try:
            # Захватываем чистый скриншот игры
            self.raw_screenshot = ImageGrab.grab(bbox=(win.left, win.top, win.left + win.width, win.top + win.height))

            # Сохраняем эталон на диск
            try:
                self.raw_screenshot.save(self.img_path)
                print(f"💾 Скриншот-эталон сохранен: {self.img_path}")
            except Exception as e:
                print(f"⚠️ Не удалось сохранить файл {self.img_path}: {e}")
        finally:
            # Обязательно возвращаем окно калибратора обратно на экран!
            self.deiconify()
            self.lift()

        self.zoom_level = 1.0
        self.lbl_zoom.configure(text="100%")
        self.redraw_all()

    def redraw_all(self):
        """Отрисовка изображения и рамок с точным учетом текущего зума"""
        self.canvas.delete("all")
        if not self.raw_screenshot:
            return

        self.update_idletasks()
        canvas_w = max(self.canvas.winfo_width(), 800)
        canvas_h = max(self.canvas.winfo_height(), 600)

        # Базовый масштаб при 100% зуме, чтобы влезло в окно
        self.base_scale = min(canvas_w / self.raw_screenshot.width, canvas_h / self.raw_screenshot.height)

        # Итоговый масштаб с учетом зума
        self.effective_scale = self.base_scale * self.zoom_level

        new_w = int(self.raw_screenshot.width * self.effective_scale)
        new_h = int(self.raw_screenshot.height * self.effective_scale)

        # Сообщаем холсту размеры прокручиваемой области (для скроллбаров!)
        self.canvas.configure(scrollregion=(0, 0, new_w, new_h))

        img_resized = self.raw_screenshot.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(img_resized)
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)

        # 1. Отрисовка сохраненных зон с учетом effective_scale
        for name, data in self.profile_data.get("zones", {}).items():
            if isinstance(data, dict) and data.get("type") == "icon_counter":
                color = "#FF00FF"
                for idx, pt in enumerate(data.get("positions", [])):
                    sx, sy = pt[0] * self.effective_scale, pt[1] * self.effective_scale
                    self.canvas.create_oval(sx - 8, sy - 8, sx + 8, sy + 8, outline=color, width=2)
                    self.canvas.create_line(sx - 12, sy, sx + 12, sy, fill=color, width=1)
                    self.canvas.create_line(sx, sy - 12, sx, sy + 12, fill=color, width=1)
                    self.canvas.create_text(sx + 10, sy - 10, text=f"{name}[{idx + 1}]", fill=color,
                                            font=("Consolas", 9, "bold"))
            else:
                x0, y0, w, h = data if isinstance(data, list) else data.get("coords", [0, 0, 0, 0])
                sx0, sy0 = x0 * self.effective_scale, y0 * self.effective_scale
                sx1, sy1 = (x0 + w) * self.effective_scale, (y0 + h) * self.effective_scale

                color = "#10B981" if name.startswith("buff_") else "#00FFFF" if name.startswith("cd_") else "#F59E0B"
                self.canvas.create_rectangle(sx0, sy0, sx1, sy1, outline=color, width=2)
                self.canvas.create_rectangle(sx0, sy0 - 18, sx0 + len(name) * 7.5, sy0, fill="#000000", outline="")
                self.canvas.create_text(sx0 + 4, sy0 - 9, text=name, fill=color, anchor="w",
                                        font=("Consolas", 10, "bold"))

        # 2. Отрисовка временных точек комбо/рун
        if self.current_points:
            for idx, pt in enumerate(self.current_points):
                sx, sy = pt[0] * self.effective_scale, pt[1] * self.effective_scale
                self.canvas.create_oval(sx - 8, sy - 8, sx + 8, sy + 8, outline="red", width=2)
                self.canvas.create_text(sx, sy, text=str(idx + 1), fill="yellow", font=("Arial", 10, "bold"))

    # =========================================================================
    # СОБЫТИЯ МЫШИ (С ПЕРЕВОДОМ КООРДИНАТ ЧЕРЕЗ CANVASX/CANVASY)
    # =========================================================================
    def on_button_press(self, event):
        if not self.raw_screenshot:
            return
        # 👑 СЕКРЕТ ПРОКРУТКИ: Получаем истинные координаты с учетом положения скроллбаров
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)

        if self.mode_var.get() == "points":
            real_x = int(cx / self.effective_scale)
            real_y = int(cy / self.effective_scale)
            self.current_points.append([real_x, real_y])
            self.redraw_all()
        else:
            self.start_x, self.start_y = cx, cy
            if self.current_rect:
                self.canvas.delete(self.current_rect)
            self.current_rect = self.canvas.create_rectangle(cx, cy, cx + 1, cy + 1, outline="#FF00FF", width=2)

    def on_move_press(self, event):
        if self.mode_var.get() == "box" and self.start_x is not None:
            cx = self.canvas.canvasx(event.x)
            cy = self.canvas.canvasy(event.y)
            self.canvas.coords(self.current_rect, self.start_x, self.start_y, cx, cy)

    def on_button_release(self, event):
        if self.mode_var.get() == "box":
            self.end_x = self.canvas.canvasx(event.x)
            self.end_y = self.canvas.canvasy(event.y)

    def save_zone(self):
        zone_name = self.combo_name.get().strip()
        if not zone_name:
            return

        if self.mode_var.get() == "points":
            if not self.current_points:
                return
            self.profile_data["zones"][zone_name] = {
                "type": "icon_counter",
                "positions": list(self.current_points),
            }
            print(
                f"💾 Счетчик '{zone_name}' сохранен ({len(self.current_points)} точек)!"
            )
            self.clear_current_points()
        else:
            if self.start_x is None:
                return
            x0 = int(min(self.start_x, self.end_x) / self.effective_scale)
            y0 = int(min(self.start_y, self.end_y) / self.effective_scale)
            w = int(abs(self.start_x - self.end_x) / self.effective_scale)
            h = int(abs(self.start_y - self.end_y) / self.effective_scale)

            # 👑 НОВОЕ: Разделяем сохранение на обычные рамки (КД/Баффы) и полоски ресурсов с max_value
            if (
                zone_name.startswith("cd_")
                or zone_name.startswith("buff_")
                or zone_name.startswith("debuff_")
            ):
                self.profile_data["zones"][zone_name] = [x0, y0, w, h]
            else:
                try:
                    max_val = float(self.entry_max.get().strip())
                except ValueError:
                    max_val = 100.0

                self.profile_data["zones"][zone_name] = {
                    "type": "horizontal_bar",
                    "coords": [x0, y0, w, h],
                    "max_value": max_val,
                }

            print(
                f"💾 Зона '{zone_name}' [X:{x0}, Y:{y0}, W:{w}, H:{h}] сохранена!"
            )
            self.start_x = None

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