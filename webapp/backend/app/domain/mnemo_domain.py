# Файл движка для генерации мнемоники

from __future__ import annotations

import logging
from dataclasses import replace
from app.core import Settings
from app.mnemo import decompose as decompose_word
from app.mnemo import get_ipa
from app.repository.decomposition_cache_repository import DecompositionCacheRepository
from app.repository.mnemo_cache_repository import WordMnemoRepository
from app.repository.user_words_repository import UserWordsRepository
from app.schemas.mnemo import (
    GenerateMnemoRequest,
    HealthResponse,
    ImageGeneratorChoice,
    MnemoResponse,
    VERSE_PRESETS,
    VersePreset,
    get_preset_by_id,
    normalize_verse_generator_id,
)
from app.services.mnemo_generation import (
    MnemoProvidersConfig,
    mnemo_providers_config_from_settings,
    mnemoClass,
)
from app.services.verse_prompt import (
    DEFAULT_VERSE_PROMPT_TEMPLATE,
    VERSE_PROMPT_TEMPLATES,
    get_default_verse_prompt_template,
)

logger = logging.getLogger(__name__)

# Нормализуем язык
def _cache_lang(lang: object) -> str:
    s = str(lang or "en").strip().lower()
    return (s[:2] if len(s) >= 2 else "en") or "en"

