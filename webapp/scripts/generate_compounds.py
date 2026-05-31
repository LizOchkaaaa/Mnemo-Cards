# Скрипт генерации состаных слов

import argparse
import json
import random
from pathlib import Path
from typing import List, Tuple

LANG_DATA = {
    "en": {
        "stems": ["rain", "snow", "sun", "moon", "star", "fire", "water", "house", "man", "woman", "child", "car", "ball", "book", "day", "night", "sea", "sand", "rock", "tree", "flower"],
        "tails": ["house", "land", "water", "light", "man", "woman", "ball", "box", "bag", "time", "day", "night", "storm", "bow", "fall", "shine", "fly"],
        "examples": [
            ("seastorm", ["sea", "storm"]),
            ("rainforest", ["rain", "forest"]),
            ("butterfly", ["butter", "fly"]),
            ("football", ["foot", "ball"]),
            ("rainbow", ["rain", "bow"]),
            ("sunset", ["sun", "set"]),
            ("moonlight", ["moon", "light"]),
            ("snowman", ["snow", "man"]),
            ("firefly", ["fire", "fly"]),
        ],
    },
    "de": {
        "stems": ["Haus", "Wasser", "Feuer", "Luft", "Erde", "Baum", "Tag", "Nacht", "Auto", "Mann", "Frau", "Kind", "Buch", "Stadt", "Land", "Regen", "Schnee", "Wind", "Berg", "See", "Fluss"],
        "tails": ["haus", "wasser", "feuer", "luft", "erde", "baum", "tag", "nacht", "auto", "mann", "frau", "kind", "buch", "stadt", "land", "regen", "schnee", "wind", "berg", "see", "fluss"],
        "examples": [
            ("Hausaufgabe", ["Haus", "Aufgabe"]),
            ("Wassermelone", ["Wasser", "Melone"]),
            ("Tageslicht", ["Tag", "Licht"]),
            ("Handschuh", ["Hand", "Schuh"]),
            ("Regenschirm", ["Regen", "Schirm"]),
            ("Schneemann", ["Schnee", "Mann"]),
            ("Feuerwerk", ["Feuer", "Werk"]),
            ("Kindergarten", ["Kinder", "Garten"]),
            ("Flugzeug", ["Flug", "Zeug"]),
        ],
    },
    "fr": {
        "stems": ["eau", "feu", "terre", "maison", "homme", "femme", "enfant", "livre", "ville", "mer", "jour", "nuit", "soleil", "lune", "vent", "jardin"],
        "tails": ["eau", "feu", "terre", "maison", "homme", "femme", "ville", "mer", "jour", "nuit", "soleil", "lune", "vent", "jardin", "terrain"],
        "examples": [
            ("portefeuille", ["porte", "feuille"]),
            ("garde-robe", ["garde", "robe"]),
            ("parapluie", ["para", "pluie"]),
            ("pomme de terre", ["pomme", "terre"]),
            ("arc-en-ciel", ["arc", "ciel"]),
            ("abat-jour", ["abat", "jour"]),
            ("essuie-glace", ["essuie", "glace"]),
            ("grille-pain", ["grille", "pain"]),
            ("coupe-ongles", ["coupe", "ongles"])
        ],
    },
    "es": {
        "stems": ["agua", "fuego", "tierra", "casa", "hombre", "mujer", "niño", "libro", "ciudad", "mar", "día", "noche", "sol", "luna", "viento", "jardín"],
        "tails": ["agua", "fuego", "tierra", "casa", "hombre", "mujer", "libro", "ciudad", "mar", "día", "noche", "sol", "luna", "mente", "ción"],
        "examples": [
            ("paraguas", ["para", "aguas"]),
            ("pararrayos", ["para", "rayos"]),
            ("abrelatas", ["abre", "latas"]),
            ("cortacésped", ["corta", "césped"]),
            ("rascacielos", ["rasca", "cielos"]),
            ("limpiaparabrisas", ["limpia", "parabrisas"]),
            ("tragaluz", ["traga", "luz"]),
            ("matamoscas", ["mata", "moscas"]),
            ("salvavidas", ["salva", "vidas"])
        ],
    },
    "it": {
        "stems": ["acqua", "fuoco", "terra", "casa", "uomo", "donna", "bambino", "libro", "città", "mare", "giorno", "notte", "sole", "luna", "vento", "giardino"],
        "tails": ["acqua", "fuoco", "terra", "casa", "uomo", "donna", "libro", "città", "mare", "giorno", "notte", "sole", "luna", "mente", "zione"],
        "examples": [
            ("portafoglio", ["porta", "foglio"]),
            ("parapioggia", ["para", "pioggia"]),
            ("pomodoro", ["pomo", "doro"]),
            ("ferrovia", ["ferro", "via"]),
            ("terremoto", ["terra", "moto"]),
            ("capolavoro", ["capo", "lavoro"]),
            ("lavastoviglie", ["lava", "stoviglie"]),
            ("salvagente", ["salva", "gente"]),
            ("portacenere", ["porta", "cenere"]),
            ("apriscatole", ["apri", "scatole"])
        ],
    },
}

