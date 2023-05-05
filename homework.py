import logging
import os
import sys
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
from dotenv import load_dotenv
from telegram import Bot

from exceptions import APIResponseException
from settings import *

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler1 = logging.StreamHandler()
handler2 = RotatingFileHandler(
    'log.log',
    maxBytes=50000000,
    backupCount=5,
    encoding='utf-8'
)
logger.addHandler(handler1)
handler1.setFormatter(formatter)
logger.addHandler(handler2)
handler2.setFormatter(formatter)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    token_dict = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    for name, token in token_dict.items():
        if not token:
            error = f'Нет переменной {name}'
            logger.critical(error)
            sys.exit(error)


def send_message(bot, message):
    """
    Отправляет сообщение в Telegram чат.
    Чат определяется переменной TELEGRAM_CHAT_ID.
    """
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logger.debug(f'Сообщение "{message}" отправлено')


def get_api_answer(timestamp):
    """Отправка запроса к API."""
    request_params = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp},
    }
    try:
        response = requests.get(**request_params)        
    except requests.exceptions.RequestException as error:
        logger.error(f'Ошибка при подключении к API: {error}')
        raise ConnectionError(f'Ошибка при подключении к API: {error}')
    if response.status_code == HTTPStatus.OK.value:
            logger.info('Эндпоинт доступен')
    else:
        logger.warning(
            f'API вернул код ошибки: {response.status_code}'
        )
        if response.get('code'):
            if response.get('message'):
                error = response['message']
                logger.error(
                    f'Ошибка в ответе от API: {error}'
                )
                raise APIResponseException(
                    f'Ошибка в ответе от API: {error}'
                )
            error = response['error']['error']
            logger.error(
                f'Ошибка в ответе от API: {error}'
            )
            raise APIResponseException(
                f'Ошибка в ответе от API: {error}'
            )
    return response.json()


def check_response(response):
    """Проверка ответа API на документацию."""
    if not isinstance(response, dict):
        raise TypeError('"response" не является словарём')
    if not response.get('homeworks'):
        raise KeyError('Не найден ключ "homeworks"')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError('Ключ "homewokrs" не явлется списком')
    if len(response.get('homeworks')) == 0:
        raise APIResponseException('Список "homeworks" пустой')
    return response.get('homeworks')[LAST_HOMEWORK]


def parse_status(homework):
    """Выдает статус домашней работы и вердикт."""
    if not homework.get('homework_name'):
        raise KeyError('Нет ключа "homework_name"')
    homework_name = homework['homework_name']
    if not homework.get('status'):
        raise KeyError('Нет ключа "status"')
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        logger.error(f'Статус {status} не найден')
        raise KeyError(f'Статус {status} не известен')
    else:
        verdict = HOMEWORK_VERDICTS[status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = Bot(token=TELEGRAM_TOKEN)
    last_message = ''

    while True:
        try:
            response = get_api_answer(ALL_HOMEWORKS)
            homework = check_response(response)
            message = parse_status(homework)
            if message != last_message:
                try:
                    send_message(bot, message)
                    last_message = message
                except Exception:
                    logger.error('Сообщение не отправлено')
            else:
                logger.debug('Нет изменений')
        except Exception as error:
            message = (f'Сбой в работе программы: {error}')
            logger.error(message)
            if message != last_message:
                try:
                    send_message(bot, message)
                    last_message = message
                except Exception as error:
                    logger.error(f'Ошибка "{error}" не отправлена ботом ')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
