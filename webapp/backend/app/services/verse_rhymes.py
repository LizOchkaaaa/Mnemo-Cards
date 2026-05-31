# Файл для фонетического анализа и подбора рифм для стихотворений

from __future__ import annotations
import logging
import re
from functools import lru_cache
from typing import List, Optional, Set, Tuple, Dict
from app.core.config import get_settings
from app.services.ipa_word import get_ipa
import wordfreq

logger = logging.getLogger(__name__)

# Гласные в IPA для подсчёта позиции ударения
_IPA_VOWEL_CHARS = frozenset("ɐɑeɛiɨɪɔoʊuʌəæɜɵɞɯɤøœyɒʉaɤ")
# Минимальная длина кандидатов рифм 
_MIN_RHYME_CANDIDATE_LEN = 4

# Базовые преобразования IPA в русские звуки
_IPA_BASE_TO_RU: List[Tuple[str, str]] = [
    ("tʃ", "ч"),
    ("dʒ", "дж"),
    ("ʃ", "ш"),
    ("ʒ", "ж"),
    ("θ", "с"),
    ("ð", "з"),
    ("ŋ", "н"),
    ("m", "м"),
    ("n", "н"),
    ("p", "п"),
    ("b", "б"),
    ("t", "т"),
    ("d", "д"),
    ("k", "к"),
    ("g", "г"),
    ("f", "ф"),
    ("v", "в"),
    ("s", "с"),
    ("z", "з"),
    ("h", "х"),
    ("ɹ", "р"),
    ("r", "р"),
    ("l", "л"),
    ("w", "у"),
    ("j", "й"),
    ("juː", "ю"),
    ("ja", "я"),
    ("je", "е"),
    ("jo", "ё"),
    ("ji", "йи"),
]

# Специфичные преобразования для разных языков
_LANG_IPA_RULES: Dict[str, List[Tuple[str, str]]] = {
    "en": [
        ("eɪ", "ей"),
        ("aɪ", "ай"),
        ("ɔɪ", "ой"),
        ("aʊ", "ау"),
        ("oʊ", "оу"),
        ("əʊ", "оу"),
        ("ɪə", "иэ"),
        ("eə", "эа"),
        ("ʊə", "уа"),
        ("iː", "и"),
        ("uː", "у"),
        ("ɔː", "о"),
        ("ɑː", "а"),
        ("ɜː", "ё"),
        ("əː", "ы"),
        ("ɪ", "и"),
        ("i", "и"),
        ("ɛ", "э"),
        ("e", "э"),
        ("æ", "э"),
        ("ʌ", "а"),
        ("ɒ", "о"),
        ("ɔ", "о"),
        ("ɑ", "а"),
        ("ʊ", "у"),
        ("u", "у"),
        ("ər", "ер"),
        ("ɜr", "ёр"),
        ("ɪr", "ир"),
        ("ʊr", "ур"),
        ("ən", "ен"),
        ("əm", "ем"),
        ("əl", "ел"),
        ("ə", "э"),
        ("lɚ", "лер"),
        ("ɚ", "ер"),
    ],
    "de": [
        ("aɪ", "ай"),
        ("aʊ", "ау"),
        ("ɔʏ", "ой"),
        ("eɪ", "эй"),
        ("iː", "и"),
        ("uː", "у"),
        ("yː", "ю"),
        ("øː", "ё"),
        ("œ", "ё"),
        ("ɪ", "и"),
        ("ʏ", "ю"),
        ("ʊ", "у"),
        ("ɛ", "э"),
        ("œ", "ё"),
        ("ɔ", "о"),
        ("a", "а"),
        ("aː", "а"),
        ("eː", "э"),
        ("oː", "о"),
        ("ə", "э"),
        ("ɐ", "а"),
        ("ç", "хь"),
        ("x", "х"),
        ("ʁ", "р"),
        ("pf", "пф"),
        ("ts", "ц"),
        ("ŋ", "н"),
    ],
    "fr": [
        ("ɑ̃", "ан"),
        ("ɛ̃", "эн"),
        ("œ̃", "ён"),
        ("ɔ̃", "он"),
        ("i", "и"),
        ("e", "э"),
        ("ɛ", "э"),
        ("a", "а"),
        ("ɑ", "а"),
        ("o", "о"),
        ("ɔ", "о"),
        ("u", "у"),
        ("y", "ю"),
        ("ø", "ё"),
        ("œ", "ё"),
        ("ə", "э"),
        ("ʁ", "р"),
        ("ɲ", "нь"),
        ("j", "й"),
        ("w", "у"),
        ("ɥ", "ю"),
    ],
    "it": [
        ("i", "и"),
        ("e", "э"),
        ("ɛ", "э"),
        ("a", "а"),
        ("o", "о"),
        ("ɔ", "о"),
        ("u", "у"),
        ("ʎ", "ль"),
        ("ɲ", "нь"),
        ("ʃ", "ш"),
        ("dz", "дз"),
        ("ts", "ц"),
    ],
    "es": [
        ("i", "и"),
        ("e", "э"),
        ("a", "а"),
        ("o", "о"),
        ("u", "у"),
        ("β", "в"),
        ("ð", "д"),
        ("ɣ", "г"),
        ("ʎ", "ль"),
        ("ɲ", "нь"),
        ("x", "х"),
        ("θ", "с"),
        ("rr", "рр"),
    ],
}

