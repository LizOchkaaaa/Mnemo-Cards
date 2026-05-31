# Файл хеширование паролей через bcrypt

from __future__ import annotations
import bcrypt

# Лимит bcrypt: пароли длиннее 72 байт обрезаются
BCRYPT_MAX_BYTES = 72

# Преобразуем строку пароля в байты
def _password_bytes(password: str) -> bytes:
    if not password:
        return b""
    raw = password.encode("utf-8")
    if len(raw) <= BCRYPT_MAX_BYTES:
        return raw
    return raw[:BCRYPT_MAX_BYTES]

# Обрезаем пароль до 72 байт и возвращает как строку
def truncate_password_for_bcrypt(password: str) -> str:
    if not password:
        return password
    raw = password.encode("utf-8")
    if len(raw) <= BCRYPT_MAX_BYTES:
        return password
    # Обрезаем байты и декодируем обратно в строку
    return raw[:BCRYPT_MAX_BYTES].decode("utf-8", errors="ignore")

# Хешируем пароль с помощью bcrypt
def hash_password(password: str) -> str:
    # Преобразуем пароль в байты
    pwd_bytes = _password_bytes(password)
    # Создаём хеш пароль с солью
    hashed = bcrypt.hashpw(pwd_bytes, bcrypt.gensalt())
    # Возвращаем хеш в виде ASCII строки
    return hashed.decode("ascii")

# Проверяем, совпадает ли введённый пароль с сохранённым хешем
def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    
    pwd_bytes = _password_bytes(plain)
    
    # Преобразуем хеш из строки в байты
    try:
        hashed_bytes = hashed.encode("ascii")
    except UnicodeEncodeError:
        return False  # Хеш должен быть только ASCII
    
    try:
        # bcrypt.checkpw() делаем следующее:
        # 1. Забираем соль из hashed_bytes
        # 2. Хешируем pwd_bytes с этой солью
        # 3. Сравнивам результат с hashed_bytes
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except Exception:
        return False