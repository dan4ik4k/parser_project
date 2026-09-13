import logging
from playwright.sync_api import Page, TimeoutError
import config
from human_mimicry import sleep_gaussian, alert_captcha_and_wait
import re
import urllib.parse

logger = logging.getLogger(__name__)

# Домены соцсетей, мессенджеров, CRM-систем онлайн-записи и агрегаторов, которые НЕ являются официальным самостоятельным веб-сайтом компании
EXCLUDED_DOMAINS = [
    # Мессенджеры и соцсети
    'wa.me', 'whatsapp.com', 'api.whatsapp',
    't.me', 'telegram.me', 'telegram.org',
    'vk.com', 'vk.me', 'vkontakte',
    'instagram.com', 'instagr.am',
    'viber.click', 'viber.me', 'viber',
    'youtube.com', 'youtu.be',
    'ok.ru', 'odnoklassniki',
    'facebook.com', 'fb.com', 'fb.me',
    'taplink.cc', 'linktr.ee', 'mssg.me', 'hipolink.me',
    'yandex.ru', 'yandex.com', 'ya.ru', '2gis.ru', 'google.com', 'maps.google',
    'dzen.ru', 'zen.yandex.ru', 'rutube.ru',

    # Системы онлайн-записи и CRM (YClients, Dikidi, Altegio и аналоги)
    'yclients.com', 'yclients.ru', 'yclients.by', 'yclients.site', 'yclients',
    'alteg.io', 'altegio.com', 'altegio',
    'dikidi.ru', 'dikidi.net', 'dikidi.online', 'dikidi.ws', 'dikidi',
    'gbooking.ru', 'sonline.su', 'arnica.pro', 'rubitime.ru',
    'mst.link', 'reservio.com', 'calendly.com', 'fresha.com',
    'simplybook.me', 'simplybook.it', 'appointy.com',
    'bitrix24.ru', 'bitrix24.site', 'amocrm.ru', 'planfix.ru', 'planfix.com',

    # Агрегаторы и доски объявлений
    'profi.ru', 'profy.ru', 'zoon.ru', 'flamp.ru', 'yell.ru', 'avito.ru', 'blizko.ru', 'tiu.ru', 'orgpage.ru'
]

def clean_and_check_website_url(href: str) -> str:
    """Извлекает прямой URL и проверяет, что это не мессенджер/соцсеть."""
    if not href:
        return ""
    
    # Расшифровка редиректов Яндекса (например /clck/jsredir?url=http...)
    if "url=" in href:
        try:
            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            if 'url' in parsed and parsed['url']:
                href = parsed['url'][0]
        except Exception:
            pass

    if not href.startswith('http'):
        return ""

    href_lower = href.lower()
    for domain in EXCLUDED_DOMAINS:
        if domain in href_lower:
            return ""

    return href

