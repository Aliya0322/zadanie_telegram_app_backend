import hmac
import hashlib
import urllib.parse
import json
import time
from typing import Optional, Dict
from config import settings
import logging

logger = logging.getLogger(__name__)

# Максимальный возраст initData (24 часа в секундах)
MAX_AUTH_AGE = 86400


def verify_telegram_init_data(init_data: str) -> Optional[Dict]:
    """
    Проверяет Telegram initData и возвращает данные пользователя если проверка успешна.
    
    Алгоритм проверки согласно документации Telegram:
    1. Парсит initData
    2. Извлекает hash
    3. Создает data-check-string из всех полей кроме hash
    4. Вычисляет секретный ключ из bot_secret
    5. Вычисляет HMAC-SHA256 и сравнивает с полученным hash
    6. Проверяет auth_date (не старше 24 часов)
    
    Args:
        init_data: Строка initData из заголовка X-Telegram-Init-Data
        
    Returns:
        Словарь с данными пользователя (user_id, user_data, auth_date) или None если проверка не прошла
    """
    if not init_data or not init_data.strip():
        logger.warning("Empty init_data provided")
        return None
    
    try:
        # Парсим initData
        parsed_data = urllib.parse.parse_qs(init_data, keep_blank_values=True)
        
        # Извлекаем hash
        received_hash = parsed_data.get('hash', [None])[0]
        if not received_hash:
            logger.warning("No hash found in init_data")
            return None
        
        # Проверяем auth_date (не старше 24 часов)
        auth_date_str = parsed_data.get('auth_date', [None])[0]
        if auth_date_str:
            try:
                auth_date = int(auth_date_str)
                current_time = int(time.time())
                age = current_time - auth_date
                
                if age < 0:
                    logger.warning(f"Invalid auth_date: future timestamp")
                    return None
                
                if age > MAX_AUTH_AGE:
                    logger.warning(f"InitData too old: {age} seconds")
                    return None
            except (ValueError, TypeError):
                logger.warning(f"Invalid auth_date format: {auth_date_str}")
                return None
        
        # Создаем строку для проверки (все поля кроме hash, отсортированные по ключу)
        data_check_string_parts = []
        for key in sorted(parsed_data.keys()):
            if key != 'hash':
                value = parsed_data[key][0]
                if value:  # Пропускаем пустые значения
                    data_check_string_parts.append(f"{key}={value}")
        
        data_check_string = '\n'.join(data_check_string_parts)
        
        # Вычисляем секретный ключ из bot_secret
        # Согласно документации Telegram: secret_key = HMAC_SHA256("WebAppData", bot_token)
        secret_key = hmac.new(
            key=b"WebAppData",
            msg=settings.bot_secret.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        
        # Вычисляем hash
        # Согласно документации: hash = HMAC_SHA256(secret_key, data_check_string)
        calculated_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode('utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        # Сравниваем hash (постоянное время сравнения для защиты от timing attacks)
        if not hmac.compare_digest(calculated_hash, received_hash):
            logger.warning("Hash verification failed")
            return None
        
        # Извлекаем user_id из user JSON
        user_str = parsed_data.get('user', [None])[0]
        if not user_str:
            logger.warning("No user data found in init_data")
            return None
        
        try:
            user_data = json.loads(user_str)
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid user JSON: {e}")
            return None
        
        user_id = user_data.get('id')
        if not user_id:
            logger.warning("No user_id in user data")
            return None
        
        return {
            'user_id': user_id,
            'user_data': user_data,
            'auth_date': auth_date_str
        }
    except Exception as e:
        logger.error(f"Error verifying init data: {e}", exc_info=True)
        return None

