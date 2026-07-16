import json
import os
from dataclasses import dataclass
from typing import Optional, Tuple, Dict


# === ResourceDetector ===
class ResourceDetector:
    def __init__(self, zone_config, screen, wow_window_rect):
        # 🛡️ БРОНЕБОЙНАЯ ЗАЩИТА: Если зона сохранена старым способом (списком), делаем из неё правильный словарь
        if isinstance(zone_config, list):
            self.config = {"type": "horizontal_bar", "coords": zone_config, "max_value": 100.0}
        else:
            self.config = zone_config

        self.screen = screen
        self.rect = wow_window_rect  # (x0, y0, x1, y1) окна игры

    def read(self):
        rtype = self.config.get("type")
        if rtype == "horizontal_bar":
            return self._read_horizontal_bar()
        elif rtype == "icon_counter":
            return self._read_icon_counter()
        return 0.0

    def _read_horizontal_bar(self):
        coords = self.config.get("coords", [0, 0, 10, 10])
        x0, y0, width, height = coords

        # Смещаем координаты относительно окна игры
        real_x = self.rect[0] + x0
        real_y = self.rect[1] + y0

        max_val = float(self.config.get("max_value", 100.0))

        y_center = real_y + height // 2
        brightness = []
        for dx in range(width):
            try:
                px = self.screen.getpixel((real_x + dx, y_center))
                lum = 0.2126 * px[0] + 0.7152 * px[1] + 0.0722 * px[2]
                brightness.append(lum)
            except:
                brightness.append(0)

        if not brightness: return 0.0

        max_drop = 0
        drop_index = 0
        for i in range(1, len(brightness)):
            drop = brightness[i - 1] - brightness[i]
            if drop > max_drop:
                max_drop = drop
                drop_index = i

        fill = width if max_drop < 20 else drop_index
        return (fill / width) * max_val

    def _read_icon_counter(self):
        count = 0
        positions = self.config.get("positions", [])
        for pos in positions:
            # Смещаем координаты относительно окна игры
            real_x = self.rect[0] + pos[0]
            real_y = self.rect[1] + pos[1]
            try:
                px = self.screen.getpixel((real_x, real_y))
                # Ищем любой яркий канал (Красный, Зеленый или Синий)
                if max(px[:3]) > 75:
                    count += 1
            except Exception:
                pass
        return float(count)


# === SpecDetector ===
class SpecDetector:
    def __init__(self, spec_colors: dict, spec_names: dict):
        self.spec_colors = spec_colors
        self.spec_names = spec_names
        self.color_to_spec = {}
        for spec_id_str, rgb in self.spec_colors.items():
            r, g, b = rgb
            self.color_to_spec[(round(r, 2), round(g, 2), round(b, 2))] = int(spec_id_str)
        self.tolerance = 0.035

    def detect(self, pixel_rgb):
        if not pixel_rgb: return None, "No data"
        r, g, b = [round(c / 255.0, 2) for c in pixel_rgb]
        if (r, g, b) in self.color_to_spec:
            spec_id = self.color_to_spec[(r, g, b)]
            return spec_id, self.spec_names.get(str(spec_id), f"Spec {spec_id}")

        for (ref_r, ref_g, ref_b), spec_id in self.color_to_spec.items():
            if abs(r - ref_r) <= self.tolerance and abs(g - ref_g) <= self.tolerance and abs(
                    b - ref_b) <= self.tolerance:
                return spec_id, self.spec_names.get(str(spec_id), f"Spec {spec_id}")
        return None, "Unknown spec"


# === BuffDetector ===
@dataclass
class BuffResult:
    up: bool
    remains: float = 0.0  # Процент заполнения (от 0.0 до 1.0)

    def to_dict(self):
        return {"up": self.up, "remains": self.remains}


class BuffDetector:
    # Подняли порог, чтобы игнорировать темно-серые рамки интерфейса
    NOISE_THRESHOLD = 40

    def __init__(self, zone_name: str, zone_coords: list, screen, wow_window_rect):
        self.name = zone_name
        self.screen = screen

        # zone_coords это массив [x, y, w, h] из нашего профиля Калибратора
        # Обязательно смещаем относительно окна игры
        self.x0 = wow_window_rect[0] + zone_coords[0]
        self.y0 = wow_window_rect[1] + zone_coords[1]
        self.width = zone_coords[2]
        self.height = zone_coords[3]

    def read(self) -> BuffResult:
        try:
            # Сканируем только горизонтальную линию строго по центру (игнорируем верх/низ рамки)
            y_center = self.y0 + self.height // 2

            filled_pixels = 0
            for dx in range(self.width):
                try:
                    px = self.screen.getpixel((self.x0 + dx, y_center))
                    # Берем самый яркий канал пикселя
                    if max(px[:3]) > self.NOISE_THRESHOLD:
                        filled_pixels += 1
                except Exception:
                    continue

            # Защита от мусора: считаем бафф активным, если заполнено хотя бы 2-3 пикселя
            is_up = filled_pixels >= max(2, int(self.width * 0.02))

            # Высчитываем процент оставшегося времени
            progress = filled_pixels / self.width if self.width > 0 else 0.0

            return BuffResult(up=is_up, remains=round(progress, 3))

        except Exception as e:
            print(f"⚠️ Ошибка чтения баффа {self.name}: {e}")
            return BuffResult(up=False, remains=0.0)