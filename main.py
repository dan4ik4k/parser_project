import logging
import os
import time
from playwright.sync_api import sync_playwright
import config
import storage
from scraper_yandex import YandexScraper
from human_mimicry import sleep_gaussian

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def run_scraper(page, target_url, limit):
    scraper = YandexScraper(page)
    # Шаг 1. Сбор ссылок
    links = scraper.scroll_and_collect_links(target_url, limit=limit)
    if not links:
        logger.error("Не найдено ссылок. Возможно, изменились селекторы Яндекса.")
        return
        
    logger.info(f"Начинаем обход {len(links)} карточек...")
    
    # Шаг 2. Обход каждой карточки
    for i, url in enumerate(links, 1):
        logger.info(f"--- Карточка [{i}/{len(links)}] ---")
        try:
            lead_data = scraper.parse_card(url)
            
            # Фильтр: только организации без веб-сайтов
            if config.ONLY_WITHOUT_WEBSITE and lead_data.get('has_website') == 1:
                logger.info(f"У компании '{lead_data.get('name')}' есть сайт ({lead_data.get('website_url')}). Пропускаем по фильтру...")
                continue

            # Защита от дубликатов по телефону
            if lead_data.get('phone') and storage.is_phone_exists(lead_data['phone']):
                logger.info(f"Телефон {lead_data['phone']} уже есть в базе. Пропускаем сохранение.")
                continue
                
            storage.save_lead(lead_data)
            logger.info(f"Сохранен лид: {lead_data.get('name')} | Телефон: {lead_data.get('phone')}")
        except Exception as e:
            logger.error(f"Ошибка при обработке карточки {url}: {e}. Пропускаем...")

def mark_queue_done(index):
    queue_file = config.BASE_DIR / "queue.txt"
    if not queue_file.exists(): return
    with open(queue_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    if index < len(lines):
        lines[index] = "[DONE] " + lines[index]
    with open(queue_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)

def run_queue(page):
    queue_file = config.BASE_DIR / "queue.txt"
    if not queue_file.exists():
        logger.error("Файл queue.txt не найден! Создайте его.")
        return

    with open(queue_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    tasks = []
    for i, line in enumerate(lines):
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('[DONE]'):
            continue
            
        parts = line.split()
        url = parts[0]
        limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 50
        tasks.append({'index': i, 'url': url, 'limit': limit})

    if not tasks:
        logger.info("Нет активных задач в очереди.")
        return

    logger.info(f"Найдено задач в очереди: {len(tasks)}")
    
    for i, task in enumerate(tasks):
        logger.info(f"\n{'='*50}\nЗАПУСК ЗАДАЧИ {i+1}/{len(tasks)}: {task['url']}\n{'='*50}")
        try:
            run_scraper(page, task['url'], task['limit'])
        except Exception as e:
            logger.error(f"Ошибка при сборе данных по задаче {task['url']}: {e}")
        
        # Отмечаем как выполненную
        mark_queue_done(task['index'])
        
        # Если это не последняя задача, делаем небольшую паузу
        if i < len(tasks) - 1:
            pause_time = 30 # 30 секунд
            logger.info(f"Задача завершена. Спим {pause_time} секунд перед следующей задачей...")
            sleep_gaussian(pause_time, 5)

def main():
    logger.info("Инициализация CSV хранилища...")
    storage.init_csv()

    while True:
        print("\n=== Локальный Парсер Яндекс Карт ===")
        speed_str = "БЫСТРЫЙ (~4-5 сек/карточка)" if config.FAST_MODE else "ОБЫЧНЫЙ (~20-25 сек/карточка)"
        print(f"Режим скорости:   {speed_str}")
        print(f"Режим фильтрации: {'ТОЛЬКО БЕЗ САЙТОВ' if config.ONLY_WITHOUT_WEBSITE else 'ВСЕ ОРГАНИЗАЦИИ'}")
        print("1. Начать парсинг (одна ссылка)")
        print("2. Ручной режим (нагуливание куки)")
        print("3. Запустить очередь задач (queue.txt) - НОЧНОЙ РЕЖИМ")
        print("4. Переключить фильтр (сохранять только компании БЕЗ сайтов)")
        print("5. Переключить скорость работы (Быстрый / Обычный)")
        print("0. Выход")
        choice = input("Выберите действие (0-5): ").strip()
        
        if choice == '0':
            print("Завершение работы.")
            break
        elif choice == '4':
            config.ONLY_WITHOUT_WEBSITE = not config.ONLY_WITHOUT_WEBSITE
            print(f"\nНовый статус фильтра: {'ТОЛЬКО БЕЗ САЙТОВ' if config.ONLY_WITHOUT_WEBSITE else 'ВСЕ ОРГАНИЗАЦИИ'}")
            continue
        elif choice == '5':
            config.FAST_MODE = not config.FAST_MODE
            config.DELAY_BETWEEN_CARDS_MEAN = 4.0 if config.FAST_MODE else 20.0
            config.DELAY_BEFORE_PHONE_CLICK_MEAN = 0.8 if config.FAST_MODE else 2.5
            config.DELAY_AFTER_PHONE_CLICK_MEAN = 0.5 if config.FAST_MODE else 1.5
            print(f"\nНовый режим скорости: {'БЫСТРЫЙ (~4-5 сек/карточка)' if config.FAST_MODE else 'ОБЫЧНЫЙ (~20-25 сек/карточка)'}")
            continue
        elif choice in ['1', '2', '3']:
            logger.info(f"Запуск Playwright (Headless = {config.HEADLESS})...")
            with sync_playwright() as p:
                config.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
                
                browser = p.chromium.launch_persistent_context(
                    user_data_dir=config.USER_DATA_DIR,
                    headless=config.HEADLESS,
                    viewport={'width': 1280, 'height': 800}
                )
                
                page = browser.pages[0] if browser.pages else browser.new_page()
                
                if choice == '2':
                    logger.info("Открываем Яндекс. Залогиньтесь, попользуйтесь картами как человек, затем закройте окно браузера.")
                    page.goto("https://yandex.ru/maps")
                    try:
                        page.wait_for_event("close", timeout=0)
                    except Exception:
                        pass
                    logger.info("Профиль сохранен.")
                elif choice == '1':
                    target_url = input("Введите URL поиска Яндекс Карт (например, https://yandex.ru/maps/.../search/Детейлинг/): ").strip()
                    if not target_url:
                        logger.error("URL не введен.")
                    else:
                        limit_str = input("Сколько организаций спарсить? (по умолчанию 20): ").strip()
                        limit = int(limit_str) if limit_str.isdigit() else 20
                        run_scraper(page, target_url, limit)
                elif choice == '3':
                    run_queue(page)
            break
        else:
            logger.error("Неизвестный выбор.")

if __name__ == "__main__":
    main()
