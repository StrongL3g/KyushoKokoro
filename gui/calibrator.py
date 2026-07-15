import os
import json
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk, ImageGrab
import pygetwindow as gw


class ProfileCalibrator(ctk.CTkToplevel):
    def __init__(self, parent, profile_name="default_profile.json"):
        super().__init__(parent)
        self.title("Интерактивный Калибратор зон")
        self.geometry("900x700")

        self.profile_path = os.path.join("profiles", profile_name)
        self.profile_data = {"zones": {}}

        # Переменные для рисования рамки мышкой
        self.start_x = None
        self.start_y = None
        self.current_rect = None
        self.scale_factor = 1.0

        # Верхняя панель с кнопками
        top_frame = ctk.CTkFrame(self)
        top_frame.pack(side="top", fill="x", padx=10, pady=10)

        btn_capture = ctk.CTkButton(top_frame, text="1. Сделать снимок WoW", command=self.capture_wow)
        btn_capture.pack(side="left", padx=5)

        # ИСПРАВЛЕНИЕ 1: width=250 перенесено сюда, в конструктор CTkEntry
        self.entry_name = ctk.CTkEntry(top_frame, placeholder_text="Имя зоны (напр: player_health)", width=250)
        self.entry_name.pack(side="left", padx=5)

        btn_save_zone = ctk.CTkButton(top_frame, text="2. Сохранить выделенную зону", command=self.save_zone,
                                      fg_color="green")
        btn_save_zone.pack(side="left", padx=5)

        # Холст (Canvas) для отображения скриншота и рисования
        self.canvas = tk.Canvas(self, cursor="cross", bg="gray")
        self.canvas.pack(side="bottom", fill="both", expand=True, padx=10, pady=10)

        # Привязываем события мыши к холсту
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

        self.wow_offset_x = 0
        self.wow_offset_y = 0

    def capture_wow(self):
        """Ищет окно WoW, делает скриншот и выводит на холст"""
        target_windows = [w for w in gw.getWindowsWithTitle("World of Warcraft") if w.visible]
        if not target_windows:
            print("❌ Окно WoW не найдено!")
            return

        win = target_windows[0]
        self.wow_offset_x, self.wow_offset_y = win.left, win.top

        # Делаем скриншот
        screen = ImageGrab.grab(bbox=(win.left, win.top, win.left + win.width, win.top + win.height))

        # Заставляем Tkinter обновить геометрию окна, чтобы canvas.winfo_width() вернул реальный размер
        self.update_idletasks()

        canvas_w = max(self.canvas.winfo_width(), 800)
        canvas_h = max(self.canvas.winfo_height(), 600)

        # Масштабируем, чтобы влезло в наше окно калибратора
        self.scale_factor = min(canvas_w / win.width, canvas_h / win.height)
        new_w = int(win.width * self.scale_factor)
        new_h = int(win.height * self.scale_factor)

        screen_resized = screen.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(screen_resized)

        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)
        print("✅ Снимок загружен! Выделяй зоны мышкой.")

    def on_button_press(self, event):
        """Запоминаем точку, где нажали кнопку мыши"""
        self.start_x = event.x
        self.start_y = event.y
        if self.current_rect:
            self.canvas.delete(self.current_rect)
        # ИСПРАВЛЕНИЕ 2: используем self.start_x и self.start_y вместо self.x/self.y
        self.current_rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x + 1, self.start_y + 1,
            outline="red", width=2
        )

    def on_move_press(self, event):
        """Растягиваем рамку вслед за мышкой"""
        cur_x, cur_y = event.x, event.y
        self.canvas.coords(self.current_rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        """Сохраняем конечные координаты при отпускании мыши"""
        self.end_x, self.end_y = event.x, event.y

    def save_zone(self):
        """Переводит координаты экрана в координаты WoW и пишет в JSON"""
        zone_name = self.entry_name.get().strip()
        if not zone_name or not self.start_x:
            print("⚠️ Введи название зоны и выдели её на экране!")
            return

        # Возвращаем координаты к реальному размеру окна игры (делим на масштаб)
        x0 = int(min(self.start_x, self.end_x) / self.scale_factor)
        y0 = int(min(self.start_y, self.end_y) / self.scale_factor)
        w = int(abs(self.start_x - self.end_x) / self.scale_factor)
        h = int(abs(self.start_y - self.end_y) / self.scale_factor)

        # Сохраняем в память
        self.profile_data["zones"][zone_name] = [x0, y0, w, h]

        # Сохраняем в файл
        os.makedirs("profiles", exist_ok=True)
        with open(self.profile_path, "w", encoding="utf-8") as f:
            json.dump(self.profile_data, f, indent=4, ensure_ascii=False)

        print(f"💾 Зона '{zone_name}' [X:{x0}, Y:{y0}, W:{w}, H:{h}] сохранена в {self.profile_path}!")
        self.entry_name.delete(0, 'end')