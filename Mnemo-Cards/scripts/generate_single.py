# Скрипт генерации простых слов

import argparse
import json
from pathlib import Path
from typing import List, Set
import nltk
from wordfreq import top_n_list
from nltk.corpus import words as words_corpus

# Скачиваем необходимые ресурсы NLTK
def download_nltk_resources():
    resources = ["words_english", "words_german", "words_french", "words_spanish", "words_italian"]
    for res in resources:
        try:
            nltk.download(res, quiet=True)
        except:
            pass

download_nltk_resources()

# Маппинг языков
NLTK_MAP = {
    "en": "words_english",
    "de": "words_german", 
    "fr": "words_french",
    "es": "words_spanish",
    "it": "words_italian",
}

# Список поддерживаемых языков
SUPPORTED_LANGS = ["en", "de", "fr", "es", "it"]

# Получение словаря для языка
def get_lexicon(lang: str) -> Set[str]:
    nltk_code = NLTK_MAP.get(lang)
    if nltk_code:
        corpus = getattr(words_corpus, nltk_code)
        return {w.lower() for w in corpus.words() if w.isalpha()}
    return set()

# Проверка, что слово состоит только из допустимых букв
def is_clean_word(w: str, lang: str) -> bool:
    if not w or not w.islower():
        return False
    
    if lang in ["en", "de", "fr", "es", "it"]:
        return w.isalpha()
    return False

# Проверка, является ли слово составным
def looks_like_compound(w: str, lexicon: Set[str], lang: str) -> bool:
    if not lexicon or len(w) < 6:
        return False
    
    # Для разных языков разная минимальная длина части
    min_part_len = 4 if lang == "de" else 3
    
    for i in range(min_part_len, len(w) - min_part_len + 1):
        first = w[:i]
        second = w[i:]
        
        # Обе части должны быть осмысленными словами
        if first in lexicon and second in lexicon:
            return True
    
    return False

# Генерация простых слов
def generate_for_lang(lang: str, n: int = 2000) -> List[dict]:
    lexicon = get_lexicon(lang)
    
    # Получаем список частотных слов
    candidates = top_n_list(lang, max(n * 3, 20000))
    
    words_list = []
    for w in candidates:
        w = w.strip().lower()
        
        if not is_clean_word(w, lang):
            continue
        if len(w) < 4 or len(w) > 14:
            continue
        
        # Исключаем составные слова
        if looks_like_compound(w, lexicon, lang):
            continue
        
        words_list.append(w)
        if len(words_list) >= n:
            break
    
    print(f"[{lang}] Сгенерировано {len(words_list)} простых слов")
    
    # Формируем записи для датасета
    return [
        {"input": {"lang": lang, "word": w}, "target": {"kind": "single", "parts": [w]}}
        for w in words_list
    ]

# Генерация для всех языков
def generate_all_languages(n: int = 2000, out_dir: str = "data"):
    out_path_dir = Path(out_dir)
    out_path_dir.mkdir(parents=True, exist_ok=True)
    
    all_rows = []
    
    for lang in SUPPORTED_LANGS:
        rows = generate_for_lang(lang, n)
        all_rows.extend(rows)
        
        if rows:
            # Сохраняем отдельный файл для языка
            out_file = out_path_dir / f"single_{lang}.jsonl"
            with out_file.open("w", encoding="utf-8") as f:
                for row in rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
    
    # Сохраняем общий файл
    all_file = out_path_dir / "all_single.jsonl"
    with all_file.open("w", encoding="utf-8") as f:
        for row in all_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    
    print(f"Всего сгенерировано: {len(all_rows)} слов")
    return all_rows

def main():
    parser = argparse.ArgumentParser(description="Генерация датасета простых слов")
    parser.add_argument("--n", type=int, default=2000)
    parser.add_argument("--out-dir", type=str, default="data")
    
    args = parser.parse_args()
    
    # Генерация датасета
    generate_all_languages(args.n, args.out_dir)

if __name__ == "__main__":
    main()