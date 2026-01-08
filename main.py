import customtkinter as ctk
import threading
import time
from PIL import ImageGrab
import pygetwindow as gw
import random
import json
import os
from pynput import keyboard
from pynput.keyboard import Key, Controller as KeyboardController


# === ResourceDetector ===
class ResourceDetector:
    def __init__(self, resource_config, screen, wow_window_rect):
        self.config = resource_config
        self.screen = screen
        self.rect = wow_window_rect  # (left, top, right, bottom)

    def read(self):
        rtype = self.config.get("type")
        if rtype == "horizontal_bar":
            return self._read_horizontal_bar()
        elif rtype == "icon_counter":
            return self._read_icon_counter()
        else:
            return 0.0

    def _read_horizontal_bar(self):
        cfg = self.config
        region = cfg["default_region"]
        x0 = self.rect[0] + region["x"]
        y0 = self.rect[1] + region["y"]
        width = region["width"]
        height = region["height"]
        max_val = cfg["max_value"]

        y_center = y0 + height // 2

        # Собираем яркость (luminance) каждого пикселя
        brightness = []
        for dx in range(width):
            try:
                px = self.screen.getpixel((x0 + dx, y_center))
                # Яркость по формуле Rec. 709
                lum = 0.2126 * px[0] + 0.7152 * px[1] + 0.0722 * px[2]
                brightness.append(lum)
            except:
                brightness.append(0)

        if not brightness:
            return 0.0

        # Находим наибольший спад яркости (от заполнения к фону)
        max_drop = 0
        drop_index = 0
        for i in range(1, len(brightness)):
            drop = brightness[i - 1] - brightness[i]
            if drop > max_drop:
                max_drop = drop
                drop_index = i

        # Если спад слишком слабый — возможно, полоска заполнена полностью
        if max_drop < 20:  # порог можно настроить
            fill = width
        else:
            fill = drop_index

        ratio = fill / width
        return ratio * max_val

    def _read_icon_counter(self):
        count = 0
        for i, pos in enumerate(self.config["icon_positions"]):
            x = self.rect[0] + pos[0]
            y = self.rect[1] + pos[1]
            try:
                px = self.screen.getpixel((x, y))
                lum = 0.2126 * px[0] + 0.7152 * px[1] + 0.0722 * px[2]
                status = "✅ active" if lum > 60 else "⚫ inactive"
                #print(f"  Icon {i + 1}: {lum:.1f} → {status}")
                if lum > 60:
                    count += 1
            except Exception as e:
                print(f"  Icon {i + 1}: ERROR {e}")
        return float(count)

# === SpecDetector ===
class SpecDetector:
    def __init__(self):
        self.spec_colors = self._load_spec_colors()
        self.spec_names = self._load_spec_names()
        self.color_to_spec = {}
        for spec_id_str, rgb in self.spec_colors.items():
            r, g, b = rgb
            key = (round(r, 2), round(g, 2), round(b, 2))
            self.color_to_spec[key] = int(spec_id_str)
        self.tolerance = 0.035

    def _load_spec_colors(self):
        path = os.path.join("class_data", "spec_colors.json")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error loading spec_colors.json: {e}")
            return {}

    def _load_spec_names(self):
        path = os.path.join("class_data", "spec_names.json")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error loading spec_names.json: {e}")
            return {}

    def detect(self, pixel_rgb):
        if not pixel_rgb:
            return None, "No data"

        r, g, b = [c / 255.0 for c in pixel_rgb]
        r, g, b = round(r, 2), round(g, 2), round(b, 2)

        if (r, g, b) in self.color_to_spec:
            spec_id = self.color_to_spec[(r, g, b)]
            name = self.spec_names.get(str(spec_id), f"Spec {spec_id}")
            return spec_id, name

        for (ref_r, ref_g, ref_b), spec_id in self.color_to_spec.items():
            if (
                abs(r - ref_r) <= self.tolerance and
                abs(g - ref_g) <= self.tolerance and
                abs(b - ref_b) <= self.tolerance
            ):
                name = self.spec_names.get(str(spec_id), f"Spec {spec_id}")
                return spec_id, name

        return None, "Unknown spec"


