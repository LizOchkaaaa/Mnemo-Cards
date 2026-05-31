# Файл для получения IPA-транскрипции

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Callable
from phonemizer import phonemize


# Поддерживаемые коды
IPA_SUPPORTED_LANGS: frozenset[str] = frozenset(
    {"en", "de", "fr", "es", "it"}
)

_ESPEAK_LANG: dict[str, str] = {
    "en": "en-gb",
    "de": "de",
    "fr": "fr-fr",
    "es": "es",
    "it": "it",
}

# Нормализация языков
def _normalize_en_word(word: str) -> str:
    t = (word or "").strip().lower()
    return re.sub(r"[^a-z]+", "", t)

def _normalize_de_word(word: str) -> str:
    t = unicodedata.normalize("NFC", (word or "").strip().lower())
    return re.sub(r"[^a-zäöüß]+", "", t)


def _normalize_es_word(word: str) -> str:
    t = unicodedata.normalize("NFC", (word or "").strip().lower())
    return re.sub(r"[^a-záéíóúñü]+", "", t)


def _normalize_fr_word(word: str) -> str:
    t = unicodedata.normalize("NFC", (word or "").strip().lower())
    return re.sub(r"[^a-zàâäæçéèêëïîôùûüÿœáíóú]+", "", t)


def _normalize_it_word(word: str) -> str:
    t = unicodedata.normalize("NFC", (word or "").strip().lower())
    return re.sub(r"[^a-zàèéìíîòóùú]+", "", t)


_NORMALIZERS: dict[str, Callable[[str], str]] = {
    "en": _normalize_en_word,
    "de": _normalize_de_word,
    "fr": _normalize_fr_word,
    "es": _normalize_es_word,
    "it": _normalize_it_word,
}

# Вызываем phonemizer для получения IPA транскрипции
def _ipa_espeak(clean_letters: str, espeak_lang: str) -> str:
    if not clean_letters:
        return ""
    
    # Вызов phonemizer
    out = phonemize(
        clean_letters,               # Текст для транскрипции
        language=espeak_lang,        # Язык
        backend="espeak",            # Используем движок eSpeak
        strip=True,                  # Убираем лишние пробелы
        preserve_punctuation=False,  # Удаляем пунктуацию
        with_stress=True,            # Добавляем ударения (ˈ и ˌ)
    )

    # Обработка результата
    if isinstance(out, str):
        return out.replace("\n", " ").strip()
    return ""

# Кэшируем
@lru_cache(maxsize=16384)
def _cached_phoneme(espeak_lang: str, clean: str) -> str:
    return _ipa_espeak(clean, espeak_lang)

# Приводим код языка к стандартному виду, поддерживаемому IPA функцией
def normalize_ipa_lang_code(lang: str | None) -> str:
    # Берём первые 2 символа, приводим к нижнему регистру
    code = (lang or "en").strip().lower()[:2]
    if code in IPA_SUPPORTED_LANGS:
        return code
    return "en"

# Код голоса espeak-ng для произношения
def espeak_voice_for_lang(lang: str | None) -> str:
    code = normalize_ipa_lang_code(lang)
    return _ESPEAK_LANG.get(code, "en-gb")


# Основная функция для получения IPA-транскрипции слова
def get_ipa(word: str, *, refresh: bool = False, lang: str = "en") -> str:
    # Стандартный вид
    code = normalize_ipa_lang_code(lang)
    # Проверяем, есть ли голос для этого языка в eSpeak
    if code not in _ESPEAK_LANG:
        code = "en"
    # Норализуем слово
    norm = _NORMALIZERS.get(code, _normalize_en_word)
    clean = norm(word)
    if not clean:
        return ""
    # Получаем код голоса для eSpeak
    espeak = _ESPEAK_LANG[code]
    if refresh:
        return _ipa_espeak(clean, espeak)
    
    return _cached_phoneme(espeak, clean)