import time
import random
import winsound
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def sleep_gaussian(mean: float, std: float):
    """Спит случайное время по Гауссову (нормальному) распределению для имитации человека."""
    delay = random.gauss(mean, std)
    # Защита от отрицательных и слишком маленьких/больших значений
    delay = max(mean * 0.5, min(delay, mean * 1.5))
    logger.debug(f"Ожидание {delay:.2f} сек...")
    time.sleep(delay)

def alert_captcha_and_wait():
    """Сигнализирует о капче и ждет ручного решения."""
    logger.warning("!!! КАПЧА ОБНАРУЖЕНА !!! Пожалуйста, решите её в открытом окне браузера.")
    
    # Трехкратный звуковой сигнал
    for _ in range(3):
        winsound.Beep(1000, 500) # Частота 1000 Гц, длительность 500 мс
        time.sleep(0.1)
        
    input(">>> Нажмите ENTER здесь в консоли ПОСЛЕ того как решите капчу в браузере: ")
    logger.info("Продолжаем работу...")