# Объединение частей
def build_word(parts: List[str], lang: str) -> str:
    if not parts:
        return ""
    
    result = parts[0]
    for next_part in parts[1:]:
        if result and next_part and result[-1] == next_part[0]:
            result = result + next_part[1:]
        else:
            result = result + next_part
    
    if lang == "de" and result:
        result = result[0].upper() + result[1:]
    
    return result

# Генерация одного составного слова
def generate_compound(stems: List[str], tails: List[str], lang: str, rng: random.Random) -> Tuple[str, List[str]]:
    for _ in range(50):
        stem = rng.choice(stems)
        tail = rng.choice(tails)
        
        if stem.lower() == tail.lower():
            continue
        
        parts = [stem, tail]
        word = build_word(parts, lang)
        
        # Простая проверка: слово не слишком длинное
        if 4 <= len(word) <= 20:
            return word, parts
    
    return None, None

# Генерация датасета
def generate_dataset(lang: str, n: int, seed: int, stems: List[str], tails: List[str], examples: List[Tuple[str, List[str]]]) -> List[dict]:
    rng = random.Random(seed)
    rows = []
    seen = set()

    # Добавляем примеры
    for word, parts in examples:
        if word not in seen:
            rows.append({
                "input": {"lang": lang, "word": word},
                "target": {"kind": "compound", "parts": parts}
            })
            seen.add(word)
    
    # Генерация
    generated = 0
    attempts = 0
    
    while generated < n and attempts < n * 30:
        attempts += 1
        word, parts = generate_compound(stems, tails, lang, rng)
        
        if word and word not in seen:
            rows.append({
                "input": {"lang": lang, "word": word},
                "target": {"kind": "compound", "parts": parts}
            })
            seen.add(word)
            generated += 1
    return rows

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", default="all")
    parser.add_argument("--n", type=int, default=500)
    parser.add_argument("--out-dir", default="data")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    if args.lang == "all":
        langs = ["en", "de", "fr", "es", "it"]
    else:
        langs = [args.lang]
    
    all_rows = []
    
    for lang in langs:
        config = LANG_DATA[lang]
        rows = generate_dataset(
            lang=lang,
            n=args.n,
            seed=args.seed,
            stems=config["stems"],
            tails=config["tails"],
            examples=config["examples"]
        )
        
        # Сохраняем
        out_file = out_dir / f"compounds_{lang}.jsonl"
        with out_file.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        all_rows.extend(rows)
    
    # Объединяем
    if args.lang == "all":
        all_file = out_dir / "all_compounds.jsonl"
        with all_file.open("w", encoding="utf-8") as f:
            for row in all_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    main()