# Правила русской фонетики (оглушение, редукция)
_RUSSIAN_PHONETIC_RULES: Dict[str, str] = {
    # Оглушение звонких согласных на конце слова
    "б": "п",
    "в": "ф",
    "г": "к",
    "д": "т",
    "ж": "ш",
    "з": "с",
    # Редукция гласных в безударной позиции
    "о": "а",
    "е": "и",
    "я": "и",
    "ё": "и",
}

# Применяет фонетические правила русского языка
def _apply_russian_phonetic_rules(word: str, stress_position: Optional[int] = None) -> str:
    if not word:
        return ""
    
    result = list(word.lower())
    
    # Оглушение на конце слова
    if result and result[-1] in _RUSSIAN_PHONETIC_RULES:
        result[-1] = _RUSSIAN_PHONETIC_RULES[result[-1]]
    
    # Редукция безударных гласных
    if stress_position is not None:
        for i, ch in enumerate(result):
            if i != stress_position and ch in "оеяё":
                result[i] = _RUSSIAN_PHONETIC_RULES.get(ch, ch)
    
    return "".join(result)

# Получаем IPA для слова на указанном языке
def _get_ipa_for_lang(word: str, lang: str = "en") -> str:
    if not word:
        return ""
    try:
        return get_ipa(word, lang=lang)
    except:
        return get_ipa(word)

# Применяем специфичные правила преобразования IPA в русское звучание
def _apply_lang_ipa_rules(ipa: str, lang: str) -> str:
    if not ipa:
        return ""
    
    s = ipa.strip()
    # Очищаем от служебных символов
    s = re.sub(r"[ˈˌ\[\]()]", "", s)
    
    result = []
    i = 0
    
    # Сначала применяем базовые правила
    rules = _IPA_BASE_TO_RU.copy()
    
    # Добавляем специфичные правила для языка
    if lang in _LANG_IPA_RULES:
        rules.extend(_LANG_IPA_RULES[lang])
    
    # Сортируем по длине для корректного сопоставления
    rules.sort(key=lambda x: -len(x[0]))
    
    while i < len(s):
        matched = False
        for ipa_seq, ru_char in rules:
            if s.startswith(ipa_seq, i):
                result.append(ru_char)
                i += len(ipa_seq)
                matched = True
                break
        if not matched:
            # Пропускаем непонятные символы
            i += 1
    
    return "".join(result)

# Определяем позицию ударения в IPA-строке
def _get_stress_position(ipa: str) -> Optional[int]:
    if not ipa:
        return None
    
    # Ищем символ ударения
    stress_match = re.search(r"[ˈˌ](.)", ipa)
    if stress_match:
        return stress_match.start(1)
    return None

