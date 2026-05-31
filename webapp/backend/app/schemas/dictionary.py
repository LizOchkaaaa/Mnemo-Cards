# Схемы для работы со словарём пользователя, где определяются структуры данных

from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from app.services.ipa_word import normalize_ipa_lang_code

# Схема для создания нового слова в словаре
class UserWordCreate(BaseModel):
    # Слово
    word: str = Field(..., min_length=1, max_length=256)
    # Перевод
    translation: str = Field(..., min_length=1, max_length=512)
    # Транскрипция
    transcription: str | None = Field(None, max_length=256)
    # Категория
    category: str | None = Field(None, max_length=128)
    # В избранном
    is_favorite: bool = False
    # Язык изучения
    word_language: str = Field(default="en", max_length=8)

    @field_validator("word_language", mode="before")
    @classmethod
    def _v_word_language_create(cls, v: object) -> str:
        return normalize_ipa_lang_code(str(v or "en"))

# Схема для обновления существующего слова
class UserWordUpdate(BaseModel):
    # Новое слово
    word: str | None = Field(None, min_length=1, max_length=256)
    # Новый перевод
    translation: str | None = Field(None, min_length=1, max_length=512)
    # Новая транскрипция
    transcription: str | None = Field(None, max_length=256)
    # Новая категория
    category: str | None = Field(None, max_length=128)
    # Новое состояние "избранное"
    is_favorite: bool | None = None
    # Новое состояние "выучено"
    is_learned: bool | None = None
    # Язык слова
    word_language: str | None = Field(None, max_length=8)

    @field_validator("word_language", mode="before")
    @classmethod
    def _v_word_language_update(cls, v: object) -> str | None:
        if v is None or str(v).strip() == "":
            return None
        return normalize_ipa_lang_code(str(v))

# Оценка ответа по SM-2
class SrsReviewRequest(BaseModel):
    quality: int = Field(..., ge=0, le=5)


# Схема ответа при получении слова
class UserWordResponse(BaseModel):
    id: int                          # ID записи в БД
    word: str                        # Слово
    translation: str                 # Перевод
    transcription: str | None        # Транскрипция
    category: str | None             # Категория
    word_language: str = "en"        # Язык слова
    is_favorite: bool                # В избранном
    is_learned: bool = False         # Выучено
    parts: list[str] | None = None   # Декомпозиция
    # SM-2
    srs_easiness: float | None = None           # Коэффициент лёгкости
    srs_interval_days: int | None = None        # Интервал повторения
    srs_repetitions: int | None = None          # Количество успешных повторений
    srs_next_review_at: datetime | None = None  # Дата следующего повторения

# Схема ответа при запросе транскрипции
class TranscriptionResponse(BaseModel):
    transcription: str

# Схема ответа при запросе перевода
class TranslationResponse(BaseModel):
    translation: str

# Схема ответа при запросе произношения
class PronunciationResponse(BaseModel):
    audio_url: str

# Схема ответа при запросе декомпозиции слова
class DecompositionResponse(BaseModel):
    word: str            # слово
    translation_ru: str  # перевод
    parts: list[str]     # части


# Экспорт словаря в DOCX
class ExportDocxRequest(BaseModel):
    entry_ids: list[int] = Field(..., min_length=1, max_length=500)