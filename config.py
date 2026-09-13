import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Настройки Playwright
USER_DATA_DIR = BASE_DIR / "playwright_profile"
HEADLESS = False

# Переключатель ускоренного режима
FAST_MODE = True

# Настройки задержек (в секундах)
# Ускоренный режим (FAST_MODE=True): ~4-5 сек на карточку
# Безопасный режим (FAST_MODE=False): ~20-25 сек на карточку
DELAY_BETWEEN_CARDS_MEAN = 4.0 if FAST_MODE else 20.0
DELAY_BETWEEN_CARDS_STD = 1.0 if FAST_MODE else 4.0

DELAY_BEFORE_PHONE_CLICK_MEAN = 0.8 if FAST_MODE else 2.5
DELAY_BEFORE_PHONE_CLICK_STD = 0.2 if FAST_MODE else 0.8

DELAY_AFTER_PHONE_CLICK_MEAN = 0.5 if FAST_MODE else 1.5
DELAY_AFTER_PHONE_CLICK_STD = 0.1 if FAST_MODE else 0.4

# Настройки хранения
CSV_FILE_PATH = BASE_DIR / "data.csv"

# Настройки фильтрации
ONLY_WITHOUT_WEBSITE = False  # Если True, сохраняет только организации без веб-сайта