# Транслитерация
@lru_cache(maxsize=2000)
def get_word_ru_sound(word: str, lang: str = "en") -> str:
    if not word:
        return ""
    w = word.strip().lower() 

    # Получаем IPA для указанного языка
    ipa_original = _get_ipa_for_lang(w, lang)
    stress_pos = _get_stress_position(ipa_original)
    
    # Транслитерируем в русское звучание
    ru_sound_raw = _apply_lang_ipa_rules(ipa_original, lang)
    
    # Применяем правила русской фонетики
    ru_sound = _apply_russian_phonetic_rules(ru_sound_raw, stress_pos)
    
    # Очищаем от небуквенных символов
    ru_sound = re.sub(r"[^а-яё]", "", ru_sound)
    
    return ru_sound

# Поиск рифмующихся русских слов для слова на любом языке
def get_rhyme_candidates(word: str, lang: str = "en", max_results: int = 6) -> List[Tuple[str, str]]:
    if not word:
        return []
    
    # Получаем русское звучание исходного слова
    ru_sound = get_word_ru_sound(word, lang)
    logger.debug("[RHYME] %s (%s) → «%s», ищем рифмы", word, lang, ru_sound)
    
    if not ru_sound:
        return []
    
    # Ищем рифмы среди русских слов
    return _find_russian_rhymes(ru_sound, max_results)

# Поиска рифм среди русских слов с учётом фонетики
def _find_russian_rhymes(ru_sound: str, max_results: int = 6) -> List[Tuple[str, str]]:
    need = _rhyme_min_tail_match()
    
    # Строим IPA для эталонного русского звучания
    ipa_ref = get_ipa(ru_sound, lang="ru")
    
    # Загружаем частотный словарь русских слов
    lex = _load_wordfreq_ru_words()
    
    # Фильтруем подходящие слова
    words_list = [w for w in lex if _is_valid_rhyme_lexeme(w, ru_sound)]
    
    # Сортируем по приоритету окончания
    ordered = _ordered_by_tail_priority(words_list, ru_sound)
    
    ipa_budget = get_settings().mnemo_rhyme_max_ipa_checks
    scored: List[Tuple[int, str]] = []
    ipa_calls = 0
    
    for w in ordered:
        if not ipa_ref or ipa_calls >= ipa_budget:
            break
        
        ipa_calls += 1
        # Строим IPA для слова-кандидата
        ipa_w = get_ipa(w, lang="ru")
        # Сравниваем фонетические окончания
        tail = _ipa_tail_match_score(ipa_ref, ipa_w)
        
        if tail >= need:
            scored.append((tail, w))
    
    # Сортируем по длине совпадения, затем по длине слова
    scored.sort(key=lambda t: (-t[0], len(t[1]), t[1]))
    
    seen: Set[str] = set()
    candidates: List[Tuple[str, str]] = []
    
    for _, w in scored:
        if w in seen:
            continue
        seen.add(w)
        candidates.append((w, ""))
        if len(candidates) >= max_results:
            break
    
    # Добираем по буквенному окончанию, если не хватает
    if len(candidates) < max_results and len(ru_sound) >= 2:
        for suf_len in (3, 2):
            if len(ru_sound) < suf_len:
                continue
            suf = ru_sound[-suf_len:]
            for w in lex:
                if (not _is_valid_rhyme_lexeme(w, ru_sound) 
                    or w in seen 
                    or len(w) < suf_len 
                    or not w.endswith(suf)):
                    continue
                candidates.append((w, ""))
                seen.add(w)
                if len(candidates) >= max_results:
                    break
            if len(candidates) >= max_results:
                break
    
    return candidates[:max_results]

