# Схемы для генерации мнемоники, где определяются структуры данных

from __future__ import annotations

from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Изучаемый язык
VerseLearningLanguage = Literal["en", "de", "es", "it", "fr"]
VERSE_LEARNING_LANGUAGE_CODES: frozenset[str] = frozenset(
    get_args(VerseLearningLanguage)
)

# Доступные модели для генерации стихотворений
VerseProvider = Literal["gptunnel", "chad", "yandex"]

class VersePreset(BaseModel):
    id: str
    label: str
    provider: VerseProvider
    model: str

VERSE_PRESETS: tuple[VersePreset, ...] = (
    # GPTunnel
    VersePreset(
        id="gptunnel:gpt-5.4",
        label="GPTunnel — gpt-5.4",
        provider="gptunnel",
        model="gpt-5.4",
    ),
    # Chad
    VersePreset(
        id="chad:gemini-3-flash",
        label="Chad — Gemini 3 Flash",
        provider="chad",
        model="gemini-3-flash",
    ),
    # Yandex Cloud
    VersePreset(
        id="yandex:deepseek-v32/latest",
        label="Yandex Cloud — DeepSeek V3.2",
        provider="yandex",
        model="deepseek-v32/latest",
    ),
)

# Множество всех допустимых ID пресетов
VERSE_PRESET_IDS: frozenset[str] = frozenset(p.id for p in VERSE_PRESETS)

# По умолчанию модель
DEFAULT_VERSE_PRESET_ID = "gptunnel:gpt-5.4"

# Нормализуем
def normalize_verse_generator_id(raw: str | None) -> str:
    if raw is None or not str(raw).strip():
        return DEFAULT_VERSE_PRESET_ID
    
    s = str(raw).strip()
    
    # Проверяем, валидный ли это ID
    if s in VERSE_PRESET_IDS:
        return s
    
    # Неизвестный ID, то возвращаем дефолтный
    return DEFAULT_VERSE_PRESET_ID

# Возвращаем объект VersePreset по его идентификатору
def get_preset_by_id(preset_id: str) -> VersePreset | None:
    for p in VERSE_PRESETS:
        if p.id == preset_id:
            return p
    return None

# Доступные модели для генерации изображений
ImageGeneratorChoice = Literal[
    "black-forest-labs/FLUX.1-schnell",
    "grok-imagine-text-to-image",
    "deepai-text2img",
]

# Схема запроса на генерацию мнемоники
class GenerateMnemoRequest(BaseModel):
    # Игнорируем лишние поля
    model_config = ConfigDict(extra="ignore")
    # Слово
    word: str = Field(..., min_length=1, max_length=128)
    # Перевод
    translation: str = Field(..., min_length=1, max_length=256)
    # Декомпозиция слова
    parts: list[str] | None = None
    # Созвучия
    consonance: str | None = None
    # Выбор модели
    verse_generator: str | None = Field(default=None, max_length=128)

    @field_validator("verse_generator", mode="before")
    @classmethod
    def _normalize_verse_generator(cls, v: object) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str):
            raise TypeError("verse_generator must be a string or null")
        s = v.strip()
        if not s:
            return None
        if s in VERSE_PRESET_IDS:
            return s
        raise ValueError("Unknown verse_generator")

    # Выбор генератора картинок
    image_generator: ImageGeneratorChoice | None = None

    # Пользовательский шаблон промпта для стихотворения
    verse_prompt_template: str | None = Field(default=None, max_length=32000)

    @field_validator("verse_prompt_template", mode="before")
    @classmethod
    def _strip_verse_prompt_template(cls, v: object) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str):
            raise TypeError("verse_prompt_template must be a string or null")
        s = v.strip()
        return s if s else None

    verse_learning_language: VerseLearningLanguage = "en"

    @field_validator("verse_learning_language", mode="before")
    @classmethod
    def _normalize_verse_learning_language(cls, v: object) -> str:
        if v is None:
            return "en"
        if not isinstance(v, str):
            raise TypeError("verse_learning_language must be a string")
        s = v.strip().lower()
        if s in VERSE_LEARNING_LANGUAGE_CODES:
            return s
        raise ValueError(
            "verse_learning_language must be one of: en, de, es, it, fr"
        )

# Схема ответа при генерации или получении мнемоники
class MnemoResponse(BaseModel):
    # Мнемонический стих
    mnemonic_phrase_ru: str
    # URL картинки
    image_url: str | None = None
    # Был ли ответ из кэша
    cache_hit: bool

# Схема ответа на запрос проверки сервиса
class HealthResponse(BaseModel):
    # Статус сервиса
    status: str
    # Словарь провайдеров
    providers: dict[str, bool]
    # Словарь с названиями моделей
    mnemo_models: dict[str, str] = Field(default_factory=dict)
    # Доступные модели генерации стихотворений
    verse_presets: list[VersePreset] = Field(default_factory=list)
    # Текст шаблона промпта
    verse_prompt_template_default: str = ""
    # Шаблоны промптов по языку
    verse_prompt_templates: dict[str, str] = Field(default_factory=dict)
    # Языки
    verse_learning_languages: list[dict[str, Any]] = Field(default_factory=list)
