# vision/etalon_matcher.py

def compare_with_etalon(current_icon, etalon_icon, threshold=5.0):
    """
    Сравнивает две иконки (PIL Image).
    Возвращает True, если они похожи (готова), False — если отличаются (в кд).
    """
    if current_icon.size != etalon_icon.size:
        return False

    total_diff = 0
    pixels = 0
    for x in range(current_icon.width):
        for y in range(current_icon.height):
            r1, g1, b1 = current_icon.getpixel((x, y))
            r2, g2, b2 = etalon_icon.getpixel((x, y))
            diff = abs(r1 - r2) + abs(g1 - g2) + abs(b1 - b2)
            total_diff += diff
            pixels += 1

    avg_diff = total_diff / pixels if pixels > 0 else 0
    return avg_diff < threshold