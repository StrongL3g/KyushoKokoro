# gui/main_window.py

import customtkinter as ctk
import threading
import time
from PIL import ImageGrab
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

        self.root.title("Core Controller")
        self.root.geometry("620x240")
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

        # GUI — 4 поля
        self.agent_toggle = ctk.CTkButton(
            root, text="Start Agent", command=self.toggle_agent, width=120, height=36
        )
        self.agent_toggle.pack(pady=8)

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

        self.save_etalon_btn = ctk.CTkButton(
            root, text="Save Cooldown Etalons", command=self._save_cooldown_etalons,
            width=150, height=30
        )
        self.save_etalon_btn.pack(pady=4)

        self.calibrator_btn = ctk.CTkButton(
            root, text="Open Calibrator", command=self._open_calibrator,
            width=150, height=30, fg_color="blue"
        )
        self.calibrator_btn.pack(pady=4)

    def _open_calibrator(self):
        # Открывает окно калибратора
        calibrator_win = ProfileCalibrator(self.root, profile_name="my_pc.json")
        calibrator_win.grab_set()  # Делает окно активным

    def _save_cooldown_etalons(self):
        if not self.monitoring:
            print("⚠️ Start agent first!")
            return

        try:
            # Получаем последний скриншот (или делаем новый)
            target_windows = [w for w in gw.getWindowsWithTitle("World of Warcraft") if w.visible]
            if not target_windows:
                print("❌ No WoW window")
                return
            win = target_windows[0]
            x0, y0, x1, y1 = win.left, win.top, win.left + win.width, win.top + win.height
            screen = ImageGrab.grab(bbox=(x0, y0, x1, y1))

            spec_id = self._last_spec_id
            if not spec_id or not self._ability_cooldown_configs:
                print("❌ No spec or cooldown config")
                return

            etalon_dir = f"class_data/{spec_id}/cooldowns"
            os.makedirs(etalon_dir, exist_ok=True)

            for name, cfg in self._ability_cooldown_configs.items():
                x = x0 + cfg["x"]
                y = y0 + cfg["y"]
                w = cfg["width"]
                h = cfg["height"]
                icon = screen.crop((x, y, x + w, y + h))
                icon.save(f"{etalon_dir}/{name}.png")
                print(f"✅ Saved {name} etalon")

            print("✨ All etalons saved!")
        except Exception as e:
            print(f"⚠️ Failed to save etalons: {e}")

    def _load_spec_config(self, spec_id):

        """Загружает ВСЁ для данного спека: ресурсы, профиль, хоткеи"""
        self._last_spec_id = spec_id
        self._player_resource_configs = []
        self._target_resource_configs = []
        self.current_profile = None
        self.current_hotkeys = None

        try:
            # 1. Ресурсы
            with open("class_data/spec_resources.json", 'r', encoding='utf-8') as f:
                spec_map = json.load(f)
            resource_names = spec_map.get(str(spec_id), [])
            for name in resource_names:
                path = f"class_data/resources/{name}.json"
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        cfg = json.load(f)
                        var_name = cfg.get("variable_name", "")
                        if var_name.startswith("target_"):
                            self._target_resource_configs.append(cfg)
                        else:
                            self._player_resource_configs.append(cfg)

            # 2. Профиль ротации
            profile_path = f"profiles/{spec_id}.json"
            if os.path.exists(profile_path):
                with open(profile_path, 'r', encoding='utf-8') as f:
                    self.current_profile = json.load(f)

            # 3. Хоткеи
            hotkey_path = f"class_data/{spec_id}/hotkeys.json"
            if os.path.exists(hotkey_path):
                with open(hotkey_path, 'r', encoding='utf-8') as f:
                    self.current_hotkeys = json.load(f)

            # 4. Бафы (новое!)
            self._buff_configs = {}
            buff_path = f"class_data/{spec_id}/buffs.json"
            if os.path.exists(buff_path):
                try:
                    with open(buff_path, 'r', encoding='utf-8') as f:
                        self._buff_configs = json.load(f)
                except Exception as e:
                    print(f"⚠️ Buff config error for {spec_id}: {e}")
            else:
                self._buff_configs = {}

            # 5. Кулдауны способностей
            self._ability_cooldown_configs = {}
            cooldown_path = f"class_data/{spec_id}/ability_cooldowns.json"
            if os.path.exists(cooldown_path):
                try:
                    with open(cooldown_path, 'r', encoding='utf-8') as f:
                        self._ability_cooldown_configs = json.load(f)
                except Exception as e:
                    print(f"⚠️ Cooldown config error for {spec_id}: {e}")
            else:
                self._ability_cooldown_configs = {}

            # 6. Загрузка эталонов кулдаунов (теперь _ability_cooldown_configs доступен)
            self._cooldown_etalons = {}
            etalon_dir = f"class_data/{spec_id}/cooldowns"
            if os.path.exists(etalon_dir):
                for name in self._ability_cooldown_configs.keys():
                    path = f"{etalon_dir}/{name}.png"
                    if os.path.exists(path):
                        self._cooldown_etalons[name] = Image.open(path).convert("RGB")

        except Exception as e:
            print(f"⚠️ Error loading config for {spec_id}: {e}")

    def _is_white(self, px, tol=15):
        return px[0] >= 255 - tol and px[1] >= 255 - tol and px[2] >= 255 - tol

    def _is_black(self, px, tol=15):
        return px[0] <= tol and px[1] <= tol and px[2] <= tol

    def _is_red(self, px, tol=20):
        return px[0] >= 255 - tol and px[1] <= tol and px[2] <= tol

    def _on_closing(self):
        self._stop_combat_action()
        self.monitoring = False

        # Остановка потоков
        if self.combat_action_thread and self.combat_action_thread.is_alive():
            self.combat_action_thread.join(timeout=1)

        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1)

        if hasattr(self, 'keyboard_listener') and self.keyboard_listener.is_alive():
            self.keyboard_listener.stop()
            self.keyboard_listener.join(timeout=1)
        self.root.destroy()

    def _load_config(self):
        default_config = {"toggle_hotkey": "`"}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.hotkey = config.get("toggle_hotkey", "`")
            except Exception:
                self.hotkey = "`"
        else:
            self.hotkey = "`"
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)

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
        if self.combat_action_active:
            return
        self.combat_action_active = True
        self.combat_action_thread = threading.Thread(target=self._rotation_action_loop, daemon=True)
        self.combat_action_thread.start()

    def _stop_combat_action(self):
        self.combat_action_active = False

    def _rotation_action_loop(self):
        """Основной цикл ротации"""
        while self.combat_action_active and self.monitoring:
            if any(self.modifiers_pressed.values()):
                time.sleep(0.01)
                continue

            if not self.current_profile or not self.current_hotkeys:
                time.sleep(0.1)
                continue

            # Создаём движок (можно кэшировать, но пока просто)
            engine = RotationEngine(self.current_profile)

            # Получаем состояния
            player_state = self.player.get_state_for_evaluation()
            target_state = self.target.get_state_for_evaluation()

            # Принимаем решение
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
        for field, text in [
            (self.signal_a_field, sig_a),
            (self.signal_b_field, sig_b),
            (self.signal_c_field, sig_c),
            (self.signal_d_field, sig_d),
        ]:
            field.configure(state="normal")
            field.delete(0, "end")
            field.insert(0, text)
            field.configure(state="readonly")

    def _safe_update(self, sig_a, sig_b, sig_c, sig_d):
        self.root.after(0, self._update_signal_fields, sig_a, sig_b, sig_c, sig_d)

    def toggle_agent(self):
        if not self.monitoring:
            self.monitoring = True
            self.agent_toggle.configure(text="Stop Agent")
            self.monitor_thread = threading.Thread(target=self._agent_loop, daemon=True)
            self.monitor_thread.start()
        else:
            self.monitoring = False
            self.agent_toggle.configure(text="Start Agent")
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

            # Внутри _agent_loop, после win = target_windows[0]
            print(f"✅ WoW window: left={win.left}, top={win.top}, width={win.width}, height={win.height}")

            screen = ImageGrab.grab(bbox=(x0, y0, x1, y1))
            screen.save("wow_window.png")  # ← сохранит именно окно WoW

            if win.width < 1 or win.height < 1:
                self._safe_update("Invalid window", "Invalid", "Invalid", "Invalid")
                self._stop_agent_safely()
                return

            combat_state = False

            while self.monitoring:
                try:
                    screen = ImageGrab.grab(bbox=(x0, y0, x1, y1))
                    w, h = screen.size
                    if w == 0 or h == 0:
                        raise ValueError("Empty capture")

                    # === ОБНОВЛЕНИЕ active_enemies — ДО всего остального ===
                    try:
                        payload_d = screen.getpixel((2, 0))
                        red_value = payload_d[0] / 255.0
                        active_enemies = min(round(red_value * 10), 10)  # ← убрал max(1,...)
                        self.target.active_enemies = active_enemies
                        print(f"🎯 Active enemies: {active_enemies}")  # ← ДОБАВЬ ЭТУ СТРОКУ
                    except Exception as e:
                        print(f"⚠️ Active enemies error: {e}")
                        active_enemies = 0

                    # Signal A: готовность
                    payload_a = screen.getpixel((0, h - 1))
                    sig_a = "Signal A: window is open" if self._is_white(payload_a) else f"A: {payload_a}"

                    # Signal B: бой
                    payload_b = screen.getpixel((0, 0))
                    if self._is_black(payload_b):
                        sig_b, new_combat = "Signal B: not combat", False
                    elif self._is_red(payload_b):
                        sig_b, new_combat = "Signal B: combat", True
                    else:
                        sig_b, new_combat = f"B: {payload_b}", False

                    # Signal C: спек
                    payload_c = screen.getpixel((1, 0))
                    spec_id, spec_name = self.spec_detector.detect(payload_c)
                    sig_c = f"Signal C: {spec_name}"

                    # Обновляем конфиги ресурсов при смене спека
                    if spec_id != self._last_spec_id:
                        if spec_id:
                            self._load_spec_config(spec_id)
                        else:
                            self._player_resource_configs = []
                            self._target_resource_configs = []
                            self.current_profile = None
                            self.current_hotkeys = None

                    # Signal D: ресурсы
                    self.player.in_combat = new_combat
                    self.player.update_from_vision(
                        screen,
                        (x0, y0, x1, y1),
                        self._player_resource_configs,
                        self._buff_configs
                    )
                    # Обновление кулдаунов способностей
                    self.player.update_cooldowns_from_vision(
                        screen,
                        (x0, y0, x1, y1),
                        self._ability_cooldown_configs
                    )
                    self.target.update_from_vision(
                        screen,
                        (x0, y0, x1, y1),
                        self._target_resource_configs,
                        active_enemies=active_enemies
                    )

                    # Для GUI: объединяем ресурсы игрока и цели
                    all_resources = {}
                    all_resources.update(self.player.resources)
                    all_resources.update({"target_health_pct": self.target.health_pct})

                    resource_texts = []
                    for var_name, value in all_resources.items():
                        name = var_name.replace("_pct", "").replace("_", " ").title()
                        resource_texts.append(f"{name}: {value:.1f}")
                    sig_d = ", ".join(resource_texts) if resource_texts else "Signal D: N/A"

                    # Управление боем
                    if new_combat and not combat_state:
                        self._start_combat_action()
                    elif not new_combat and combat_state:
                        self._stop_combat_action()
                    combat_state = new_combat

                    # Обновление GUI
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
        self.root.after(0, lambda: self.agent_toggle.configure(text="Start Agent"))
