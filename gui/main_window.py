# gui/main_window.py

import customtkinter as ctk
import threading
import time
from PIL import Image, ImageGrab
import pygetwindow as gw
import json
import os
from pynput import keyboard
from pynput.keyboard import Key, Controller as KeyboardController

# Импорты модулей
from vision.detectors import SpecDetector
from game.player import Player
from game.target import Target
from rotation.engine import RotationEngine
from gui.calibrator import ProfileCalibrator
from gui.simc_importer import SimcImportWindow
from gui.spell_editor import SpellEditorWindow

from config.paths import SPEC_COLORS_PATH, SPEC_NAMES_PATH


def _load_json_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Failed to load {path}: {e}")
        return {}


# === CoreController ===
class CoreController:
    def __init__(self, root):
        self.root = root
        self.config_file = "config.json"
        self._load_config()

        self.root.title("KyushoKokoro - Core Controller")
        self.root.geometry("620x470")  # Немного увеличили окно для панели профилей
        self.root.resizable(False, False)

        self.monitoring = False
        self.monitor_thread = None

        # Инициализация
        spec_colors = _load_json_file(SPEC_COLORS_PATH)
        spec_names = _load_json_file(SPEC_NAMES_PATH)
        self.spec_detector = SpecDetector(spec_colors, spec_names)
        self.player = Player()
        self.target = Target()
        self._last_spec_id = None
        self._player_resource_configs = []
        self._target_resource_configs = []
        self.ui_zones = {}

        # 👑 НОВОЕ: Информационная панель спека и явный выбор профиля
        self.info_frame = ctk.CTkFrame(root, fg_color="transparent")
        self.info_frame.pack(pady=(5, 5), fill="x", padx=10)

        self.lbl_current_spec = ctk.CTkLabel(
            self.info_frame, text="Спек: Ожидание игры...",
            font=("Arial", 12, "bold"), text_color="gray"
        )
        self.lbl_current_spec.pack(side="top")

        prof_ctrl_frame = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        prof_ctrl_frame.pack(side="top", pady=2)

        ctk.CTkLabel(prof_ctrl_frame, text="Профиль экрана:", font=("Arial", 12)).pack(side="left", padx=5)

        # Выпадающий список (пока заблокирован, ждет определения спека)
        self.combo_main_profile = ctk.CTkComboBox(
            prof_ctrl_frame, values=["Нет данных"], state="disabled",
            command=self._on_main_profile_changed, width=200, font=("Arial", 12, "bold")
        )
        self.combo_main_profile.pack(side="left", padx=5)

        # GUI — кнопка старта
        self.agent_toggle = ctk.CTkButton(
            root, text="Start Agent", command=self.toggle_agent, width=140, height=36,
            fg_color="#3B82F6", hover_color="#2563EB"
        )
        self.agent_toggle.pack(pady=4)

        # GUI — 4 поля сигналов
        self.signal_a_field = ctk.CTkEntry(root, width=380, state="readonly")
        self.signal_a_field.pack(pady=1)
        self.signal_b_field = ctk.CTkEntry(root, width=380, state="readonly")
        self.signal_b_field.pack(pady=1)
        self.signal_c_field = ctk.CTkEntry(root, width=380, state="readonly")
        self.signal_c_field.pack(pady=1)
        self.signal_d_field = ctk.CTkEntry(root, width=480, state="readonly")
        self.signal_d_field.pack(pady=1)

        self._update_signal_fields("Agent idle", "Agent idle", "No spec", "No resources")

        # Клавиатура
        self.keyboard = KeyboardController()
        self.combat_action_active = False
        self.combat_action_thread = None
        self.combat_key = '1'
        self.min_interval_ms = 50
        self.max_interval_ms = 100

        # Модификаторы
        self.modifiers_pressed = {'ctrl': False, 'shift': False, 'alt': False}
        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        self.keyboard_listener.start()

        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        self.current_profile = None
        self.current_hotkeys = None

        # Кнопки инструментов
        tools_frame = ctk.CTkFrame(root, fg_color="transparent")
        tools_frame.pack(pady=10)

        self.calibrator_btn = ctk.CTkButton(
            tools_frame, text="🗺️ Калибратор зон", command=self._open_calibrator,
            width=140, height=30, fg_color="#8B5CF6", hover_color="#7C3AED"
        )
        self.calibrator_btn.grid(row=0, column=0, padx=5, pady=5)

        self.import_simc_btn = ctk.CTkButton(
            tools_frame, text="📥 Импорт SimC", command=self._open_simc_importer,
            width=140, height=30, fg_color="#8B5CF6", hover_color="#7C3AED"
        )
        self.import_simc_btn.grid(row=0, column=1, padx=5, pady=5)

        self.spell_editor_btn = ctk.CTkButton(
            tools_frame, text="⌨️ Редактор хоткеев", command=self._open_spell_editor,
            width=140, height=30, fg_color="#10B981", hover_color="#059669"
        )
        self.spell_editor_btn.grid(row=1, column=0, columnspan=2, padx=5, pady=0)

    # 👑 НОВЫЙ МЕТОД: Горячее переключение профиля прямо в Главном окне
    def _on_main_profile_changed(self, selected_profile):
        """Срабатывает, когда пользователь выбирает профиль из выпадающего списка"""
        if not self._last_spec_id:
            return

        spec_id = self._last_spec_id

        # Запоминаем выбор для будущих запусков
        active_file = f"class_data/{spec_id}/ui_profiles/active_profile.txt"
        try:
            os.makedirs(os.path.dirname(active_file), exist_ok=True)
            with open(active_file, "w", encoding="utf-8") as f:
                f.write(selected_profile)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения активного профиля: {e}")

        # Горячая подгрузка координат (без перезапуска агента!)
        ui_profile_path = f"class_data/{spec_id}/ui_profiles/{selected_profile}"
        if os.path.exists(ui_profile_path):
            try:
                with open(ui_profile_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.ui_zones = data.get("zones", {})
                print(f"🔄 Горячее переключение! Теперь используется: {selected_profile}")
            except Exception as e:
                print(f"⚠️ Ошибка чтения профиля {selected_profile}: {e}")

    def _open_spell_editor(self):
        current_spec = getattr(self, "_last_spec_id", 260) if getattr(self, "_last_spec_id", None) else 260
        SpellEditorWindow(parent=self.root, current_spec_id=current_spec)

    def _open_simc_importer(self):
        current_spec = self._last_spec_id if self._last_spec_id else 260
        SimcImportWindow(parent=self.root, spec_id=current_spec)

    def _open_calibrator(self):
        current_spec = getattr(self, "_last_spec_id", 260) if getattr(self, "_last_spec_id", None) else 260
        ProfileCalibrator(self.root, spec_id=current_spec, profile_name=self.combo_main_profile.get())

    # 👑 ОБНОВЛЕННЫЙ МЕТОД: Умная загрузка спека и подтягивание списка профилей
    def _load_spec_config(self, spec_id):
        self._last_spec_id = spec_id
        self.current_profile = None
        self.current_hotkeys = None
        self.ui_zones = {}

        try:
            # 1. Красиво выводим текущий спек в интерфейс
            spec_name = self.spec_detector.spec_names.get(str(spec_id), f"Неизвестно ({spec_id})")
            self.root.after(0, lambda: self.lbl_current_spec.configure(
                text=f"Спек: {spec_name}", text_color="#10B981"
            ))

            # 2. Ищем все доступные профили для этого спека
            profiles_dir = f"class_data/{spec_id}/ui_profiles"
            available_profiles = []
            if os.path.exists(profiles_dir):
                available_profiles = [f for f in os.listdir(profiles_dir) if f.endswith(".json")]

            if not available_profiles:
                available_profiles = ["default_pc.json"]

            # 3. Читаем прошлый выбор из памяти
            profile_name = available_profiles[0]
            active_file = os.path.join(profiles_dir, "active_profile.txt")
            if os.path.exists(active_file):
                try:
                    with open(active_file, "r", encoding="utf-8") as f:
                        saved_name = f.read().strip()
                        if saved_name in available_profiles:
                            profile_name = saved_name
                except Exception:
                    pass

            # 4. Обновляем выпадающий список (Разблокируем его и заполняем)
            def update_combo():
                self.combo_main_profile.configure(state="normal", values=available_profiles)
                self.combo_main_profile.set(profile_name)

            self.root.after(0, update_combo)

            # 5. Загружаем сами координаты
            ui_profile_path = os.path.join(profiles_dir, profile_name)
            if os.path.exists(ui_profile_path):
                with open(ui_profile_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.ui_zones = data.get("zones", {})
            else:
                print(f"⚠️ Файл профиля {ui_profile_path} не найден.")

            # 6. Логика ротации
            rotation_path = f"profiles/{spec_id}.json"
            if os.path.exists(rotation_path):
                with open(rotation_path, 'r', encoding='utf-8') as f:
                    self.current_profile = json.load(f)

            # 7. Хоткеи
            spells_path = f"class_data/{spec_id}/spells.json"
            if os.path.exists(spells_path):
                with open(spells_path, 'r', encoding='utf-8') as f:
                    spells = json.load(f)
                    self.current_hotkeys = {k: v.get("hotkey") for k, v in spells.items() if v.get("hotkey")}

            # 8. Эталоны
            self.player._cooldown_etalons = {}
            etalon_dir = f"class_data/{spec_id}/cooldowns"
            if os.path.exists(etalon_dir):
                for f in os.listdir(etalon_dir):
                    if f.endswith(".png"):
                        name = f.split(".")[0]
                        self.player._cooldown_etalons[name] = Image.open(f"{etalon_dir}/{f}").convert("RGB")

        except Exception as e:
            print(f"⚠️ Error loading config for {spec_id}: {e}")

    # ===== Системные методы (без изменений) =====
    def _is_white(self, px, tol=15):
        return px[0] >= 255 - tol and px[1] >= 255 - tol and px[2] >= 255 - tol

    def _is_black(self, px, tol=15):
        return px[0] <= tol and px[1] <= tol and px[2] <= tol

    def _is_red(self, px, tol=20):
        return px[0] >= 255 - tol and px[1] <= tol and px[2] <= tol

    def _on_closing(self):
        self._stop_combat_action()
        self.monitoring = False
        if self.combat_action_thread and self.combat_action_thread.is_alive(): self.combat_action_thread.join(timeout=1)
        if self.monitor_thread and self.monitor_thread.is_alive(): self.monitor_thread.join(timeout=1)
        if hasattr(self, 'keyboard_listener') and self.keyboard_listener.is_alive():
            self.keyboard_listener.stop()
            self.keyboard_listener.join(timeout=1)
        self.root.destroy()

    def _load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.hotkey = json.load(f).get("toggle_hotkey", "`")
            except:
                self.hotkey = "`"
        else:
            self.hotkey = "`"
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump({"toggle_hotkey": "`"}, f)

    def _on_key_press(self, key):
        try:
            key_char = key.char
        except AttributeError:
            key_char = None
        if key_char == self.hotkey:
            self.root.after(0, self.toggle_agent)
            return
        if key in (Key.ctrl, Key.ctrl_l, Key.ctrl_r):
            self.modifiers_pressed['ctrl'] = True
        elif key in (Key.shift, Key.shift_l, Key.shift_r):
            self.modifiers_pressed['shift'] = True
        elif key in (Key.alt, Key.alt_l, Key.alt_r):
            self.modifiers_pressed['alt'] = True

    def _on_key_release(self, key):
        if key in (Key.ctrl, Key.ctrl_l, Key.ctrl_r):
            self.modifiers_pressed['ctrl'] = False
        elif key in (Key.shift, Key.shift_l, Key.shift_r):
            self.modifiers_pressed['shift'] = False
        elif key in (Key.alt, Key.alt_l, Key.alt_r):
            self.modifiers_pressed['alt'] = False

    def _start_combat_action(self):
        if self.combat_action_active: return
        self.combat_action_active = True
        self.combat_action_thread = threading.Thread(target=self._rotation_action_loop, daemon=True)
        self.combat_action_thread.start()

    def _stop_combat_action(self):
        self.combat_action_active = False

    def _rotation_action_loop(self):
        while self.combat_action_active and self.monitoring:
            if any(self.modifiers_pressed.values()):
                time.sleep(0.01)
                continue
            if not self.current_profile or not self.current_hotkeys:
                time.sleep(0.1)
                continue

            engine = RotationEngine(self.current_profile)
            player_state = self.player.get_state_for_evaluation()
            target_state = self.target.get_state_for_evaluation()
            spell = engine.evaluate(player_state, target_state)

            if spell:
                action_key = self.current_hotkeys.get(spell)
                if action_key:
                    try:
                        self.keyboard.press(action_key)
                        self.keyboard.release(action_key)
                        print(f"✅ Pressed: {action_key} ({spell})")
                    except Exception as e:
                        print(f"[Action] Keyboard error: {e}")
            time.sleep(0.1)

    def _update_signal_fields(self, sig_a, sig_b, sig_c, sig_d):
        for field, text in [(self.signal_a_field, sig_a), (self.signal_b_field, sig_b),
                            (self.signal_c_field, sig_c), (self.signal_d_field, sig_d)]:
            field.configure(state="normal")
            field.delete(0, "end")
            field.insert(0, text)
            field.configure(state="readonly")

    def _safe_update(self, sig_a, sig_b, sig_c, sig_d):
        self.root.after(0, self._update_signal_fields, sig_a, sig_b, sig_c, sig_d)

    def toggle_agent(self):
        if not self.monitoring:
            self.monitoring = True
            self.agent_toggle.configure(text="Stop Agent", fg_color="#DC2626", hover_color="#B91C1C")
            self.monitor_thread = threading.Thread(target=self._agent_loop, daemon=True)
            self.monitor_thread.start()
        else:
            self.monitoring = False
            self.agent_toggle.configure(text="Start Agent", fg_color="#3B82F6", hover_color="#2563EB")
            self._update_signal_fields("Agent stopped", "Agent stopped", "Agent stopped", "Agent stopped")

    def _agent_loop(self):
        try:
            target_windows = [w for w in gw.getWindowsWithTitle("World of Warcraft") if w.visible]
            if not target_windows:
                self._safe_update("No WoW window", "No WoW", "No WoW", "No WoW")
                self._stop_agent_safely()
                return

            win = target_windows[0]
            x0, y0, x1, y1 = win.left, win.top, win.left + win.width, win.top + win.height

            if win.width < 1 or win.height < 1:
                self._safe_update("Invalid window", "Invalid", "Invalid", "Invalid")
                self._stop_agent_safely()
                return

            combat_state = False

            while self.monitoring:
                try:
                    screen = ImageGrab.grab(bbox=(x0, y0, x1, y1))
                    w, h = screen.size
                    if w == 0 or h == 0: raise ValueError("Empty capture")

                    try:
                        payload_d = screen.getpixel((2, 0))
                        active_enemies = min(round((payload_d[0] / 255.0) * 10), 10)
                        self.target.active_enemies = active_enemies
                    except Exception:
                        active_enemies = 1

                    payload_a = screen.getpixel((0, h - 1))
                    sig_a = "Signal A: window is open" if self._is_white(payload_a) else f"A: {payload_a}"

                    payload_b = screen.getpixel((0, 0))
                    if self._is_black(payload_b):
                        sig_b, new_combat = "Signal B: not combat", False
                    elif self._is_red(payload_b):
                        sig_b, new_combat = "Signal B: combat", True
                    else:
                        sig_b, new_combat = f"B: {payload_b}", False

                    payload_c = screen.getpixel((1, 0))
                    spec_id, spec_name = self.spec_detector.detect(payload_c)
                    sig_c = f"Signal C: {spec_name}"

                    if spec_id != self._last_spec_id:
                        if spec_id:
                            self._load_spec_config(spec_id)
                        else:
                            self.current_profile = None
                            self.current_hotkeys = None
                            self.ui_zones = {}

                    self.player.in_combat = new_combat
                    self.player.update_from_vision(screen, (x0, y0, x1, y1), self.ui_zones)
                    self.target.update_from_vision(screen, (x0, y0, x1, y1), self.ui_zones,
                                                   active_enemies=active_enemies)

                    all_resources = {}
                    all_resources.update(self.player.resources)
                    all_resources.update({"target_health_pct": self.target.health_pct})

                    resource_texts = []
                    for var_name, value in all_resources.items():
                        name = var_name.replace("_pct", "").replace("_", " ").title()
                        resource_texts.append(f"{name}: {value:.0f}")
                    sig_d = ", ".join(resource_texts) if resource_texts else "Signal D: Ожидание данных..."

                    if new_combat and not combat_state:
                        self._start_combat_action()
                    elif not new_combat and combat_state:
                        self._stop_combat_action()
                    combat_state = new_combat

                    self._safe_update(sig_a, sig_b, sig_c, sig_d)

                except Exception as e:
                    self._safe_update(f"Capture err", "Error", "Error", str(e)[:30])
                    break
                time.sleep(0.1)

        except Exception as e:
            self._safe_update(f"Agent failed", "Fatal", "Fatal", str(e)[:30])
        finally:
            self._stop_combat_action()
            self._stop_agent_safely()

    def _stop_agent_safely(self):
        self.monitoring = False
        self.root.after(0, lambda: self.agent_toggle.configure(text="Start Agent", fg_color="#3B82F6",
                                                               hover_color="#2563EB"))