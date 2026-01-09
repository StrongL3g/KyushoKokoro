# vision/detectors.py

import json
import os
from PIL import ImageDraw
from dataclasses import dataclass
from typing import Optional, Tuple, Dict


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
@dataclass
class BuffResult:
    """Результат детекции баффа"""
    up: bool
    remains: Optional[float] = None  # секунды
    progress: Optional[float] = None  # 0.0-1.0

class BuffDetector:
    """
    Финальный детектор баффов с прогресс-баром
    Оптимизирован для скорости (работа в цикле 100мс)
    """

    # Пороги
    BLACK_THRESHOLD = 30
    PROGRESS_BAR_THRESHOLD = 50

    def __init__(self, buff_config: Dict, screen, wow_window_rect: Tuple[int, int, int, int]):
        self.config = buff_config
        self.screen = screen
        self.rect = wow_window_rect
        self.name = buff_config.get("name", "unknown")
        self.type = buff_config.get("type", "binary")
        self.debug = buff_config.get("debug", False)

        # Предвычисленные координаты для скорости
        self._setup_coordinates()

    def _setup_coordinates(self):
        """Предвычисляем координаты для скорости"""
        detection = self.config["detection"]
        self.icon_x = self.rect[0] + detection["x"]
        self.icon_y = self.rect[1] + detection["y"]
        self.icon_w = detection.get("width", 20)
        self.icon_h = detection.get("height", 20)

        # Точки для проверки крестом (9 точек)
        w, h = self.icon_w, self.icon_h
        self.check_points = [
            (w // 2, h // 2),  # Центр
            (0, h // 2),  # Слева
            (w - 1, h // 2),  # Справа
            (w // 2, 0),  # Сверху
            (w // 2, h - 1),  # Снизу
            (0, 0),  # Левый верх
            (w - 1, 0),  # Правый верх
            (0, h - 1),  # Левый низ
            (w - 1, h - 1)  # Правый низ
        ]

        # Координаты прогресс-бара если есть
        if self.type == "timed" and "timer" in self.config:
            timer = self.config["timer"]
            self.bar_x = self.rect[0] + timer["x"]
            self.bar_y = self.rect[1] + timer["y"]
            self.bar_w = timer["width"]
            self.bar_h = timer["height"]
            self.max_time = timer.get("max_time", 20)
            self.direction = timer.get("direction", "right_to_left")
            self.has_bar = True
        else:
            self.has_bar = False

    def read(self) -> BuffResult:
        """Основной метод - оптимизирован для скорости"""
        try:
            # 1. Быстрая проверка активности
            if not self._is_buff_active_fast():
                return BuffResult(up=False)

            # 2. Если binary-бафф - возвращаем просто активен
            if self.type == "binary" or not self.has_bar:
                return BuffResult(up=True)

            # 3. Читаем прогресс-бар
            progress = self._read_progress_bar_fast()

            if progress is None:
                return BuffResult(up=True)  # Бафф есть, но время не определено

            # 4. Вычисляем оставшееся время
            remains = progress * self.max_time

            if self.debug:
                print(f"✅ {self.name}: {remains:.1f}с ({progress:.0%})")

            return BuffResult(up=True, remains=remains, progress=progress)

        except Exception as e:
            if self.debug:
                print(f"⚠️ {self.name}: {e}")
            return BuffResult(up=False)

    def _is_buff_active_fast(self) -> bool:
        """Сверхбыстрая проверка активности"""
        for dx, dy in self.check_points:
            try:
                px = self.screen.getpixel((self.icon_x + dx, self.icon_y + dy))
                if len(px) == 4:
                    r, g, b, _ = px
                else:
                    r, g, b = px

                if r > self.BLACK_THRESHOLD or g > self.BLACK_THRESHOLD or b > self.BLACK_THRESHOLD:
                    return True

            except Exception:
                continue

        return False

    def _read_progress_bar_fast(self) -> Optional[float]:
        """Быстрое чтение прогресс-бара"""
        # Проверяем только среднюю линию
        y = self.bar_y + self.bar_h // 2

        # Для скорости проверяем не все пиксели, а с шагом
        step = 2 if self.bar_w > 30 else 1
        filled = 0
        checked = 0

        if self.direction == "right_to_left":
            # Идем слева направо
            for x in range(0, self.bar_w, step):
                try:
                    px = self.screen.getpixel((self.bar_x + x, y))
                    if len(px) == 4:
                        r, g, b, _ = px
                    else:
                        r, g, b = px

                    brightness = 0.2126 * r + 0.7152 * g + 0.0722 * b
                    if brightness > self.PROGRESS_BAR_THRESHOLD:
                        filled += 1
                    checked += 1

                except Exception:
                    continue

            if checked == 0:
                return None

            progress = filled / checked
            return 1.0 - progress  # Инвертируем для right_to_left

        else:  # left_to_right
            # Идем справа налево
            for x in range(self.bar_w - 1, -1, -step):
                try:
                    px = self.screen.getpixel((self.bar_x + x, y))
                    if len(px) == 4:
                        r, g, b, _ = px
                    else:
                        r, g, b = px

                    brightness = 0.2126 * r + 0.7152 * g + 0.0722 * b
                    if brightness > self.PROGRESS_BAR_THRESHOLD:
                        filled += 1
                    checked += 1

                except Exception:
                    continue

            if checked == 0:
                return None

            return filled / checked

    def _read_progress_bar_accurate(self) -> Optional[float]:
        """Точное чтение прогресс-бара (для отладки)"""
        y = self.bar_y + self.bar_h // 2

        # Находим границу методом бинарного поиска
        if self.direction == "right_to_left":
            # Ищем последний заполненный пиксель слева направо
            last_filled = -1
            for x in range(self.bar_w):
                try:
                    px = self.screen.getpixel((self.bar_x + x, y))
                    if len(px) == 4:
                        r, g, b, _ = px
                    else:
                        r, g, b = px

                    brightness = 0.2126 * r + 0.7152 * g + 0.0722 * b
                    if brightness > self.PROGRESS_BAR_THRESHOLD:
                        last_filled = x
                except Exception:
                    continue

            if last_filled == -1:
                return 0.0  # Полностью пусто
            elif last_filled == self.bar_w - 1:
                return 1.0  # Полностью заполнено

            progress = (last_filled + 1) / self.bar_w
            return 1.0 - progress

        else:  # left_to_right
            # Ищем первый заполненный пиксель справа налево
            first_filled = self.bar_w
            for x in range(self.bar_w - 1, -1, -1):
                try:
                    px = self.screen.getpixel((self.bar_x + x, y))
                    if len(px) == 4:
                        r, g, b, _ = px
                    else:
                        r, g, b = px

                    brightness = 0.2126 * r + 0.7152 * g + 0.0722 * b
                    if brightness > self.PROGRESS_BAR_THRESHOLD:
                        first_filled = x
                except Exception:
                    continue

            if first_filled == self.bar_w:
                return 0.0  # Полностью пусто
            elif first_filled == 0:
                return 1.0  # Полностью заполнено

            progress = (self.bar_w - first_filled) / self.bar_w
            return progress