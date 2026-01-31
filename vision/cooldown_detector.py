# vision/cooldown_detector.py
from vision.etalon_matcher import compare_with_etalon

def is_ability_ready(screen, x0, y0, width, height, etalon_image=None, debug_name=""):
    """
    Определяет, готова ли способность.
    - Если есть эталон → сравнивает с ним.
    - Если нет эталона → использует fallback по яркости/насыщенности.
    """
    try:
        current_icon = screen.crop((x0, y0, x0 + width, y0 + height)).convert("RGB")
    except Exception as e:
        print(f"⚠️ Crop error: {e}")
        return True  # безопасный fallback

    if etalon_image is not None:
        # Сравнение с эталоном
        ready = compare_with_etalon(current_icon, etalon_image)
    else:
        # Fallback: анализ яркости/насыщенности
        luminance_values = []
        saturation_values = []

        for x in range(current_icon.width):
            for y in range(current_icon.height):
                r, g, b = current_icon.getpixel((x, y))
                lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
                luminance_values.append(lum)

                max_c = max(r, g, b)
                min_c = min(r, g, b)
                sat = (max_c - min_c) / max_c if max_c > 0 else 0
                saturation_values.append(sat)

        if not luminance_values:
            return True

        avg_lum = sum(luminance_values) / len(luminance_values)
        avg_sat = sum(saturation_values) / len(saturation_values)

        LUM_THRESHOLD = 80
        SAT_THRESHOLD = 0.15
        ready = (avg_lum > LUM_THRESHOLD) and (avg_sat > SAT_THRESHOLD)

    if debug_name:
        status = "✅ ready" if ready else "⏳ on CD"
        print(f"🔍 Cooldown {debug_name}: {status}")

    return ready