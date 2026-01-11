# config/paths.py
import os

# Базовая директория проекта
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Пути к данным
CLASS_DATA_DIR = os.path.join(BASE_DIR, "class_data")
SPEC_COLORS_PATH = os.path.join(CLASS_DATA_DIR, "spec_colors.json")
SPEC_NAMES_PATH = os.path.join(CLASS_DATA_DIR, "spec_names.json")
SPEC_RESOURCES_PATH = os.path.join(CLASS_DATA_DIR, "spec_resources.json")



