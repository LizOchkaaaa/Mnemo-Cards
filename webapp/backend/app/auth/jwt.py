# Файл для работы с JWT

from __future__ import annotations
from datetime import datetime, timedelta, timezone
import hashlib
import jwt

# Ключ 32 байта для HS256
def _hs256_signing_key(secret: str) -> bytes:
    return hashlib.sha256((secret or "").encode("utf-8")).digest()

# Создаем токен
def create_token(
    payload: dict,                        # Данные, которые хотим зашифровать
    secret: str,                          # Секретный ключ для подписи
    algorithm: str = "HS256",             # Алгоритм шифрования
    expire_minutes: int = 60 * 24 * 7,    # Время жизни токена в минутах
) -> str:
    # Получаем текущее время
    now = datetime.now(timezone.utc)
    # Формируем полный payload с добавлением стандартных полей JWT
    data = {**payload, "exp": now + timedelta(minutes=expire_minutes), "iat": now}
    key = _hs256_signing_key(secret) if algorithm.upper() == "HS256" else secret
    return jwt.encode(data, key, algorithm=algorithm)

# Декодируем и проверяем JWT токен (подпись, срок, алгоритм)
def decode_token(token: str, secret: str, algorithm: str = "HS256") -> dict | None:
    try:
        key = _hs256_signing_key(secret) if algorithm.upper() == "HS256" else secret
        return jwt.decode(token, key, algorithms=[algorithm])
    except jwt.PyJWTError:
        return None

