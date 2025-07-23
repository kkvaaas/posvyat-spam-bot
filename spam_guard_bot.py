import telebot
from telebot import types
from datetime import datetime, timedelta
import re
import os
import signal
import sys

# Вставьте сюда ваш токен
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8169936734:AAEhipG_AH2fEI1NvRO4nEx9gJ11zjegCAI')
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Флаг для graceful shutdown
running = True

def signal_handler(signum, frame):
    """Обработчик сигналов для graceful shutdown"""
    global running
    print("\nПолучен сигнал завершения. Останавливаю бота...")
    running = False
    bot.stop_polling()

# Регистрируем обработчики сигналов
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Словарь для нормализации символов (греческие, латиница -> кириллица)
SIMILAR_LETTERS = {
    # Греческие
    'Α': 'А', 'Β': 'В', 'Ε': 'Е', 'Ζ': 'З', 'Η': 'Н', 'Ι': 'И', 'Κ': 'К', 'Μ': 'М', 'Ν': 'Н', 'Ο': 'О', 'Ρ': 'Р', 'Τ': 'Т', 'Υ': 'У', 'Χ': 'Х',
    # Латиница
    'A': 'А', 'B': 'В', 'C': 'С', 'E': 'Е', 'H': 'Н', 'I': 'И', 'K': 'К', 'M': 'М', 'O': 'О', 'P': 'Р', 'S': 'С', 'T': 'Т', 'X': 'Х', 'Y': 'У',
    # Похожие символы
    '0': 'О', '3': 'З', '6': 'Б', '4': 'Ч', '8': 'В',
    # Маленькие
    'а': 'а', 'с': 'с', 'е': 'е', 'о': 'о', 'р': 'р', 'х': 'х', 'у': 'у', 'к': 'к', 'м': 'м', 'н': 'н', 'т': 'т', 'в': 'в', 'з': 'з', 'и': 'и',
    # Греческие маленькие
    'α': 'а', 'β': 'в', 'γ': 'г', 'δ': 'д', 'ε': 'е', 'η': 'н', 'ι': 'и', 'κ': 'к', 'μ': 'м', 'ν': 'н', 'ο': 'о', 'ρ': 'р', 'τ': 'т', 'υ': 'у', 'χ': 'х',
}

def normalize_text(text):
    """Заменяет похожие символы на кириллицу для борьбы с обходом фильтра."""
    return ''.join(SIMILAR_LETTERS.get(c, c) for c in text)

# Регулярки для поиска спама (по нормализованному тексту)
SPAM_PATTERNS = [
    # Старые паттерны
    r'срочн. наб.р',
    r'л[её]гк. задач',
    r'мгновенн. оплат',
    r'деньг. на карт',
    r'ограничен',
    r'зарабатыва',
    r'https?://clck\.ru',
    r'онлайн.?опрос',
    r'тест.?приложен',
    r'отзыв.?серв',
    r'\d+.{0,10}(руб|р|₽|₽|k|к|т[ысрч])',
    
    # Новые паттерны для шабашек и подработок
    r'шабашк[аиу]',
    r'на (пару|несколько) часов',
    r'\d+[-–]\d+ (человек|чела|ч[её]л)',
    r'(плат[ияюем]{1,3}|оплат[ау]).{0,10}\d+[.,]?\d*\s*(р|руб|₽|₽|k|к|т[ысрч])',
    r'в (конце|концу) (смен[ыы]|работ[ыы])',
    r'разов[аыую] работ',
    r'подработк[аиу]',
    r'смен[ауы].{0,10}\d+[.,]?\d*\s*(р|руб|₽|₽|k|к|т[ысрч])',
    r'\d+[kк]\s*(р|руб|₽|₽)',
    r'(за|по)\s*\d+[.,]?\d*\s*(р|руб|₽|₽|k|к|т[ысрч])',
    r'(нужны?|ищем|требуются).{0,10}(работник|сотрудник|помощник)',
]

SPAM_REGEXES = [re.compile(p, re.IGNORECASE) for p in SPAM_PATTERNS]

# Проверка на спам
def is_spam(text):
    norm = normalize_text(text)
    for regex in SPAM_REGEXES:
        if regex.search(norm):
            return True
    return False

# Обработчик всех сообщений
@bot.message_handler(content_types=['text'])
def handle_message(message: types.Message):
    try:
        if message.chat.type not in ['group', 'supergroup']:
            return
        if is_spam(message.text):
            try:
                bot.delete_message(message.chat.id, message.message_id)
            except Exception as e:
                print(f"Ошибка при удалении сообщения: {e}")
            try:
                # Проверяем права бота
                bot_info = bot.get_me()
                chat_member = bot.get_chat_member(message.chat.id, bot_info.id)
                
                print(f"Статус бота: {chat_member.status}")
                print(f"Может ограничивать: {chat_member.can_restrict_members}")
                
                if chat_member.status == 'administrator' and chat_member.can_restrict_members:
                    # Проверяем статус пользователя
                    user_member = bot.get_chat_member(message.chat.id, message.from_user.id)
                    print(f"Статус пользователя: {user_member.status}")
                    
                    if user_member.status in ['restricted', 'kicked']:
                        bot.send_message(message.chat.id, f"Пользователь {message.from_user.first_name} уже заблокирован.")
                        return
                    
                    # Бан на 30 дней
                    until_date = datetime.utcnow() + timedelta(days=30)
                    bot.ban_chat_member(message.chat.id, message.from_user.id, until_date=until_date)
                    bot.send_message(message.chat.id, f"Пользователь {message.from_user.first_name} заблокирован на 30 дней за спам.")
                else:
                    error_msg = f"Спам от {message.from_user.first_name} обнаружен, но у бота нет прав на блокировку пользователей."
                    if chat_member.status != 'administrator':
                        error_msg += " Бот не является администратором."
                    elif not chat_member.can_restrict_members:
                        error_msg += " Нет права 'Блокировать пользователей'."
                    bot.send_message(message.chat.id, error_msg)
            except Exception as e:
                print(f"Ошибка при блокировке пользователя: {e}")
                error_details = f"Спам от {message.from_user.first_name} обнаружен, но не удалось заблокировать пользователя. Ошибка: {str(e)}"
                bot.send_message(message.chat.id, error_details)
    except Exception as e:
        print(f"Общая ошибка в обработчике сообщений: {e}")

if __name__ == '__main__':
    print('Бот запущен... Нажмите Ctrl+C для остановки.')
    try:
        while running:
            try:
                bot.polling(none_stop=True, timeout=60)
            except Exception as e:
                print(f"Ошибка в polling: {e}")
                if not running:
                    break
                print("Перезапуск через 5 секунд...")
                import time
                time.sleep(5)
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем.")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
    finally:
        print("Завершение работы бота.") 
