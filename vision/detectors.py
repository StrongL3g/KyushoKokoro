import os
import time
from PIL import Image
from dataclasses import dataclass


# === ResourceDetector ===
class ResourceDetector:
    def __init__(self, zone_config, screen, wow_window_rect):
        if isinstance(zone_config, list):
            self.config = {"type": "horizontal_bar", "coords": zone_config, "max_value": 100.0}
        else:
            self.config = zone_config

        self.screen = screen
        self.rect = wow_window_rect

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
            real_x = self.rect[0] + pos[0]
            real_y = self.rect[1] + pos[1]
            try:
                px = self.screen.getpixel((real_x, real_y))
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
    remains: float = 0.0
    level: int = 0

    def to_dict(self):
        return {"up": self.up, "remains": self.remains, "level": self.level}


class BuffDetector:
    NOISE_THRESHOLD = 40
    MSE_MATCH_THRESHOLD = 850.0  # Чуть увеличили допуск для компенсации ГКД и бликов

    # 👑 ГЕОМЕТРИЧЕСКИЕ ОТСТУПЫ (Игнорирование рамок аддона)
    BORDER_TRIM_Y = 0.20  # Отрезать 20% сверху и снизу (рамки)
    ICON_BAR_GAP = 3  # Зазор между иконкой и полосой таймера в пикселях
    BAR_END_TRIM = 2  # Срез правого края полоски (чтобы не цеплять рамку)
    ICON_INNER_CROP = 0.15  # Срез 15% по краям иконки для сравнения MSE (игнор свечения рамки)

    def __init__(self, zone_name: str, zone_coords: list, screen, wow_window_rect, spec_id: int = 260):
        self.name = zone_name
        self.screen = screen
        self.spec_id = str(spec_id)

        self.x0 = wow_window_rect[0] + zone_coords[0]
        self.y0 = wow_window_rect[1] + zone_coords[1]
        self.width = zone_coords[2]
        self.height = zone_coords[3]

        self.icon_w = min(self.height, self.width)

        # Защита от спама в unknown_buffs (сохранять не чаще 1 раза в 5 секунд)
        self.last_unknown_save_time = 0.0
        self.save_cooldown = 5.0

        self.etalons = {}
        self._load_level_etalons()

    def _load_level_etalons(self):
        clean_name = self.name.replace("buff_", "").replace("debuff_", "")
        etalon_dir = f"class_data/{self.spec_id}/buff_etalons/{clean_name}"
        if os.path.exists(etalon_dir):
            for i in range(1, 10):
                path = f"{etalon_dir}/level_{i}.png"
                if os.path.exists(path):
                    try:
                        # Загружаем эталон и сразу вырезаем его сердцевину (без рамок)
                        img = Image.open(path).convert("RGB").resize((self.icon_w, self.height))
                        crop_margin = int(self.icon_w * self.ICON_INNER_CROP)
                        inner_img = img.crop(
                            (crop_margin, crop_margin, self.icon_w - crop_margin, self.height - crop_margin))
                        self.etalons[i] = inner_img
                    except Exception:
                        pass

    def read(self) -> BuffResult:
        try:
            # 1. Сканируем полоску времени (с учетом зазора от иконки и среза правой рамки)
            y_center = self.y0 + self.height // 2
            start_x = self.icon_w + self.ICON_BAR_GAP
            end_x = max(start_x, self.width - self.BAR_END_TRIM)
            bar_effective_width = end_x - start_x

            filled_pixels = 0
            for dx in range(start_x, end_x):
                try:
                    px = self.screen.getpixel((self.x0 + dx, y_center))
                    if max(px[:3]) > self.NOISE_THRESHOLD:
                        filled_pixels += 1
                except Exception:
                    continue

            is_up = filled_pixels >= max(2, int(bar_effective_width * 0.03))
            progress = filled_pixels / bar_effective_width if bar_effective_width > 0 else 0.0

            # 2. Оцениваем иконку слева (только сердцевину без окантовки!)
            detected_level = 0
            if is_up:
                crop_margin = int(self.icon_w * self.ICON_INNER_CROP)
                icon_crop = self.screen.crop((
                    self.x0 + crop_margin,
                    self.y0 + crop_margin,
                    self.x0 + self.icon_w - crop_margin,
                    self.y0 + self.height - crop_margin
                ))

                if self.etalons:
                    detected_level = self._detect_level_mse(icon_crop)

                # 👑 Авто-сбор с защитой от спама (не чаще 1 раза в 5 секунд)
                if not self.etalons or (self.etalons and detected_level == 0):
                    now = time.time()
                    if now - self.last_unknown_save_time > self.save_cooldown:
                        self._save_unknown_sample()
                        self.last_unknown_save_time = now

            return BuffResult(up=is_up, remains=round(progress, 3), level=detected_level)

        except Exception as e:
            return BuffResult(up=False, remains=0.0, level=0)

    def _detect_level_mse(self, icon_crop: Image.Image) -> int:
        try:
            best_level = 0
            min_mse = float('inf')
            for level, etalon in self.etalons.items():
                mse = self._calculate_mse(icon_crop, etalon)
                if mse < min_mse:
                    min_mse = mse
                    best_level = level

            if min_mse <= self.MSE_MATCH_THRESHOLD:
                return best_level
            return 0
        except Exception:
            return 0

    def _save_unknown_sample(self):
        """Сохраняет неизвестный бафф для ручной классификации (с ограничением по количеству)"""
        try:
            unknown_dir = f"class_data/{self.spec_id}/unknown_buffs"
            os.makedirs(unknown_dir, exist_ok=True)

            existing = os.listdir(unknown_dir)
            if len(existing) >= 15:
                return

            timestamp = int(time.time() * 1000)
            full_crop = self.screen.crop((self.x0, self.y0, self.x0 + self.width, self.y0 + self.height))
            full_crop.save(f"{unknown_dir}/sample_{timestamp}.png")
        except Exception:
            pass

    @staticmethod
    def _calculate_mse(img1: Image.Image, img2: Image.Image) -> float:
        i1 = img1.resize((16, 16)).getdata()
        i2 = img2.resize((16, 16)).getdata()
        err = 0.0
        for p1, p2 in zip(i1, i2):
            err += (p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2 + (p1[2] - p2[2]) ** 2
        return err / (16 * 16 * 3)