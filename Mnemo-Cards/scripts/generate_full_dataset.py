# clean_and_merge_datasets.py
import argparse
import json
import random
from pathlib import Path
from typing import List, Dict, Set, Tuple
from nltk.corpus import words

REAL_WORDS_CACHE = {
    "en": set(),
    "de": set(),
    "fr": set(),
    "es": set(),
    "it": set(),
}

# Загружаем реальные слова из NLTK
def load_real_words(lang: str) -> Set[str]:
    if REAL_WORDS_CACHE[lang]:
        return REAL_WORDS_CACHE[lang]
    
    if lang == "en":
        REAL_WORDS_CACHE["en"] = set(w.lower() for w in words.words())
    elif lang == "de":
        if hasattr(words, 'words_german'):
            REAL_WORDS_CACHE["de"] = set(w.lower() for w in words.words_german())
    elif lang == "fr":
        if hasattr(words, 'words_french'):
            REAL_WORDS_CACHE["fr"] = set(w.lower() for w in words.words_french())
    elif lang == "es":
        if hasattr(words, 'words_spanish'):
            REAL_WORDS_CACHE["es"] = set(w.lower() for w in words.words_spanish())
    elif lang == "it":
        if hasattr(words, 'words_italian'):
            REAL_WORDS_CACHE["it"] = set(w.lower() for w in words.words_italian())
    
    return REAL_WORDS_CACHE[lang]

# Проверяем существует ли слово в словаре
def word_exists_in_dictionary(word: str, lang: str) -> bool:
    word_lower = word.lower()
    
    # Загружаем словарь
    dictionary = load_real_words(lang)
    if dictionary:
        return word_lower in dictionary

    if len(word_lower) < 3:
        return False
    
    # Должна быть хотя бы одна гласная
    if lang == "en":
        if not any(c in 'aeiouy' for c in word_lower):
            return False
    elif lang == "de":
        if not any(c in 'aeiouäöüy' for c in word_lower):
            return False
    elif lang in ["fr", "es", "it"]:
        if not any(c in 'aeiou' for c in word_lower):
            return False
    
    return True

# Проверка, что слово состоит из допустимых букв
def is_clean_word(word: str, lang: str) -> bool:
    if not word or len(word) < 3:
        return False
    
    if lang == "en":
        return all('a' <= c <= 'z' for c in word.lower())
    elif lang == "de":
        return all(c in 'abcdefghijklmnopqrstuvwxyzäöüß' for c in word.lower())
    elif lang in ["fr", "es", "it"]:
        return all(c in 'abcdefghijklmnopqrstuvwxyzàâäéèêëîïôöùûüç' for c in word.lower())
    
    return True

# Проверка слов
def quick_word_exists(word: str, lang: str, strict: bool = False) -> bool:
    word_lower = word.lower()
    
    # Минимальная длина
    if len(word_lower) < 3:
        return False
    
    # Проверка на бессмысленные повторения
    if any(c * 5 in word_lower for c in set(word_lower)):
        return False
    
    # Строгая проверка по словарю
    if strict:
        return word_exists_in_dictionary(word_lower, lang)
    
    # Быстрая проверка
    if not is_clean_word(word_lower, lang):
        return False
    
    # Должна быть хотя бы одна гласная
    vowels_map = {
        "en": 'aeiouy',
        "de": 'aeiouäöüy',
        "fr": 'aeiouy',
        "es": 'aeiou',
        "it": 'aeiou',
    }
    vowels = vowels_map.get(lang, 'aeiou')
    if not any(c in vowels for c in word_lower):
        return False
    
    # Слишком много согласных подряд
    consonants = 'bcdfghjklmnpqrstvwxyz'
    if lang == "de":
        consonants = 'bcdfghjklmnpqrstvwxyzß'
    
    max_consecutive = 0
    current = 0
    for ch in word_lower:
        if ch in consonants:
            current += 1
            max_consecutive = max(max_consecutive, current)
        else:
            current = 0
    if max_consecutive > 4:
        return False
    
    return True

