# Модуль декомпозиции

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
import torch
from app.services.ipa_word import normalize_ipa_lang_code

logger = logging.getLogger(__name__)

# Извлекаем части слова из ответа
def _parts_from_generated_line(text: str) -> Optional[list[str]]:
    # Проверяем, что текст не пустой и есть разделитель "+"
    if not (text or "").strip() or "+" not in text:
        return None
    
    t = text.strip()
    # Разделяем по " + "
    parts = [p.strip().lower() for p in re.split(r"\s*\+\s*", t) if p.strip()]
    return parts if len(parts) >= 2 else None

# Оставляем только буквы
def _letters_only(s: str) -> str:
    normalized = unicodedata.normalize("NFC", (s or "").lower())
    return "".join(ch for ch in normalized if ch.isalpha())

# Проверяем, что склейка частей даёт исходное слово
def _compound_parts_spell_word(parts: list[str], word_letters: str) -> bool:
    if len(parts) < 2:
        return False
    joined = "".join(_letters_only(p) for p in parts)
    return joined == word_letters

# Результат декомпозиции
@dataclass
class DecompositionResult:
    src_lang: str
    word: str
    parts: list[str]

    def to_dict(self) -> dict:
        return asdict(self)

# Класс декомпозиции
class MnemoDecomposer:
    # Инициализация
    def __init__(
        self,
        *,
        decomposer_model_dir: Optional[str | Path] = None,
    ):
        # Нормализованный абсолютный путь к модели
        self.model_dir = self._resolve_model_dir(decomposer_model_dir)
        self._tok = None
        self._model = None
        self._disabled_reason: Optional[str] = None

    # Нормализация пути к директории модели
    @staticmethod
    def _resolve_model_dir(decomposer_model_dir: Optional[str | Path]) -> Optional[Path]:
        if decomposer_model_dir is not None:
            # Убираем пробелы/кавычки
            s = str(decomposer_model_dir).strip().strip("'").strip('"')
            if s:
                p = Path(s).expanduser()
                # Относительный путь приводим к абсолютному
                if not p.is_absolute():
                    p = (Path.cwd() / p).resolve()
                # Принимаем только существующую директорию
                if p.exists() and p.is_dir():
                    return p
                return None
        return None
    
    # Декомпозиция слова
    def decompose_word(self, word: str, lang: str = "en") -> DecompositionResult:
        code = normalize_ipa_lang_code(lang)
        w = (word or "").strip()
        w_l = w.lower()
        # Основная логика разбиения
        parts = self._split_compound_or_morphemes(w_l, code)
        return DecompositionResult(src_lang=code, word=w, parts=parts)
    
    # Гарантируем, что модель загружена в память
    def _ensure_loaded(self) -> bool:
        if self._disabled_reason is not None:
            return False
        
        # Уже загружена
        if self._tok is not None and self._model is not None:
            return True
        
        if self.model_dir is None:
            self._disabled_reason = "model dir is not found"
            logger.info("decomposer: model dir is not set or path missing")
            return False

        # Одна попытка загрузки модели
        self._tok = None
        self._model = None
        try:
            self._tok = AutoTokenizer.from_pretrained(
                str(self.model_dir),
                local_files_only=True,
            )
            self._model = AutoModelForSeq2SeqLM.from_pretrained(
                str(self.model_dir),
                local_files_only=True,
            )
            self._model.eval()
            logger.info("decomposer: model loaded from %s", self.model_dir)
            return True
        except Exception as e:
            self._tok = None
            self._model = None
            self._disabled_reason = f"failed to load model from {self.model_dir}: {e}"
            logger.warning("decomposer: %s", self._disabled_reason)
            return False
    
    # Функция разбора слова через модель
    def _split_compound_or_morphemes(self, w_l: str, lang_code: str) -> list[str]:
        word_only = _letters_only(w_l)

        if self._ensure_loaded():
            try:
                prompt = f"decompose {lang_code}: {w_l}"
                # Токенизация входа в тензоры
                inputs = self._tok([prompt], return_tensors="pt", truncation=True)
                # Генерация последовательности без градиентов
                with torch.no_grad():
                    out = self._model.generate(
                        **inputs, 
                        max_new_tokens=32,
                        num_beams=4,
                    )

                # Декодируем ответ модели в строку
                text = self._tok.decode(out[0], skip_special_tokens=True).strip()
                parsed = _parts_from_generated_line(text)

                if parsed and _compound_parts_spell_word(parsed, word_only):
                    return parsed

                if parsed and not _compound_parts_spell_word(parsed, word_only):
                    logger.debug(
                        "decomposer: model reply ignored (does not spell word=%r raw=%r parts=%s)",
                        w_l,
                        text[:200],
                        parsed,
                    )
                else:
                    logger.debug(
                        "decomposer: no «+» in model reply word=%r lang=%s raw=%r",
                        w_l,
                        lang_code,
                        text[:200],
                    )
            except Exception as e:
                logger.warning(f"decomposer error for '{w_l}' lang={lang_code}: {e}")

        logger.info(
            "decomposer: whole-word fallback word=%r lang=%s (no valid model «+» match, wordfreq not applied)",
            w_l,
            lang_code,
        )
        return [w_l]

_decomposer: MnemoDecomposer | None = None

# Инициализация singleton
def init_decomposer(model_dir: str | Path | None = None) -> None:
    global _decomposer
    raw = str(model_dir).strip().strip("'").strip('"') if model_dir else ""
    if raw:
        logger.info("decomposer: DECOMPOSER_MODEL_DIR=%s", raw)
    
    _decomposer = MnemoDecomposer(decomposer_model_dir=model_dir)

    if _decomposer.model_dir is None:
        logger.info("model directory decompose is not found")
    else:
        _decomposer._ensure_loaded()

# Возвращает singleton декомпозитора
def get_decomposer() -> MnemoDecomposer:
    global _decomposer
    if _decomposer is None:
        _decomposer = MnemoDecomposer()
    return _decomposer

# Декомпозиция
def decompose(word: str, lang: str = "en") -> dict:
    return get_decomposer().decompose_word(word, lang=lang).to_dict()