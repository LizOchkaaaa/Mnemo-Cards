# Файл настроек приложения

from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Определяем путь к файлу .env
def _env_file_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / ".env"

# Путь до модели
def _default_multilingual_decomposer_model_dir() -> str:
    return str(Path(__file__).resolve().parents[3] / "models" / "decomposer_multilingual")

# Настройки приложения
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_file_path(),        # Путь к .env файлу
        env_file_encoding="utf-8",        # Кодировка .env файла
        extra="ignore",                   # Игнорируем лишние переменные в .env
    )

    app_name: str                                                                      # Название приложения
    api_prefix: str                                                                    # Префикс API
    host: str                                                                          # Хост для запуска сервера
    port: int = Field(ge=1, le=65535)                                                  # Порт
    cors_allow_origins: str                                                            # Разрешённые CORS-домены
    cache_dir: Path = Field(validation_alias="MNEMO_CACHE_DIR")                        # Директория для кэша
    generated_images_dir: Path = Field(validation_alias="MNEMO_GENERATED_IMAGES_DIR")  # Директория для изображений

    # RuGPT
    rugpt_api_key: str | None = Field(default=None, repr=False)           # API-ключ
    rugpt_base_url: str                                                   # Базовый URL API
    rugpt_image_model: str                                                # Модель для генерации
    rugpt_image_aspect_ratio: str                                         # Соотношение сторон

    # Chad
    chad_api_key: str | None = Field(default=None, repr=False)            # API-ключ
    chad_text_model: str | None = None                                    # Модель для генерации

    # GPTunnel
    gptunnel_api_key: str | None = Field(default=None, repr=False)        # API-ключ
    gptunnel_base_url: str                                                # Базовый URL
    gptunnel_text_model: str = Field(default="gpt-5.4")                   # Модель по умолчанию

    # Yandex Cloud AI
    yandex_cloud_folder: str | None = Field(                              # ID каталога в Yandex Cloud
        default=None, 
        validation_alias="YANDEX_CLOUD_FOLDER"
    )
    yandex_cloud_api_key: str | None = Field(                             # API-ключ
        default=None, 
        repr=False, 
        validation_alias="YANDEX_CLOUD_API_KEY"
    )
    yandex_cloud_model: str = Field(                                      # Модель по умолчанию
        default="deepseek-v32/latest",
        validation_alias="YANDEX_CLOUD_MODEL",
    )
    yandex_cloud_base_url: str = Field(                                   # Базовый URL
        default="https://ai.api.cloud.yandex.net/v1",
        validation_alias="YANDEX_CLOUD_BASE_URL",
    )

    # MashaGPT
    mashagpt_api_key: str | None = Field(default=None, repr=False)        # API-ключ
    mashagpt_api_url: str                                                 # Базовый URL
    mashagpt_image_model: str                                             # Модель для изображений

    # DeepAI text2img (генерация изображений)
    deepai_api_key: str | None = Field(default=None, repr=False)          # API-ключ
    deepai_image_api_url: str = Field(                                    # URL API
        default="https://api.deepai.org/api/text2img"
    )

    jwt_secret: str                                                       # Секрет для JWT
    jwt_algorithm: str                                                    # Алгоритм
    jwt_expire_minutes: int = Field(ge=1, le=60 * 24 * 365)               # Время жизни токена
    database_url: str                                                     # URL подключения к базе данных
    decomposer_model_dir: str | None = None

    mnemo_verse_max_retries: int = Field(                                 # Макс. попыток генерации стиха
        default=5,
        ge=1,
        le=10,
        validation_alias="MNEMO_VERSE_MAX_RETRIES",
    )

    # Настройки рифм
    mnemo_rhyme_min_tail_match: int = Field(                              # Мин. совпадение IPA-символов
        default=3,
        ge=2,
        le=12,
        validation_alias="MNEMO_RHYME_MIN_TAIL_MATCH",
    )
    mnemo_rhyme_wordfreq_n: int = Field(                                  # Кол-во слов из wordfreq
        default=25000,
        ge=3000,
        le=100_000,
        validation_alias="MNEMO_RHYME_WORDFREQ_N",
    )
    mnemo_rhyme_max_ipa_checks: int = Field(                              # Лимит IPA-проверок
        default=1200,
        ge=500,
        le=50_000,
        validation_alias="MNEMO_RHYME_MAX_IPA_CHECKS",
    )
    mnemo_rhyme_wordfreq_full: bool = Field(                              # Загружать все слова wordfreq
        default=False, 
        validation_alias="MNEMO_RHYME_WORDFREQ_FULL"
    )
    mnemo_rhyme_ru_vowel_check: bool = Field(                             # Проверять конфликт гласных
        default=True, 
        validation_alias="MNEMO_RHYME_RU_VOWEL_CHECK"
    )
    mnemo_verbose_verse_debug: bool = Field(                              # Подробное логирование стихов
        default=False, 
        validation_alias="MNEMO_VERBOSE_VERSE_DEBUG"
    )

    deepai_image_width: str = Field(default="1024", validation_alias="DEEPAI_IMAGE_WIDTH")
    deepai_image_height: str = Field(default="576", validation_alias="DEEPAI_IMAGE_HEIGHT")
    deepai_image_generator_version: str = Field(default="hd", validation_alias="DEEPAI_IMAGE_GENERATOR_VERSION")
    deepai_genius_preference: str = Field(default="graphic", validation_alias="DEEPAI_GENIUS_PREFERENCE")
    deepai_super_genius_resolution: str = Field(default="2k", validation_alias="DEEPAI_SUPER_GENIUS_RESOLUTION")

    @field_validator(
        "rugpt_api_key",
        "chad_api_key",
        "chad_text_model",
        "gptunnel_api_key",
        "mashagpt_api_key",
        "deepai_api_key",
        "yandex_cloud_folder",
        "yandex_cloud_api_key",
        "decomposer_model_dir",
        mode="before",
    )

    # Преобразуем пустые строки в None
    @classmethod
    def _empty_to_none(cls, v: str | None) -> str | None:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        # Удаляем лишние кавычки и пробелы
        return v.strip().strip("'\"").strip() or None

    @field_validator(
        "rugpt_base_url", 
        "gptunnel_base_url", 
        "mashagpt_api_url", 
        "deepai_image_api_url", 
        mode="before"
    )

    # Очищаем URL
    @classmethod
    def _strip_url(cls, v: str | None) -> str:
        return (v or "").strip().rstrip("/")

    @field_validator("mnemo_rhyme_wordfreq_full", "mnemo_verbose_verse_debug", mode="before")

    # Преобразуем строки 'true'/'false' в булевые значения
    @classmethod
    def _coerce_bool_env_false_default(cls, v: object) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes")
        return bool(v)

    @field_validator("mnemo_rhyme_ru_vowel_check", mode="before")

    # Преобразуем в булевое значение
    @classmethod
    def _coerce_ru_vowel_check(cls, v: object) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("0", "false", "no"):
                return False
            return True
        return True

    @model_validator(mode="after")
    def _fallback_decomposer_to_multilingual(self) -> Settings:
        if self.decomposer_model_dir:
            return self
        return self.model_copy(update={"decomposer_model_dir": _default_multilingual_decomposer_model_dir()})

    # Преобразуем строку с CORS-доменами в кортеж
    def cors_allow_origins_tuple(self) -> tuple[str, ...]:
        if not self.cors_allow_origins or not self.cors_allow_origins.strip():
            return ("*",)
        
        parts = tuple(x.strip() for x in self.cors_allow_origins.split(",") if x.strip())
        return parts or ("*",)
    
# Возвращаем единственный экземпляр настроек
@lru_cache
def get_settings() -> Settings:
    return Settings()