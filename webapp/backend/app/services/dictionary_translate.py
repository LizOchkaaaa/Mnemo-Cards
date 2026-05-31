# Перевод слова через API MyMemory

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

# Языки
_MYMEMORY_ALLOWED: frozenset[str] = frozenset({
    "en",
    "ru", 
    "de", 
    "fr", 
    "es", 
    "it",
})

# Приводим код языка к стандартному формату для MyMemory API
def normalize_translation_lang_code(code: str | None, *, fallback: str = "en") -> str:
    # Нормализуем
    c = (code or "").strip().lower()
    if len(c) >= 2 and c[:2] in _MYMEMORY_ALLOWED:
        return c[:2]
    return fallback[:2]

# Переводим слово через MyMemory API
def fetch_mymemory_translation(
    word: str,
    *,
    source_lang: str = "en",    # С какого языка переводим
    target_lang: str = "ru",    # На какой язык переводим
    timeout_sec: float = 6.0,   # Таймаут запроса
) -> str | None:
    w = (word or "").strip()
    if not w or len(w) > 500:
        return None
    # Нормализуем
    src = normalize_translation_lang_code(source_lang, fallback="en")
    tgt = normalize_translation_lang_code(target_lang, fallback="ru")
    if src == tgt:
        return None

    # Кодируем слово для безопасной передачи в URL
    q = urllib.parse.quote(w)
    url = f"https://api.mymemory.translated.net/get?q={q}&langpair={src}|{tgt}"

    try:
        # Создаём запрос
        req = urllib.request.Request(url, headers={"User-Agent": "MnemoBackend/1.0"})
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            data = json.loads(resp.read())
            
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, json.JSONDecodeError):
        logger.debug("[TRANSLATE] MyMemory failed: %s", exc)
        return None

    # Проверка
    if not isinstance(data, dict):
        return None

    # Пытаемся получить перевод из поля responseData
    rd = data.get("responseData") or {}
    text = (rd.get("translatedText") or "").strip()
    
    # Список сообщений-заглушек означают, что перевод не удался
    forbidden = {"MYMEMORY WARNING", "PLEASE SELECT TWO DISTINCT LANGUAGES"}
    
    # Если есть текст и это не сообщение об ошибке
    if text and not any(msg in text.upper() for msg in forbidden):
        # И если перевод не совпадает с исходным словом
        if text.lower() != w.lower():
            return text

    # Если не нашли в responseData, ищем в массиве matches
    for m in data.get("matches") or []:
        if isinstance(m, dict):
            t = (m.get("translation") or "").strip()
            if t and t.lower() != w.lower() and len(t) < 2048:
                return t
    return None

# Возвращаем список языков, поддерживаемых MyMemory API
def supported_translation_lang_codes() -> frozenset[str]:
    return _MYMEMORY_ALLOWED