# Проверка, что части составного слова имеют смысл
def validate_compound_parts(parts: List[str], word: str, lang: str) -> bool:
    if not parts:
        return False
    
    for part in parts:
        if len(part) < 2 and part not in ['a', 'i', 'u', 'e', 'o', 't', 's', 'n', 'bi', 'tri', 'uni']:
            return False
    
    return True

# Проверяем нужно ли оставить запись
def clean_row(row: dict, lang: str, strict: bool = False) -> Tuple[bool, str]:
    word = row.get("input", {}).get("word", "")
    target = row.get("target", {})
    parts = target.get("parts", [])
    kind = target.get("kind", "unknown")
    
    if not word:
        return False, "пустое слово"
    
    # Для составных слов
    if kind == "compound":
        if not word_exists_in_dictionary(word, lang):
            return False, f"несуществующее слово: {word}"
        
        if parts and not validate_compound_parts(parts, word, lang):
            return False, f"невалидные части: {parts}"
    else:
        # Для простых слов
        if not quick_word_exists(word, lang, strict):
            return False, f"несуществующее слово: {word}"
    
    return True, "ok"

# Очищаем датасет от несуществующих слов
def clean_dataset(rows: List[dict], lang: str, strict: bool = False, 
                  verbose: bool = True) -> Tuple[List[dict], Dict[str, int]]:
    
    stats = {
        "total": len(rows),
        "kept": 0,
        "removed": 0,
        "removed_reasons": {},
        "by_kind": {"single": 0, "compound": 0}
    }
    
    cleaned_rows = []
    
    for row in rows:
        if "lang" not in row.get("input", {}):
            if "input" in row:
                row["input"]["lang"] = lang
            else:
                row["input"] = {"lang": lang, "word": row.get("word", "")}
        
        keep, reason = clean_row(row, lang, strict)
        
        if keep:
            cleaned_rows.append(row)
            stats["kept"] += 1
            
            kind = row.get("target", {}).get("kind", "unknown")
            if kind in stats["by_kind"]:
                stats["by_kind"][kind] += 1
        else:
            stats["removed"] += 1
            stats["removed_reasons"][reason] = stats["removed_reasons"].get(reason, 0) + 1
    
    return cleaned_rows, stats

# Читаем JSONL файл
def read_jsonl(path: Path) -> List[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

# Записываем JSONL файл
def write_jsonl(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--single", default="data/all_single.jsonl")
    parser.add_argument("--compound", default="data/all_compounds.jsonl")
    parser.add_argument("--out", default="data/final_dataset.jsonl")
    parser.add_argument("--shuffle", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    
    # Загрузка
    single_rows = read_jsonl(Path(args.single))
    compound_rows = read_jsonl(Path(args.compound))
    
    # Объединение
    all_rows = single_rows + compound_rows
    
    # Группируем по языкам
    rows_by_lang: Dict[str, List[dict]] = {
        "en": [],
        "de": [],
        "fr": [],
        "es": [],
        "it": [],
    }
    
    for row in all_rows:
        lang = row.get("input", {}).get("lang", "en")
        if lang not in rows_by_lang:
            lang = "en"
        rows_by_lang[lang].append(row)
    
    # Очистка
    cleaned_rows = []
    all_stats = {}
    
    for lang, rows in rows_by_lang.items():
        if not rows:
            continue
        
        cleaned, stats = clean_dataset(rows, lang, args.strict, args.verbose)
        cleaned_rows.extend(cleaned)
        all_stats[lang] = stats
    
    # Перемешивание
    if args.shuffle:
        random.seed(args.seed)
        random.shuffle(cleaned_rows)
    
    # Сохраняем
    write_jsonl(Path(args.out), cleaned_rows)

if __name__ == "__main__":
    main()