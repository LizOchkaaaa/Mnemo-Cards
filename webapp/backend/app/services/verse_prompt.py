# Файл для формирования промпта для генерации стихотворений

from __future__ import annotations
import logging
from app.services.verse_rhymes import (
    get_ipa,
    get_rhyme_hints_for_prompt_with_ipa,
    get_russian_rhyme_candidates,
    russian_word_with_stress,
)

logger = logging.getLogger(__name__)

VERSE_LEARNING_LANG_LABELS: dict[str, str] = {
    "en": "английский",
    "de": "немецкий",
    "fr": "французский",
    "es": "испанский",
    "it": "итальянский",
}

DEFAULT_VERSE_PROMPT_TEMPLATE = """Напиши детское стихотворение в две строки на русском языке, чтобы ребёнку было легко запомнить иностранное слово.

Правила:
1. Изучаемое слово «{word}» (на языке {lang}) должно встречаться в стихотворении один раз, в конце второй строки.
2. Перевод «{translation}» должен встречаться в стихотворении один раз во второй строке.
2. В конце первой строки должно стоять русское слово, которое рифмуется с «{word}» (по звучанию).
3. Иностранное слово «{word}» не переводится, вставляется как есть.
4. Перевод слова «{word}» = «{translation}» должен быть понятен из контекста стихотворения.
5. Стихотворение должно быть простым, детским, ровно две строки.

Слово: {word}
Перевод: {translation}
Язык слова: {lang}
Подсказка по звучанию для рифмы: {phonetic_hint}

Теперь напиши двустишие для слова «{word}» с переводом «{translation}».
"""

# Один шаблон для всех языков изучения
VERSE_PROMPT_TEMPLATES: dict[str, str] = {
    "en": DEFAULT_VERSE_PROMPT_TEMPLATE,
    "de": DEFAULT_VERSE_PROMPT_TEMPLATE,
    "es": DEFAULT_VERSE_PROMPT_TEMPLATE,
    "it": DEFAULT_VERSE_PROMPT_TEMPLATE,
    "fr": DEFAULT_VERSE_PROMPT_TEMPLATE,
}

# Возвращаем шаблон промпта для указанного языка
def get_default_verse_prompt_template(language: str | None) -> str:
    lang = (language or "").strip().lower()
    return VERSE_PROMPT_TEMPLATES.get(lang, DEFAULT_VERSE_PROMPT_TEMPLATE)

# Подставляем данные в шаблон промпта
def apply_verse_prompt_template(
    template: str,
    word: str,
    translation: str,
    phonetic_ipa: str = "",
    *,
    verse_learning_lang: str = "en",
) -> str:
    w = (word or "").strip().lower()
    t = (translation or "").strip().lower()
    vlc = (verse_learning_lang or "en").strip().lower()[:2] or "en"
    lang_label = VERSE_LEARNING_LANG_LABELS.get(vlc, vlc)
    # Получаем IPA транскрипцию
    ipa = (phonetic_ipa or "").strip() or get_ipa(w, lang=vlc)
    # Получаем подсказки по рифмам на основе IPA
    phonetic_hint = get_rhyme_hints_for_prompt_with_ipa(w, ipa)
    # Подставляем значения в шаблон
    out = template
    out = out.replace("{phonetic_hint}", phonetic_hint)
    out = out.replace("{translation}", t)
    out = out.replace("{word}", w)
    out = out.replace("{ipa}", ipa)
    out = out.replace("{lang}", lang_label)

    return out

# После неудачной проверки стиха добавляет явный список русских кандидатов для конца первой строки
def append_rhyme_retry_block(
    base_prompt: str,
    word: str,
    phonetic_ipa: str = "",
    *,
    verse_learning_lang: str = "en",
    max_examples: int = 10,
) -> str:
    w = (word or "").strip().lower()
    if not w:
        return base_prompt
    vlc = (verse_learning_lang or "en").strip().lower()[:2] or "en"
    ipa = (phonetic_ipa or "").strip() or get_ipa(w, lang=vlc)

    candidates = get_russian_rhyme_candidates(w, max_results=max_examples)
    extra_lines = [
        "",
        "---",
        "Предыдущий вариант не прошёл автоматическую проверку формы или рифмы.",
        (
            "Выбери другое одно русское слово в конце первой строки, которое рифмуется с «"
            + w
            + "» по звучанию. Примеры частотных русских слов, которые могут подойти:"
        ),
    ]
    if candidates:
        shown = candidates[:max_examples]
        stressed = [russian_word_with_stress(rw) for rw, _ in shown]
        extra_lines.append(", ".join(f"«{x}»" for x in stressed if x))
    else:
        extra_lines.append(get_rhyme_hints_for_prompt_with_ipa(w, ipa))

    extra_lines.append(
        "Снова напиши ровно две строки стиха на русском по тем же правилам (изучаемое слово только в конце второй строки, один раз)."
    )
    return (base_prompt.rstrip() + "\n" + "\n".join(extra_lines)).strip() + "\n"

# Формируем готовый промпт для генерации стихотворения
def build_poem_prompt_with_examples(
    *,
    word: str,
    translation_ru: str,
    phonetic_ipa: str = "",
    template: str | None = None,
    verse_learning_lang: str = "en",
) -> str:
    body = (template if template is not None else "").strip()
    if not body:
        body = DEFAULT_VERSE_PROMPT_TEMPLATE
    return apply_verse_prompt_template(
        body,
        word,
        translation_ru,
        phonetic_ipa,
        verse_learning_lang=verse_learning_lang,
    )