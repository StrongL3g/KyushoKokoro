def is_ability_ready(screen, x0, y0, width, height, debug_name=""):
    """
    Определяет, готова ли способность по виду иконки.
    Возвращает True — готова, False — в кулдауне.
    """
    margin = 4
    x_start = x0 + margin
    x_end = x0 + width - margin
    y_start = y0 + margin
    y_end = y0 + height - margin

    if x_end <= x_start or y_end <= y_start:
        return False

    luminance_values = []
    saturation_values = []

    for x in range(x_start, x_end):
        for y in range(y_start, y_end):
            try:
                px = screen.getpixel((x, y))
                r, g, b = px[:3]
            except:
                continue

            # Яркость
            lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
            luminance_values.append(lum)

            # Насыщенность
            max_c = max(r, g, b)
            min_c = min(r, g, b)
            delta = max_c - min_c
            sat = delta / max_c if max_c > 0 else 0
            saturation_values.append(sat)

    if not luminance_values:
        return False

    avg_lum = sum(luminance_values) / len(luminance_values)
    avg_sat = sum(saturation_values) / len(saturation_values)

    # Пороги — настрой под свой UI!
    LUM_THRESHOLD = 40
    SAT_THRESHOLD = 0.15

    ready = (avg_lum > LUM_THRESHOLD) and (avg_sat > SAT_THRESHOLD)

    if debug_name:
        print(f"🔍 Cooldown {debug_name}: lum={avg_lum:.1f}, sat={avg_sat:.2f} → {'✅ ready' if ready else '⏳ on CD'}")

    return ready