class YandexScraper:
    def __init__(self, page: Page):
        self.page = page

    def check_for_captcha(self):
        """Проверяет наличие окна с капчей."""
        try:
            # Ищем чекбокс 'Я не робот' или фрейм капчи (селекторы примерные)
            captcha_iframe = self.page.locator("iframe[src*='showcaptcha']").first
            if captcha_iframe.is_visible(timeout=1000):
                return True
                
            checkbox = self.page.locator(".CheckboxCaptcha-Button")
            if checkbox.is_visible(timeout=1000):
                return True
        except Exception:
            pass
        return False

    def handle_captcha_if_needed(self):
        if self.check_for_captcha():
            alert_captcha_and_wait()
            self.page.wait_for_timeout(2000)

    def scroll_and_collect_links(self, search_url: str, limit: int = 50) -> list[str]:
        """Открывает поиск, скроллит левую панель и собирает ссылки на карточки."""
        logger.info(f"Открываем {search_url}")
        try:
            self.page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
        except TimeoutError:
            logger.warning(f"Таймаут открытия страницы поиска: {search_url}. Пробуем собрать уже загруженные данные...")
        except Exception as e:
            logger.error(f"Ошибка открытия поиска {search_url}: {e}")
        self.handle_captcha_if_needed()
        
        # Ждем загрузки хоть какого-то элемента панели
        try:
            self.page.wait_for_selector("a[href*='/org/'], .search-list-view__list, [class*='search-snippet']", timeout=15000)
        except TimeoutError:
            logger.warning("Панель результатов не загрузилась или изменились селекторы.")
            # Попробуем сделать скриншот или просто продолжить попытки
        
        links = set()
        scroll_attempts = 0
        max_scroll_attempts = 40
        
        # Помещаем курсор мыши над боковой панелью результатов (слева)
        self.page.mouse.move(250, 400)
        
        while len(links) < limit and scroll_attempts < max_scroll_attempts:
            # Универсальный поиск всех ссылок на организации
            # Ищем ссылки содержащие '/org/' в href или класс snippet
            candidate_locators = [
                "a[href*='/org/']",
                "a.search-snippet-view__link-overlay",
                "a[class*='search-snippet']",
                "a[class*='snippet']"
            ]
            
            found_any = False
            for sel in candidate_locators:
                items = self.page.locator(sel).all()
                if items:
                    found_any = True
                    for item in items:
                        try:
                            href = item.get_attribute("href")
                            if href and ('/org/' in href or '/maps/org/' in href):
                                full_url = f"https://yandex.ru{href}" if href.startswith('/') else href
                                links.add(full_url)
                        except Exception:
                            pass
                    break
                    
            if len(links) >= limit:
                break
                
            # Прокрутка боковой панели
            self.page.mouse.move(250, 400) # Держим мышь над левой панелью
            self.page.mouse.wheel(0, 1500)  # Крутим вниз
                
            logger.info(f"Собрано ссылок: {len(links)}. Скроллим дальше...")
            sleep_gaussian(0.8, 0.2)
            scroll_attempts += 1
            self.handle_captcha_if_needed()
            
        logger.info(f"Итого собрано уникальных ссылок: {len(links)}")
        return list(links)[:limit]

    def parse_card(self, url: str) -> dict:
        """Переходит на карточку и собирает информацию."""
        # Очистка URL от вкладок типа /reviews/, /gallery/, /features/
        # Оставляем только базовый URL до ID включительно
        clean_url = re.sub(r"(/org/[^/]+/\d+/).*", r"\1", url)
        
        logger.info(f"Открываем карточку: {clean_url}")
        try:
            self.page.goto(clean_url, wait_until="domcontentloaded", timeout=45000)
        except TimeoutError:
            logger.warning(f"Таймаут открытия карточки: {clean_url}. Продолжаем сбор информации...")
        except Exception as e:
            logger.error(f"Ошибка навигации к {clean_url}: {e}")

        self.handle_captcha_if_needed()
        
        data = {
            'source': 'yandex',
            'website_url': '',
            'yandex_url': clean_url,
            'name': '',
            'phone': '',
            'has_website': 0,
            'rating': '',
            'reviews_count': '',
            'address': ''
        }
        
        # Эмуляция чтения
        sleep_gaussian(config.DELAY_BETWEEN_CARDS_MEAN, config.DELAY_BETWEEN_CARDS_STD)
        
        try:
            # Название
            for sel in ["h1.orgpage-header-view__header", "h1[class*='title']", "h1"]:
                el = self.page.locator(sel).first
                if el.is_visible(timeout=250):
                    data['name'] = el.inner_text().strip()
                    break
                    
            # Рейтинг
            for sel in [".business-rating-badge-view__rating-text", "[class*='rating-badge-view__rating-text']", "[class*='rating-text']", "[class*='rating-value']"]:
                el = self.page.locator(sel).first
                if el.is_visible(timeout=250):
                    data['rating'] = el.inner_text().strip()
                    break

            # Количество отзывов
            for sel in [
                ".business-rating-amount-view",
                "[class*='rating-amount-view']",
                "[class*='rating-amount']",
                "[class*='rating-count']",
                "[class*='reviews-count']",
                "a[href*='/reviews/']",
                "[class*='header-rating-view']"
            ]:
                el = self.page.locator(sel).first
                if el.is_visible(timeout=250):
                    text = el.inner_text().strip()
                    numbers = re.findall(r'\d+', text.replace('\xa0', '').replace(' ', ''))
                    if numbers:
                        data['reviews_count'] = numbers[0]
                        break
                    elif text:
                        data['reviews_count'] = text
                        break

            # Fallback для количества отзывов через поиск текстов в карточке
            if not data['reviews_count']:
                try:
                    page_text = self.page.locator("body").inner_text()
                    match = re.search(r"(\d+[\d\s]*)\s*(оценок|оценки|оценка|отзывов|отзыва|отзыв)", page_text, re.IGNORECASE)
                    if match:
                        data['reviews_count'] = re.sub(r'\D', '', match.group(1))
                except Exception as e:
                    logger.debug(f"Ошибка поиска отзывов через regex: {e}")
                    
            # Адрес
            for sel in [".business-contacts-view__address-link", "[class*='address-link']", "address"]:
                el = self.page.locator(sel).first
                if el.is_visible(timeout=250):
                    data['address'] = el.inner_text().strip()
                    break
                    
            # Телефон: сначала кликаем на кнопку
            phone_btns = [
                self.page.get_by_text("Показать телефон").first,
                self.page.locator("button:has-text('Показать телефон')").first,
                self.page.locator(".card-phones-view__more").first,
                self.page.locator("[class*='phones-view__more']").first,
                self.page.locator("[class*='phones'] button").first
            ]
            for btn in phone_btns:
                if btn.is_visible(timeout=500):
                    sleep_gaussian(config.DELAY_BEFORE_PHONE_CLICK_MEAN, config.DELAY_BEFORE_PHONE_CLICK_STD)
                    try:
                        btn.click(timeout=3000)
                        sleep_gaussian(config.DELAY_AFTER_PHONE_CLICK_MEAN, config.DELAY_AFTER_PHONE_CLICK_STD)
                    except Exception:
                        pass
                    break
                    
            # Телефон: извлекаем текст по селекторах
            phone_locators = [
                self.page.locator("a[href^='tel:']").first,
                self.page.locator(".business-phone-view__number").first,
                self.page.locator("[class*='phone-view__number']").first,
                self.page.locator("[class*='phone-number']").first
            ]
            for el in phone_locators:
                if el.is_visible(timeout=250):
                    data['phone'] = el.inner_text().strip()
                    break
            
            # Телефон: если селекторы не сработали (как на скриншоте), ищем регуляркой по всему тексту
            if not data['phone']:
                try:
                    # Ищем элементы, содержащие паттерн +7 (XXX) или 8 (XXX)
                    # Используем простой regex: \+7 \(\d{3}\) \d{3}-\d{2}-\d{2}
                    page_text = self.page.locator("body").inner_text()
                    match = re.search(r"(\+7|8)\s*\(?\d{3}\)?\s*\d{3}[-\s]?\d{2}[-\s]?\d{2}", page_text)
                    if match:
                        data['phone'] = match.group(0).strip()
                except Exception as e:
                    logger.debug(f"Regex phone extraction failed: {e}")
                    
            # Сайт (с исключениями всех соцсетей, мессенджеров и мультиссылок)
            site_candidates = self.page.locator(".business-urls-view__link, [class*='urls-view__link'], a[href*='http']").all()
            for el in site_candidates:
                try:
                    if el.is_visible(timeout=250):
                        raw_href = el.get_attribute("href")
                        real_url = clean_and_check_website_url(raw_href)
                        if real_url:
                            data['has_website'] = 1
                            data['website_url'] = real_url
                            break
                except Exception:
                    pass
                    
        except TimeoutError:
            logger.warning(f"Таймаут на {url}")
        except Exception as e:
            logger.error(f"Ошибка {url}: {e}")
            
        return data