# === CoreController ===
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


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
        self.spec_detector = SpecDetector()
        self.game_state = {}
        self._last_spec_id = None
        self._resource_configs = []

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

    def _load_spec_config(self, spec_id):

        print(f"🔍 Loading config for spec_id={spec_id}")

        """Загружает ВСЁ для данного спека: ресурсы, профиль, хоткеи"""
        self._last_spec_id = spec_id
        self._resource_configs = []
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
                        self._resource_configs.append(json.load(f))

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

            print(f"✅ Profile loaded: {self.current_profile is not None}")
            print(f"✅ Hotkeys loaded: {self.current_hotkeys is not None}")

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
        """Основной цикл ротации — заменяет старый combat_action_loop"""
        while self.combat_action_active and self.monitoring:
            # Блокировка при модификаторах
            if any(self.modifiers_pressed.values()):
                time.sleep(0.01)
                continue

            # Проверяем профиль и хоткеи
            if not self.current_profile or not self.current_hotkeys:
                time.sleep(0.1)
                continue

            # Обходим правила по приоритету
            action_key = None
            for rule in self.current_profile.get("rotation", []):
                spell = rule["spell"]
                condition = rule["condition"]
                if self._evaluate_condition(condition):
                    action_key = self.current_hotkeys.get(spell)
                    if action_key:
                        break

            # Выполняем нажатие
            if action_key:
                try:
                    self.keyboard.press(action_key)
                    self.keyboard.release(action_key)
                    # print(f"✅ Pressed: {action_key} ({spell})")  # отладка
                except Exception as e:
                    print(f"[Action] Keyboard error: {e}")

            # Задержка между проверками (100 мс = 10 FPS)
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

    def _evaluate_condition(self, condition: str) -> bool:
        """Оценивает условие на основе self.game_state"""
        # Безопасный контекст: только то, что есть в game_state
        env = {
            "energy": self.game_state.get("energy", 0),
            "combo_points": self.game_state.get("combo_points", 0),
            "in_combat": self.game_state.get("in_combat", False),
            "player_health_pct": self.game_state.get("player_health_pct", 100),
            "target_health_pct": self.game_state.get("target_health_pct", 100),
            # Добавляй сюда новые переменные по мере расширения game_state
        }
        try:
            return eval(condition, {"__builtins__": {}}, env)
        except Exception as e:
            print(f"⚠️ Condition error: {condition} → {e}")
            return False

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
                    payload_c = screen.getpixel((2, 0))
                    spec_id, spec_name = self.spec_detector.detect(payload_c)
                    sig_c = f"Signal C: {spec_name}"

                    # Обновляем конфиги ресурсов при смене спека
                    if spec_id != self._last_spec_id:
                        if spec_id:
                            self._load_spec_config(spec_id)
                        else:
                            self._resource_configs = []
                            self.current_profile = None
                            self.current_hotkeys = None

                    # Signal D: ресурсы
                    self.game_state = {"in_combat": new_combat}
                    resource_texts = []
                    for cfg in self._resource_configs:
                        try:
                            detector = ResourceDetector(cfg, screen, (x0, y0, x1, y1))
                            value = detector.read()
                            var_name = cfg["variable_name"]
                            self.game_state[var_name] = value
                            resource_texts.append(f"{cfg['name']}: {value:.1f}")
                        except Exception as e:
                            print(f"⚠️ Resource error: {e}")
                    sig_d = ", ".join(resource_texts) if resource_texts else "Signal D: N/A"

                    # Отладка: вывод текущего состояния
                    if new_combat:
                        state_str = ", ".join(f"{k}={v:.1f}" if isinstance(v, float) else f"{k}={v}"
                                              for k, v in self.game_state.items())
                        print(f"📊 State: {state_str}")

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


if __name__ == "__main__":
    app = ctk.CTk()
    core = CoreController(app)
    app.mainloop()