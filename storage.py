import csv
import os
import uuid
from config import CSV_FILE_PATH, BASE_DIR

FIELDNAMES = [
    'id', 'source', 'name', 'phone', 'has_website', 
    'website_url', 'yandex_url', 'rating', 'reviews_count', 'address', 'target_result'
]

def init_csv():
    """Создает CSV файл с заголовками, если его нет, или мигрирует существующий."""
    file_exists = os.path.exists(CSV_FILE_PATH)
    if not file_exists:
        with open(CSV_FILE_PATH, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter=';')
            writer.writeheader()
    else:
        # Автоматическая миграция для добавления колонки yandex_url
        rows = []
        upgrade_needed = False
        with open(CSV_FILE_PATH, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            if reader.fieldnames and 'yandex_url' not in reader.fieldnames:
                upgrade_needed = True
                for row in reader:
                    web = row.get('website_url', '')
                    if 'yandex.ru' in web:
                        row['yandex_url'] = web
                        row['website_url'] = ''
                        row['has_website'] = '0'
                    rows.append(row)

        if upgrade_needed:
            with open(CSV_FILE_PATH, mode='w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter=';')
                writer.writeheader()
                for row in rows:
                    for field in FIELDNAMES:
                        if field not in row: row[field] = ""
                    writer.writerow(row)

def save_lead(lead_data: dict):
    """Дописывает один лид в конец CSV файла."""
    if 'id' not in lead_data:
        lead_data['id'] = str(uuid.uuid4())
        
    # Заполняем пропущенные поля пустыми строками
    for field in FIELDNAMES:
        if field not in lead_data:
            lead_data[field] = ""
            
    with open(CSV_FILE_PATH, mode='a', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter=';')
        writer.writerow(lead_data)

PARSED_URLS_FILE = BASE_DIR / "parsed_urls.txt"

def get_parsed_urls() -> set[str]:
    """Возвращает множество всех уже пройденных URL карточек."""
    urls = set()
    
    # 1. Чтение из файла истории проверенных карточек
    if PARSED_URLS_FILE.exists():
        with open(PARSED_URLS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                if url:
                    urls.add(url)

    # 2. Чтение из существующей базы data.csv
    if os.path.exists(CSV_FILE_PATH):
        with open(CSV_FILE_PATH, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                yurl = row.get('yandex_url', '').strip()
                if yurl:
                    urls.add(yurl)

    return urls

def add_parsed_url(url: str):
    """Записывает обработанный URL в память."""
    if not url:
        return
    with open(PARSED_URLS_FILE, mode='a', encoding='utf-8') as f:
        f.write(url.strip() + '\n')

def clear_parsed_urls():
    """Очищает память пройденных карточек."""
    if PARSED_URLS_FILE.exists():
        with open(PARSED_URLS_FILE, mode='w', encoding='utf-8') as f:
            f.write('')

def is_phone_exists(phone: str) -> bool:
    """Проверяет, есть ли уже такой телефон в базе (чтобы не парсить дубли)."""
    if not os.path.exists(CSV_FILE_PATH):
        return False
        
    if not phone:
        return False

    with open(CSV_FILE_PATH, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            if row.get('phone') == phone:
                return True
    return False