# Движок для генерации мнемонических карточек
class MnemoDomainEngine:
    # Инифиализация
    def __init__(
        self,
        settings: Settings,
        mnemo_cache_repo: WordMnemoRepository | None = None,
        decomposition_cache_repo: DecompositionCacheRepository | None = None,
        user_words_repo: UserWordsRepository | None = None,
    ):
        self.settings = settings
        self.mnemo_cache_repo = mnemo_cache_repo 
        self.decomposition_cache_repo = decomposition_cache_repo 
        self.user_words_repo = user_words_repo       
        self.provider_config = mnemo_providers_config_from_settings(settings)

    # Преобразуем публичный токен в полный URL изображения
    def _to_image_public_url(self, token: str | None) -> str | None:
        if not token:
            return None
        return f"{self.settings.api_prefix}/mnemo/image/public/{token}"
    
    # Определяем, какой генератор изображений использовать
    @staticmethod
    def _image_generator_for_request(request: GenerateMnemoRequest) -> ImageGeneratorChoice:
        ig = request.image_generator
        if ig is None:
            return "black-forest-labs/FLUX.1-schnell"
        return ig

    # Определяем какой генератор стихотворений использовать
    @staticmethod
    def _verse_preset_for_request(verse_generator: str | None) -> VersePreset:
        pid = normalize_verse_generator_id(verse_generator)
        preset = get_preset_by_id(pid)
        if preset is None:
            preset = get_preset_by_id(normalize_verse_generator_id(None))
        assert preset is not None
        return preset

    # Обновляем конфигурацию провайдеров
    @staticmethod
    def _provider_config_for_preset(
        base: MnemoProvidersConfig, preset: VersePreset
    ) -> MnemoProvidersConfig:
        if preset.provider == "gptunnel":
            return replace(base, gptunnel_text_model=preset.model)
        if preset.provider == "chad":
            return replace(base, chad_text_model=preset.model)
        return replace(base, yandex_cloud_model=preset.model)
    
    # Генерируем мнемоническую карточку
    def generate(self, request: GenerateMnemoRequest, *, user_id: int) -> MnemoResponse:
        image_generator = self._image_generator_for_request(request)
        word = request.word.strip().lower()         
        trans = request.translation.strip()      
        req_lang = request.verse_learning_language   
        cache_ll = _cache_lang(req_lang)

        preview = trans[:80] if trans else ""
        logger.info(
            "[MNEMO] domain.generate start word=%r translation_preview=%r",
            word,
            preview,
        )

        # Проверка сохраненной
        if self.mnemo_cache_repo:
            cached = self.mnemo_cache_repo.get(user_id, word, learning_lang=cache_ll)
            if cached is not None:
                logger.info("[MNEMO] domain.generate cache hit word=%r", word)
                # Формируем URL картинки
                if getattr(cached, "image_url", None):
                    image_url = cached.image_url
                elif cached.image_public_token:
                    image_url = self._to_image_public_url(cached.image_public_token)
                else:
                    image_url = None
                return MnemoResponse(
                    mnemonic_phrase_ru=cached.mnemonic_phrase_ru,
                    image_url=image_url,
                    cache_hit=True,
                )
            
        # Декомпозиция
        image_parts: list[str] | None = None
        parts_for_decomp_cache: list[str] | None = None

        if request.parts and len(request.parts) >= 2:
            parts_for_decomp_cache = [x.strip() for x in request.parts if x.strip()]
            image_parts = parts_for_decomp_cache or None
            logger.info("[MNEMO] domain.generate using request parts=%s", image_parts)
        else:
            logger.info("[MNEMO] domain.generate fetching decomposition for word=%r", word)
            try:
                dec = decompose_word(request.word.strip(), lang=str(req_lang))
                raw = dec.get("parts") or []
                parts_for_decomp_cache = [str(p).strip() for p in raw if p]
                image_parts = parts_for_decomp_cache[:6] if parts_for_decomp_cache else None
                logger.info("[MNEMO] domain.generate decomposition parts=%s", image_parts)
            except Exception as exc:
                logger.warning("[MNEMO] domain.generate decomposition failed: %s", exc)
                image_parts = None
                parts_for_decomp_cache = None

        # Сохранение
        entry = (
            self.user_words_repo.get_by_user_and_word(user_id, word)
            if self.user_words_repo and word and trans and parts_for_decomp_cache
            else None
        )
        if self.decomposition_cache_repo and entry is not None and parts_for_decomp_cache:
            try:
                self.decomposition_cache_repo.save(entry.id, parts_for_decomp_cache)
                logger.info("[MNEMO] domain.generate decomposition saved to cache")
            except Exception as exc:
                logger.warning("[MNEMO] domain.generate decomposition cache save failed: %s", exc)

        verse_preset = self._verse_preset_for_request(request.verse_generator)
        request_provider_config = self._provider_config_for_preset(
            self.provider_config, verse_preset
        )

        logger.info(
            "[MNEMO] domain.generate pipeline word=%r verse_provider=%s preset_model=%r",
            word, verse_preset.provider, verse_preset.model,
        )

        # Получение транскрипции
        try:
            phonetic_ipa = get_ipa(word, lang=str(req_lang))
        except Exception as exc:
            logger.warning("[MNEMO] domain.generate get_ipa failed word=%r: %s", word, exc)
            phonetic_ipa = ""

        # Генерация
        generated = mnemoClass(providers=request_provider_config).generate(
            word_en=word,
            translation_ru=trans,
            parts=image_parts or [],
            phonetic_ipa=phonetic_ipa,
            verse_prompt_template=(
                request.verse_prompt_template
                if request.verse_prompt_template is not None
                else get_default_verse_prompt_template(req_lang)
            ),
            verse_provider=verse_preset.provider,
            image_generator=image_generator,
            verse_learning_language=str(req_lang),
            verse_max_retries=self.settings.mnemo_verse_max_retries,
        )

        logger.info(
            "[MNEMO] domain.generate pipeline finished word=%r verse_source=%s has_image=%s",
            word, generated.verse_source, bool(generated.image_data),
        )

        # Сохранение
        if self.mnemo_cache_repo:
            try:
                self.mnemo_cache_repo.save(
                    user_id=user_id,
                    word=word,
                    mnemonic_phrase_ru=generated.mnemonic_phrase_ru,
                    image_data=generated.image_data,
                    image_content_type=generated.image_content_type,
                    learning_lang=cache_ll,
                )
            except Exception as exc:
                logger.exception("[MNEMO] domain.generate mnemo cache save failed: %s", exc)

        # URL изображения
        image_url: str | None = None
        if self.mnemo_cache_repo:
            row_after = self.mnemo_cache_repo.get(user_id, word, learning_lang=cache_ll)
            if row_after is not None:
                if getattr(row_after, "image_url", None):
                    image_url = row_after.image_url
                elif generated.image_data and row_after.image_public_token:
                    image_url = self._to_image_public_url(row_after.image_public_token)

        return MnemoResponse(
            mnemonic_phrase_ru=generated.mnemonic_phrase_ru,
            image_url=image_url,
            cache_hit=False,
        )
    
    # Возвращаем сохраненную мнемокарточку
    def get_cache(self, word: str, *, user_id: int, learning_lang: str = "en") -> MnemoResponse | None:
        w = word.strip().lower()

        if not self.mnemo_cache_repo:
            return None

        cached = self.mnemo_cache_repo.get(user_id, w, learning_lang=learning_lang)
        if cached is None:
            return None

        # Формируем URL картинки
        if getattr(cached, "image_url", None):
            image_url = cached.image_url
        elif cached.image_data and cached.image_public_token:
            image_url = self._to_image_public_url(cached.image_public_token)
        else:
            image_url = None
            
        return MnemoResponse(
            mnemonic_phrase_ru=cached.mnemonic_phrase_ru,
            image_url=image_url,
            cache_hit=True,
        )
    
    # Возвращаем список слов, для которых есть сохраненные карточки
    def list_cached_words(self, user_id: int) -> list[str]:
        if not self.mnemo_cache_repo:
            return []
        return self.mnemo_cache_repo.list_words(user_id)
    
    # Статус сервисов
    def health(self) -> HealthResponse:
        s = self.settings
        
        # Какие провайдеры доступны
        yandex_configured = bool(s.yandex_cloud_api_key and s.yandex_cloud_folder)
        providers = {
            "chad_verse": True,
            "gptunnel_verse": True,
            "yandex_verse": yandex_configured,
            "mashagpt_image": True,
            "rugpt_image": True,
            "deepai_image": bool(s.deepai_api_key),
        }

        # Какие модели используются
        mnemo_models = {
            "verse_chad": (s.chad_text_model or "").strip(),
            "verse_gptunnel": (s.gptunnel_text_model or "").strip(),
            "verse_yandex": (s.yandex_cloud_model or "").strip(),
            "image_rugpt": (s.rugpt_image_model or "").strip(),
            "image_masha_task": (s.mashagpt_image_model or "").strip(),
            "image_deepai": (s.deepai_image_api_url or "").strip(),
        }

        return HealthResponse(
            status="ok",
            providers=providers,
            mnemo_models=mnemo_models,
            verse_presets=list(VERSE_PRESETS),
            verse_prompt_template_default=DEFAULT_VERSE_PROMPT_TEMPLATE,
            verse_prompt_templates=dict(VERSE_PROMPT_TEMPLATES),
            verse_learning_languages=[
                {"id": "en", "label": "Английский", "active": True},
                {"id": "de", "label": "Немецкий", "active": True},
                {"id": "fr", "label": "Французский", "active": True},
                {"id": "es", "label": "Испанский", "active": True},
                {"id": "it", "label": "Итальянский", "active": True},
            ],
        )