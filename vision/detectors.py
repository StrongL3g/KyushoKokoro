# vision/detectors.py

import json
import os
from PIL import Image

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

# === BuffDetector ===
class BuffDetector:
    """
    Детектор активности баффа по яркости иконки.
    Поддерживает бинарные (есть/нет) и таймерные (осталось X сек) бафы.
    """
    def __init__(self, buff_config, screen, wow_window_rect):
        self.config = buff_config
        self.screen = screen
        self.rect = wow_window_rect

    def read(self):
        detection = self.config["detection"]
        x0 = self.rect[0] + detection["x"]
        y0 = self.rect[1] + detection["y"]
        width = detection.get("width", 36)
        height = detection.get("height", 36)
        threshold = detection["threshold"]

        # === ОТЛАДКА: сохраняем область баффа ===
        try:
            debug_img = self.screen.crop((x0, y0, x0 + width, y0 + height))
            buff_name = self.config.get("name", "unknown_buff")
            debug_img.save(f"debug_buff_{buff_name.replace(' ', '_')}.png")
            print(f"📸 Saved debug image for '{buff_name}'")
        except Exception as e:
            print(f"⚠️ Failed to save debug image: {e}")
        # ======================================

        total_lum = 0
        count = 0
        for dx in range(width):
            for dy in range(height):
                try:
                    px = self.screen.getpixel((x0 + dx, y0 + dy))
                    lum = 0.2126 * px[0] + 0.7152 * px[1] + 0.0722 * px[2]
                    total_lum += lum
                    count += 1
                except:
                    continue

        avg_lum = total_lum / count if count > 0 else 0
        is_active = avg_lum > threshold
        print(f"🔍 Buff '{buff_name}': avg_lum={avg_lum:.1f}, threshold={threshold}, active={is_active}")
        return is_active