# Формируем подсказку для модели о том, как рифмовать слово
def get_rhyme_hints_for_prompt(word: str, lang: str = "en") -> str:
    if not word:
        return ""
    
    ru_sound = get_word_ru_sound(word, lang)
    
    if not ru_sound:
        return f"Слово «{word}» нужно рифмовать по его звучанию на русском"
    
    candidates = get_rhyme_candidates(word, lang, max_results=4)
    
    if candidates:
        ru_words = [w for w, _ in candidates]
        examples = ", ".join(f"«{w}»" for w in ru_words[:3])
        ending = ru_sound[-2:] if len(ru_sound) >= 2 else ru_sound
        
        return (
            f"Русское произношение слова «{word}»: «{ru_sound}». "
            f"Рифмуй с русскими словами, оканчивающимися на «{ending}». "
            f"Примеры: {examples}."
        )
    else:
        ending = ru_sound[-2:] if len(ru_sound) >= 2 else ru_sound
        return f"Рифмуй слово «{word}» (произносится как «{ru_sound}») с русскими словами на «{ending}»"

# Оцениваем длину совпадающего фонетического хвоста IPA
def _ipa_tail_match_score(ipa1: str, ipa2: str) -> int:
    a = _normalize_ipa_for_rhyme(ipa1)
    b = _normalize_ipa_for_rhyme(ipa2)
    if not a or not b:
        return 0
    n = min(len(a), len(b))
    for i in range(1, n + 1):
        if a[-i:] != b[-i:]:
            return i - 1
    return n

# Нормализуем
def _normalize_ipa_for_rhyme(ipa: str) -> str:
    if not ipa:
        return ""
    s = ipa.replace("ˈ", "").replace("ˌ", "").replace("ː", "")
    s = re.sub(r"\s+", "", s)
    return s

# Возвращаем минимальную длину совпадающего фонетического хвоста для рифмы
def _rhyme_min_tail_match() -> int:
    return get_settings().mnemo_rhyme_min_tail_match

# Проверяем подходит ли русское слово для рифмы
def _is_valid_rhyme_lexeme(word_ru: str, ru_sound: str) -> bool:
    return len(word_ru) >= _MIN_RHYME_CANDIDATE_LEN and word_ru != ru_sound

# Сортируем слова по приоритету буквенного окончания
def _ordered_by_tail_priority(words_list: List[str], ru_sound: str) -> List[str]:
    if len(ru_sound) < 2:
        return words_list
    suf2 = ru_sound[-2:]
    prio = [w for w in words_list if w.endswith(suf2)]
    prio_set = set(prio)
    rest = [w for w in words_list if w not in prio_set]
    return prio + rest

# Загружаем частотный список русских слов из wordfreq
@lru_cache(maxsize=1)
def _load_wordfreq_ru_words() -> frozenset[str]:
    words: Set[str] = set()
    try:
        n = get_settings().mnemo_rhyme_wordfreq_n
        for w in wordfreq.top_n_list("ru", n, wordlist="best"):
            w = w.strip().lower()
            if len(w) >= 2 and len(w) <= 32 and re.fullmatch(r"[а-яё]+", w):
                words.add(w)
    except Exception as e:
        logger.warning("Failed to load wordfreq: %s", e)
    return frozenset(words)

# Проверяем рифмуются ли два слова с учётом фонетики
def last_tokens_rhyme(token_a: str, token_b: str, target_word_en: str = "", target_ipa: str = "", lang: str = "en") -> bool:
    if not token_a or not token_b:
        return False
    
    # Получаем IPA для русского слова
    ipa_a = get_ipa(token_a, lang="ru")
    
    # Для иностранного слова получаем IPA через его русское звучание
    ru_sound = get_word_ru_sound(token_b, lang)
    ipa_b = get_ipa(ru_sound, lang="ru") if ru_sound else ""
    
    if not ipa_a or not ipa_b:
        return False
    
    need = _rhyme_min_tail_match()
    tail = _ipa_tail_match_score(ipa_a, ipa_b)
    
    logger.debug("Rhyme check: %s vs %s, tail=%d, need=%d", token_a, token_b, tail, need)
    
    return tail >= need

# Экспорт функций
__all__ = [
    "get_ipa",
    "get_word_ru_sound",
    "get_rhyme_candidates",
    "get_rhyme_hints_for_prompt",
    "last_tokens_rhyme",
]